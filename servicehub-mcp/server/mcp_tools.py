"""
MCP tools for ServiceHub.

Exposes service center search, slot availability, and booking management
as MCP tools that can be invoked by AI assistants.
"""

from datetime import date, timedelta

from fastmcp import FastMCP

from .database import get_connection


def load_tools(mcp: FastMCP) -> None:
    """Register all ServiceHub MCP tools with the FastMCP server."""

    @mcp.tool
    def health() -> dict:
        """Check ServiceHub server health and database connectivity."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM service_centers")
                    count = cur.fetchone()[0]
            return {"status": "healthy", "service_centers": count}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @mcp.tool
    def list_states() -> list[str]:
        """List all Indian states that have registered service centers."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT state FROM service_centers ORDER BY state")
                return [row[0] for row in cur.fetchall()]

    @mcp.tool
    def list_cities(state: str) -> list[str]:
        """
        List cities in a state that have service centers.

        Args:
            state: Indian state name (e.g. 'Karnataka', 'Maharashtra')
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT city FROM service_centers WHERE state = %s ORDER BY city",
                    (state,),
                )
                return [row[0] for row in cur.fetchall()]

    @mcp.tool
    def list_areas(state: str, city: str) -> list[str]:
        """
        List locality areas in a city that have service centers.

        Args:
            state: State name
            city: City name
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT area FROM service_centers WHERE state = %s AND city = %s ORDER BY area",
                    (state, city),
                )
                return [row[0] for row in cur.fetchall()]

    @mcp.tool
    def search_service_centers(
        state: str = "",
        city: str = "",
        area: str = "",
    ) -> list[dict]:
        """
        Search for service centers by location. All parameters are optional filters.

        Args:
            state: State name filter
            city: City name filter
            area: Area/locality filter
        """
        conditions = []
        params = []
        if state:
            conditions.append("state = %s")
            params.append(state)
        if city:
            conditions.append("city = %s")
            params.append(city)
        if area:
            conditions.append("area = %s")
            params.append(area)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, name, state, city, area, address, phone,
                           capacity_per_day, working_hours, working_days
                    FROM service_centers {where}
                    ORDER BY state, city, area, name
                    """,
                    params,
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    @mcp.tool
    def get_slot_availability(
        center_id: int,
        days_ahead: int = 14,
    ) -> list[dict]:
        """
        Get slot availability for a service center for the next N days.

        Args:
            center_id: Service center ID
            days_ahead: Number of days to look ahead (default 14)
        """
        start = date.today()
        end = start + timedelta(days=days_ahead - 1)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.dt::date AS slot_date,
                        sc.capacity_per_day AS total_slots,
                        COALESCE(ss.booked_slots, 0) AS booked_slots,
                        sc.capacity_per_day - COALESCE(ss.booked_slots, 0) AS available_slots
                    FROM service_centers sc
                    CROSS JOIN generate_series(%s::date, %s::date, '1 day') AS d(dt)
                    LEFT JOIN service_slots ss
                        ON ss.center_id = sc.id AND ss.slot_date = d.dt::date
                    WHERE sc.id = %s
                    ORDER BY slot_date
                    """,
                    (start, end, center_id),
                )
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                for r in rows:
                    r["slot_date"] = str(r["slot_date"])
                return rows

    @mcp.tool
    def create_booking(
        center_id: int,
        slot_date: str,
        vehicle_number: str,
        customer_name: str = "",
        service_type: str = "General Service",
    ) -> dict:
        """
        Book a service slot for a vehicle.

        Args:
            center_id: Service center ID
            slot_date: Date in YYYY-MM-DD format
            vehicle_number: Vehicle registration number (e.g. MH12AB1234)
            customer_name: Customer's name (optional)
            service_type: Type of service (default: General Service)
        """
        import re
        cleaned = vehicle_number.strip().upper().replace(" ", "")
        if not re.match(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$", cleaned):
            return {"error": "Invalid vehicle number format. Expected: MH12AB1234"}

        try:
            booking_date = date.fromisoformat(slot_date)
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD."}

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO service_slots (center_id, slot_date, total_slots, booked_slots)
                    VALUES (%s, %s, (SELECT capacity_per_day FROM service_centers WHERE id = %s), 1)
                    ON CONFLICT (center_id, slot_date) DO UPDATE
                        SET booked_slots = service_slots.booked_slots + 1
                    WHERE service_slots.booked_slots < service_slots.total_slots
                    RETURNING booked_slots, total_slots
                    """,
                    (center_id, booking_date, center_id),
                )
                if cur.fetchone() is None:
                    return {"error": "No available slots for this date."}

                cur.execute(
                    """
                    INSERT INTO bookings (center_id, slot_date, vehicle_number, customer_name, service_type)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, slot_date
                    """,
                    (center_id, booking_date, cleaned, customer_name, service_type),
                )
                row = cur.fetchone()
                conn.commit()
                return {"booking_id": row[0], "slot_date": str(row[1]), "vehicle_number": cleaned}

    @mcp.tool
    def cancel_booking(booking_id: int) -> dict:
        """
        Cancel an existing booking by its ID.

        Args:
            booking_id: The booking ID to cancel
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM bookings WHERE id = %s RETURNING center_id, slot_date",
                    (booking_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return {"error": f"Booking {booking_id} not found."}
                center_id, slot_date = row
                cur.execute(
                    """
                    UPDATE service_slots
                    SET booked_slots = GREATEST(0, booked_slots - 1)
                    WHERE center_id = %s AND slot_date = %s
                    """,
                    (center_id, slot_date),
                )
                conn.commit()
                return {"message": "Booking cancelled", "booking_id": booking_id}

    @mcp.tool
    def list_bookings(center_id: int, slot_date: str) -> list[dict]:
        """
        List all bookings for a service center on a given date.

        Args:
            center_id: Service center ID
            slot_date: Date in YYYY-MM-DD format
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, vehicle_number, customer_name, customer_phone,
                           service_type, notes, created_at
                    FROM bookings
                    WHERE center_id = %s AND slot_date = %s
                    ORDER BY created_at
                    """,
                    (center_id, slot_date),
                )
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                for r in rows:
                    r["created_at"] = r["created_at"].isoformat()
                return rows

    # ── Vehicle Profile MCP tools ─────────────────────────────────────────

    def _resolve_vehicle(plate: str) -> int | None:
        """Resolve a vehicle registration number to a driver ID."""
        cleaned = plate.strip().upper().replace(" ", "")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM drivers WHERE license_plate = %s",
                    (cleaned,),
                )
                row = cur.fetchone()
                return row[0] if row else None

    @mcp.tool
    def list_vehicles() -> list[dict]:
        """List all registered vehicles with registration number, make/model, type, latest score, and risk band."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT d.license_plate, d.vehicle_type, d.vehicle_make,
                           d.vehicle_model, d.vehicle_year, d.name AS owner_name,
                           d.city, ds.overall_score, ds.risk_band
                    FROM drivers d
                    LEFT JOIN LATERAL (
                        SELECT overall_score, risk_band
                        FROM driver_scores
                        WHERE driver_id = d.id
                        ORDER BY week_date DESC LIMIT 1
                    ) ds ON TRUE
                    ORDER BY d.license_plate
                    """
                )
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                for r in rows:
                    if r.get("overall_score") is not None:
                        r["overall_score"] = float(r["overall_score"])
                return rows

    @mcp.tool
    def get_vehicle_summary(vehicle_registration: str) -> dict:
        """
        Get a vehicle's latest scores and full details by registration number.

        Args:
            vehicle_registration: Vehicle registration number (e.g. KA01AB1234, MH02CD5678)
        """
        driver_id = _resolve_vehicle(vehicle_registration)
        if driver_id is None:
            return {"error": f"Vehicle {vehicle_registration} not found"}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT d.license_plate, d.name AS owner_name, d.city,
                           d.vehicle_type, d.vehicle_make, d.vehicle_model,
                           d.vehicle_year, d.battery_capacity_kwh,
                           d.engine_displacement_cc,
                           ds.overall_score, ds.safety_score, ds.efficiency_score,
                           ds.eco_score, ds.consistency_score, ds.risk_band,
                           ds.premium_multiplier
                    FROM drivers d
                    LEFT JOIN LATERAL (
                        SELECT overall_score, safety_score, efficiency_score,
                               eco_score, consistency_score, risk_band, premium_multiplier
                        FROM driver_scores
                        WHERE driver_id = d.id
                        ORDER BY week_date DESC LIMIT 1
                    ) ds ON TRUE
                    WHERE d.id = %s
                    """,
                    (driver_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"error": f"Vehicle {vehicle_registration} not found"}
                cols = [d[0] for d in cur.description]
                result = dict(zip(cols, row))
                for k in result:
                    if result[k] is None:
                        continue
                    if k not in ("license_plate", "owner_name", "city", "vehicle_type",
                                 "vehicle_make", "vehicle_model", "vehicle_year", "risk_band"):
                        result[k] = float(result[k])
                return result

    @mcp.tool
    def get_insurance_assessment(vehicle_registration: str) -> dict:
        """
        Get aggregated driving metrics for insurance risk assessment by vehicle registration number.

        Args:
            vehicle_registration: Vehicle registration number (e.g. KA01AB1234, MH02CD5678)
        """
        driver_id = _resolve_vehicle(vehicle_registration)
        if driver_id is None:
            return {"error": f"Vehicle {vehicle_registration} not found"}
        start = date.today() - timedelta(days=90)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT license_plate, vehicle_make, vehicle_model, vehicle_type FROM drivers WHERE id = %s",
                    (driver_id,),
                )
                vrow = cur.fetchone()
                vehicle_info = dict(zip([d[0] for d in cur.description], vrow)) if vrow else {}

                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total_trips,
                        COALESCE(SUM(distance_km), 0) AS total_distance_km,
                        COALESCE(AVG(avg_speed_kmh), 0) AS avg_speed,
                        COALESCE(MAX(max_speed_kmh), 0) AS max_speed_recorded,
                        COALESCE(SUM(hard_brakes), 0) AS total_hard_brakes,
                        COALESCE(SUM(rapid_accels), 0) AS total_rapid_accels,
                        COALESCE(AVG(highway_pct), 0) AS avg_highway_pct,
                        COUNT(*) FILTER (WHERE night_driving) AS night_trip_count,
                        COALESCE(SUM(idle_time_min), 0) AS total_idle_min
                    FROM trip_logs
                    WHERE driver_id = %s AND trip_date >= %s
                    """,
                    (driver_id, start),
                )
                agg_cols = [d[0] for d in cur.description]
                agg = dict(zip(agg_cols, cur.fetchone()))

                cur.execute(
                    """
                    SELECT overall_score, safety_score, risk_band, premium_multiplier
                    FROM driver_scores
                    WHERE driver_id = %s
                    ORDER BY week_date DESC LIMIT 1
                    """,
                    (driver_id,),
                )
                score_row = cur.fetchone()
                if score_row:
                    score_cols = [d[0] for d in cur.description]
                    agg.update(dict(zip(score_cols, score_row)))

                for k in agg:
                    if agg[k] is not None and k not in ("risk_band",):
                        try:
                            agg[k] = float(agg[k])
                        except (TypeError, ValueError):
                            pass
                return {**vehicle_info, **agg}

    @mcp.tool
    def compare_vehicles_insurance(vehicle_registrations: list[str]) -> list[dict]:
        """
        Side-by-side insurance risk comparison of up to 10 vehicles by registration number.

        Args:
            vehicle_registrations: List of vehicle registration numbers to compare (max 10, e.g. ["KA01AB1234", "MH02CD5678"])
        """
        if len(vehicle_registrations) > 10:
            return [{"error": "Maximum 10 vehicles for comparison"}]
        results = []
        for reg in vehicle_registrations:
            results.append(get_insurance_assessment(reg))
        return results

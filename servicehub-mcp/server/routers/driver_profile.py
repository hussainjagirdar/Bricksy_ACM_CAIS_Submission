"""Driver profile router — telemetry dashboard endpoints."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..database import get_connection

router = APIRouter(prefix="/api", tags=["Driver Profile"])


@router.get("/drivers")
def list_drivers():
    """List all drivers with vehicle summary."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.name, d.city, d.vehicle_type, d.vehicle_make,
                       d.vehicle_model, d.vehicle_year, d.license_plate,
                       ds.overall_score, ds.risk_band
                FROM drivers d
                LEFT JOIN LATERAL (
                    SELECT overall_score, risk_band
                    FROM driver_scores
                    WHERE driver_id = d.id
                    ORDER BY week_date DESC LIMIT 1
                ) ds ON TRUE
                ORDER BY d.id
                """
            )
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/drivers/{driver_id}")
def get_driver(driver_id: int):
    """Full driver profile."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, phone, email, city, vehicle_type,
                       vehicle_make, vehicle_model, vehicle_year,
                       license_plate, battery_capacity_kwh,
                       engine_displacement_cc
                FROM drivers WHERE id = %s
                """,
                (driver_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Driver not found")
            cols = [desc[0] for desc in cur.description]
            result = dict(zip(cols, row))
            # Convert Decimal to float for JSON
            for k in ("battery_capacity_kwh",):
                if result[k] is not None:
                    result[k] = float(result[k])
            return result


@router.get("/drivers/{driver_id}/trips")
def get_trips(
    driver_id: int,
    days: int = Query(default=90, ge=1, le=365),
):
    """Trip history for a driver."""
    start = date.today() - timedelta(days=days)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, trip_date, start_hour, distance_km, duration_min,
                       avg_speed_kmh, max_speed_kmh, hard_brakes, rapid_accels,
                       fuel_or_energy, highway_pct, night_driving, idle_time_min
                FROM trip_logs
                WHERE driver_id = %s AND trip_date >= %s
                ORDER BY trip_date, start_hour
                """,
                (driver_id, start),
            )
            cols = [desc[0] for desc in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            for r in rows:
                r["trip_date"] = str(r["trip_date"])
                for k in ("distance_km", "avg_speed_kmh", "max_speed_kmh",
                           "fuel_or_energy", "highway_pct"):
                    if r[k] is not None:
                        r[k] = float(r[k])
            return rows


@router.get("/drivers/{driver_id}/scores")
def get_scores(driver_id: int):
    """Score history over time."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT week_date, overall_score, safety_score,
                       efficiency_score, eco_score, consistency_score,
                       risk_band, premium_multiplier
                FROM driver_scores
                WHERE driver_id = %s
                ORDER BY week_date
                """,
                (driver_id,),
            )
            cols = [desc[0] for desc in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            for r in rows:
                r["week_date"] = str(r["week_date"])
                for k in ("overall_score", "safety_score", "efficiency_score",
                           "eco_score", "consistency_score", "premium_multiplier"):
                    if r[k] is not None:
                        r[k] = float(r[k])
            return rows


@router.get("/drivers/{driver_id}/vehicle-health")
def get_vehicle_health(driver_id: int):
    """Latest 8 weekly health snapshots."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT week_date, brake_wear_pct,
                       tyre_fl_psi, tyre_fr_psi, tyre_rl_psi, tyre_rr_psi,
                       battery_soh_pct, battery_soc_pct,
                       engine_health_pct, oil_life_pct, coolant_temp_c
                FROM vehicle_health
                WHERE driver_id = %s
                ORDER BY week_date DESC
                LIMIT 8
                """,
                (driver_id,),
            )
            cols = [desc[0] for desc in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            for r in rows:
                r["week_date"] = str(r["week_date"])
                for k in cols:
                    if k != "week_date" and r[k] is not None:
                        r[k] = float(r[k])
            return rows


@router.get("/drivers/{driver_id}/insurance-metrics")
def get_insurance_metrics(driver_id: int):
    """Aggregated insurance-relevant metrics + latest scores."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Latest scores
            cur.execute(
                """
                SELECT overall_score, safety_score, efficiency_score,
                       eco_score, consistency_score, risk_band, premium_multiplier
                FROM driver_scores
                WHERE driver_id = %s
                ORDER BY week_date DESC LIMIT 1
                """,
                (driver_id,),
            )
            score_row = cur.fetchone()
            if not score_row:
                raise HTTPException(status_code=404, detail="No score data for driver")
            score_cols = [desc[0] for desc in cur.description]
            scores = dict(zip(score_cols, score_row))
            for k in scores:
                if isinstance(scores[k], (int, float)):
                    pass
                elif scores[k] is not None and k != "risk_band":
                    scores[k] = float(scores[k])

            # Aggregated trip metrics (last 90 days)
            start = date.today() - timedelta(days=90)
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
            agg_row = cur.fetchone()
            agg_cols = [desc[0] for desc in cur.description]
            aggregates = dict(zip(agg_cols, agg_row))
            for k in aggregates:
                if aggregates[k] is not None:
                    aggregates[k] = float(aggregates[k])

            return {**scores, **aggregates}

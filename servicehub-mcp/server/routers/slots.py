"""Slots router — slot availability across a date range for service centers."""

from datetime import date

from fastapi import APIRouter, Query

from ..database import get_connection

router = APIRouter(prefix="/api", tags=["Slots"])


@router.get("/slots")
def get_slots(
    center_ids: list[int] = Query(..., description="List of center IDs"),
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
):
    """
    Return slot availability for one or more centers over a date range.

    Uses generate_series to fill in days with no bookings as fully available.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    sc.id AS center_id,
                    d.dt::date AS slot_date,
                    sc.capacity_per_day AS total_slots,
                    COALESCE(ss.booked_slots, 0) AS booked_slots,
                    sc.capacity_per_day - COALESCE(ss.booked_slots, 0) AS available_slots
                FROM service_centers sc
                CROSS JOIN generate_series(%s::date, %s::date, '1 day'::interval) AS d(dt)
                LEFT JOIN service_slots ss
                    ON ss.center_id = sc.id AND ss.slot_date = d.dt::date
                WHERE sc.id = ANY(%s)
                ORDER BY sc.id, slot_date
                """,
                (start_date, end_date, center_ids),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            # Convert date objects to ISO strings for JSON serialisation
            for r in rows:
                r["slot_date"] = str(r["slot_date"])
            return rows

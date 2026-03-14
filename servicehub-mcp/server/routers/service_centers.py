"""Service centers router — locations and center lookup endpoints."""

from fastapi import APIRouter, HTTPException, Query

from ..database import get_connection

router = APIRouter(prefix="/api", tags=["Service Centers"])


@router.get("/states")
def list_states():
    """Return all states that have service centers, sorted alphabetically."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT state FROM service_centers ORDER BY state")
            return [row[0] for row in cur.fetchall()]


@router.get("/cities")
def list_cities(state: str = Query(..., description="State name")):
    """Return all cities in a given state that have service centers."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT city FROM service_centers WHERE state = %s ORDER BY city",
                (state,),
            )
            return [row[0] for row in cur.fetchall()]


@router.get("/areas")
def list_areas(
    state: str = Query(..., description="State name"),
    city: str = Query(..., description="City name"),
):
    """Return all areas in a given state+city that have service centers."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT area FROM service_centers WHERE state = %s AND city = %s ORDER BY area",
                (state, city),
            )
            return [row[0] for row in cur.fetchall()]


@router.get("/centers")
def list_centers(
    state: str = Query(...),
    city: str = Query(...),
    area: str = Query(...),
):
    """Return all service centers matching state + city + area."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, state, city, area, address, phone, email,
                       capacity_per_day, working_hours, working_days
                FROM service_centers
                WHERE state = %s AND city = %s AND area = %s
                ORDER BY name
                """,
                (state, city, area),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


@router.get("/centers/{center_id}")
def get_center(center_id: int):
    """Return details for a single service center."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, state, city, area, address, phone, email,
                       capacity_per_day, working_hours, working_days
                FROM service_centers WHERE id = %s
                """,
                (center_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Service center not found")
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

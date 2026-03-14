"""Bookings router — create, list, and cancel service bookings."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
import re

from ..database import get_connection

router = APIRouter(prefix="/api", tags=["Bookings"])


class BookingCreate(BaseModel):
    center_id: int
    slot_date: date
    vehicle_number: str
    customer_name: str = ""
    customer_phone: str = ""
    service_type: str = "General Service"
    notes: str = ""

    @field_validator("vehicle_number")
    @classmethod
    def validate_vehicle_number(cls, v: str) -> str:
        cleaned = v.strip().upper().replace(" ", "")
        if not re.match(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$", cleaned):
            raise ValueError(
                "Invalid vehicle number format. Expected format: MH12AB1234"
            )
        return cleaned


@router.get("/bookings")
def list_bookings(
    center_id: int = Query(...),
    slot_date: date = Query(...),
):
    """Return all bookings for a given center on a specific date."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, center_id, slot_date, vehicle_number,
                       customer_name, customer_phone, service_type, notes, created_at
                FROM bookings
                WHERE center_id = %s AND slot_date = %s
                ORDER BY created_at
                """,
                (center_id, slot_date),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            for r in rows:
                r["slot_date"] = str(r["slot_date"])
                r["created_at"] = r["created_at"].isoformat()
            return rows


@router.post("/bookings", status_code=201)
def create_booking(payload: BookingCreate):
    """
    Create a new booking and atomically increment the booked_slots counter.
    Returns the created booking.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Upsert service_slots row, checking capacity
            cur.execute(
                """
                INSERT INTO service_slots (center_id, slot_date, total_slots, booked_slots)
                VALUES (
                    %s, %s,
                    (SELECT capacity_per_day FROM service_centers WHERE id = %s),
                    1
                )
                ON CONFLICT (center_id, slot_date) DO UPDATE
                    SET booked_slots = service_slots.booked_slots + 1
                WHERE service_slots.booked_slots < service_slots.total_slots
                RETURNING booked_slots, total_slots
                """,
                (payload.center_id, payload.slot_date, payload.center_id),
            )
            result = cur.fetchone()
            if result is None:
                raise HTTPException(
                    status_code=409,
                    detail="No available slots for this center on the selected date.",
                )

            # Create the booking record
            cur.execute(
                """
                INSERT INTO bookings
                    (center_id, slot_date, vehicle_number, customer_name,
                     customer_phone, service_type, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, center_id, slot_date, vehicle_number,
                          customer_name, customer_phone, service_type, notes, created_at
                """,
                (
                    payload.center_id,
                    payload.slot_date,
                    payload.vehicle_number,
                    payload.customer_name,
                    payload.customer_phone,
                    payload.service_type,
                    payload.notes,
                ),
            )
            cols = [d[0] for d in cur.description]
            row = dict(zip(cols, cur.fetchone()))
            row["slot_date"] = str(row["slot_date"])
            row["created_at"] = row["created_at"].isoformat()
            conn.commit()
            return row


@router.delete("/bookings/{booking_id}", status_code=200)
def cancel_booking(booking_id: int):
    """
    Cancel a booking and atomically decrement the booked_slots counter.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Fetch and delete booking
            cur.execute(
                "DELETE FROM bookings WHERE id = %s RETURNING center_id, slot_date",
                (booking_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Booking not found")

            center_id, slot_date = row
            # Decrement slot counter (floor at 0)
            cur.execute(
                """
                UPDATE service_slots
                SET booked_slots = GREATEST(0, booked_slots - 1)
                WHERE center_id = %s AND slot_date = %s
                """,
                (center_id, slot_date),
            )
            conn.commit()
            return {"message": "Booking cancelled successfully", "id": booking_id}

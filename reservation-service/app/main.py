from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.libmanager_common import (
    Reservation,
    ReservationCreateRequest,
    ReservationStatus,
    Role,
    Settings,
    build_audit_event,
    has_permission,
)

settings = Settings(service_name="reservation-service", service_port=8604)
app = FastAPI(title="LibManager Reservation Service", version="1.0.0")

reservations: dict[str, Reservation] = {}
queue_by_material: dict[str, list[str]] = {}
audit_log: list[dict[str, Any]] = []


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="reservation",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


class ReservationActionRequest(BaseModel):
    actor_id: str
    actor_role: Role


ReservationActionRequest.model_rebuild()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/reservations")
async def create_reservation(request: ReservationCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "reservation:create")

    queue = queue_by_material.setdefault(request.material_id, [])
    existing = [
        reservations[item_id]
        for item_id in queue
        if reservations[item_id].patron_id == request.patron_id
        and reservations[item_id].status in {ReservationStatus.WAITING, ReservationStatus.READY}
    ]
    if existing:
        raise HTTPException(status_code=409, detail="Active reservation already exists for this patron and material")

    reservation = Reservation(
        reservation_id=f"RES-{uuid4().hex[:10].upper()}",
        patron_id=request.patron_id,
        material_id=request.material_id,
        pickup_branch=request.pickup_branch,
        status=ReservationStatus.WAITING,
        queue_position=len(queue) + 1,
    )
    reservations[reservation.reservation_id] = reservation
    queue.append(reservation.reservation_id)
    _audit(request.actor_id, request.actor_role, "reservation.create", reservation.reservation_id)
    return reservation.model_dump(mode="json")


@app.get("/reservations")
async def list_reservations(
    patron_id: str | None = None,
    material_id: str | None = None,
    status: ReservationStatus | None = None,
) -> dict[str, Any]:
    items = []
    for reservation in reservations.values():
        if patron_id and reservation.patron_id != patron_id:
            continue
        if material_id and reservation.material_id != material_id:
            continue
        if status and reservation.status != status:
            continue
        items.append(reservation.model_dump(mode="json"))
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {"items": items, "count": len(items)}


@app.get("/reservations/material/{material_id}/queue")
async def material_queue(material_id: str) -> dict[str, Any]:
    queue = queue_by_material.get(material_id, [])
    items = [reservations[item_id].model_dump(mode="json") for item_id in queue if item_id in reservations]
    return {"material_id": material_id, "items": items, "count": len(items)}


@app.post("/reservations/{reservation_id}/ready")
async def mark_ready(reservation_id: str, request: ReservationActionRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "reservation:update")
    reservation = reservations.get(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation.status = ReservationStatus.READY
    reservation.notified_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "reservation.ready", reservation_id)
    return reservation.model_dump(mode="json")


@app.post("/reservations/{reservation_id}/fulfill")
async def fulfill(reservation_id: str, request: ReservationActionRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "reservation:update")
    reservation = reservations.get(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation.status = ReservationStatus.FULFILLED
    queue = queue_by_material.get(reservation.material_id, [])
    if reservation_id in queue:
        queue.remove(reservation_id)
    _audit(request.actor_id, request.actor_role, "reservation.fulfill", reservation_id)
    return reservation.model_dump(mode="json")


@app.post("/reservations/{reservation_id}/cancel")
async def cancel(reservation_id: str, request: ReservationActionRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "reservation:update")
    reservation = reservations.get(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation.status = ReservationStatus.CANCELLED
    queue = queue_by_material.get(reservation.material_id, [])
    if reservation_id in queue:
        queue.remove(reservation_id)
    _audit(request.actor_id, request.actor_role, "reservation.cancel", reservation_id)
    return reservation.model_dump(mode="json")


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

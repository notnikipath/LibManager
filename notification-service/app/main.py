from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.libmanager_common import NotificationChannel, Role, Settings, Severity, has_permission

settings = Settings(service_name="notification-service", service_port=8607)
app = FastAPI(title="LibManager Notification Service", version="1.0.0")

messages: list[dict[str, Any]] = []


class NotificationRequest(BaseModel):
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    severity: Severity = Severity.INFO
    actor_role: Role


class CheckoutNotificationRequest(BaseModel):
    patron_id: str
    material_title: str
    due_date: str
    actor_role: Role


class ReservationReadyNotificationRequest(BaseModel):
    patron_id: str
    material_title: str
    pickup_branch: str
    actor_role: Role


NotificationRequest.model_rebuild()
CheckoutNotificationRequest.model_rebuild()
ReservationReadyNotificationRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/notify/send")
async def send_notification(request: NotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = request.model_dump(mode="json")
    payload["status"] = "queued"
    messages.append(payload)
    return payload


@app.post("/notify/checkout")
async def notify_checkout(request: CheckoutNotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": NotificationChannel.PUSH.value,
        "recipient": request.patron_id,
        "subject": "Book checkout confirmed",
        "body": f"{request.material_title} is issued to your account until {request.due_date}.",
        "severity": Severity.INFO.value,
        "status": "queued",
    }
    messages.append(payload)
    return payload


@app.post("/notify/reservation-ready")
async def notify_reservation_ready(request: ReservationReadyNotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": NotificationChannel.SMS.value,
        "recipient": request.patron_id,
        "subject": "Reservation ready",
        "body": f"{request.material_title} is ready for pickup at {request.pickup_branch}.",
        "severity": Severity.INFO.value,
        "status": "queued",
    }
    messages.append(payload)
    return payload


@app.get("/notify/history")
async def history() -> dict[str, Any]:
    return {"items": messages, "count": len(messages)}

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.libmanager_common import (
    DebtSummary,
    Patron,
    PatronRegisterRequest,
    Role,
    Settings,
    build_audit_event,
    has_permission,
    recommend_materials,
)

settings = Settings(service_name="patron-service", service_port=8602)
app = FastAPI(title="LibManager Patron Service", version="1.0.0")


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="patron",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _seed_patron() -> Patron:
    return Patron(
        patron_id="PAT-001",
        full_name="Alexey Petrov",
        email="alexey.petrov@example.com",
        phone="+79990000001",
        e_card_number="ECARD-0001",
    )


patrons: dict[str, Patron] = {"PAT-001": _seed_patron()}
loan_history: dict[str, list[dict[str, Any]]] = {"PAT-001": []}
debts: dict[str, DebtSummary] = {"PAT-001": DebtSummary(patron_id="PAT-001", total_debt_rub=0, overdue_loans=0)}
audit_log: list[dict[str, Any]] = []


class HistoryAppendRequest(BaseModel):
    loan: dict[str, Any]
    actor_id: str
    actor_role: Role


class DebtUpdateRequest(BaseModel):
    total_debt_rub: float
    overdue_loans: int
    actor_id: str
    actor_role: Role


class RecommendationRequest(BaseModel):
    tag_index: dict[str, list[str]]


HistoryAppendRequest.model_rebuild()
DebtUpdateRequest.model_rebuild()
RecommendationRequest.model_rebuild()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/patrons")
async def list_patrons() -> dict[str, Any]:
    items = [patron.model_dump(mode="json") for patron in patrons.values()]
    return {"items": items, "count": len(items)}


@app.post("/patrons/register")
async def register_patron(
    request: PatronRegisterRequest,
    actor_id: str = "LIB-001",
    actor_role: Role = Role.LIBRARIAN,
) -> dict[str, Any]:
    _assert_permission(actor_role, "patron:create")
    patron_id = f"PAT-{uuid4().hex[:8].upper()}"
    patron = Patron(
        patron_id=patron_id,
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
        e_card_number=f"ECARD-{uuid4().hex[:8].upper()}",
    )
    patrons[patron_id] = patron
    loan_history[patron_id] = []
    debts[patron_id] = DebtSummary(patron_id=patron_id)
    _audit(actor_id, actor_role, "patron.register", patron_id)
    return patron.model_dump(mode="json")


@app.get("/patrons/{patron_id}")
async def get_patron(patron_id: str) -> dict[str, Any]:
    patron = patrons.get(patron_id)
    if patron is None:
        raise HTTPException(status_code=404, detail="Patron not found")
    return patron.model_dump(mode="json")


@app.get("/patrons/{patron_id}/history")
async def get_history(patron_id: str) -> dict[str, Any]:
    if patron_id not in patrons:
        raise HTTPException(status_code=404, detail="Patron not found")
    entries = loan_history.get(patron_id, [])
    return {"items": entries, "count": len(entries)}


@app.post("/patrons/{patron_id}/history")
async def append_history(patron_id: str, request: HistoryAppendRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "patron:update")
    if patron_id not in patrons:
        raise HTTPException(status_code=404, detail="Patron not found")
    entry = {**request.loan, "recorded_at": datetime.now(UTC).isoformat()}
    loan_history.setdefault(patron_id, []).append(entry)
    _audit(request.actor_id, request.actor_role, "patron.history.append", patron_id)
    return {"status": "ok", "entry": entry}


@app.get("/patrons/{patron_id}/debts")
async def get_debts(patron_id: str) -> dict[str, Any]:
    if patron_id not in patrons:
        raise HTTPException(status_code=404, detail="Patron not found")
    summary = debts.setdefault(patron_id, DebtSummary(patron_id=patron_id))
    return summary.model_dump(mode="json")


@app.post("/patrons/{patron_id}/debts/update")
async def update_debts(patron_id: str, request: DebtUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "patron:update")
    if patron_id not in patrons:
        raise HTTPException(status_code=404, detail="Patron not found")
    summary = DebtSummary(
        patron_id=patron_id,
        total_debt_rub=round(max(request.total_debt_rub, 0.0), 2),
        overdue_loans=max(request.overdue_loans, 0),
    )
    debts[patron_id] = summary
    _audit(
        request.actor_id,
        request.actor_role,
        "patron.debts.update",
        patron_id,
        {"total_debt_rub": summary.total_debt_rub, "overdue_loans": summary.overdue_loans},
    )
    return summary.model_dump(mode="json")


@app.post("/patrons/{patron_id}/recommendations")
async def recommendations(patron_id: str, request: RecommendationRequest) -> dict[str, Any]:
    if patron_id not in patrons:
        raise HTTPException(status_code=404, detail="Patron not found")

    history_entries = loan_history.get(patron_id, [])
    history_tags: list[str] = []
    for entry in history_entries:
        history_tags.extend(entry.get("tags", []))

    material_ids = recommend_materials(history_tags, request.tag_index, limit=8)
    return {"patron_id": patron_id, "material_ids": material_ids, "based_on_tags": history_tags[-20:]}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

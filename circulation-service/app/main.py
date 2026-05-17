from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.libmanager_common import (
    LoanCheckoutRequest,
    LoanRecord,
    LoanRenewRequest,
    LoanReturnRequest,
    MaterialType,
    Role,
    Settings,
    build_audit_event,
    calculate_overdue_fine,
    has_permission,
)

settings = Settings(service_name="circulation-service", service_port=8603)
app = FastAPI(title="LibManager Circulation Service", version="1.0.0")

loans: dict[str, LoanRecord] = {}
material_loans: dict[str, str] = {}
audit_log: list[dict[str, Any]] = []

# Outstanding fines that have not been settled yet.
fine_balance_by_patron: dict[str, float] = {"PAT-001": 0.0}


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="circulation",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


class SettleDebtRequest(BaseModel):
    amount_rub: float
    actor_id: str
    actor_role: Role


SettleDebtRequest.model_rebuild()


def _daily_rate(material_type: MaterialType) -> float:
    return {
        MaterialType.PRINTED_BOOK: 10.0,
        MaterialType.EBOOK: 3.0,
        MaterialType.AUDIOBOOK: 5.0,
        MaterialType.MAGAZINE: 8.0,
        MaterialType.DISSERTATION: 25.0,
    }[material_type]


def _debt_for_patron(patron_id: str) -> tuple[float, int]:
    now = datetime.now(UTC)
    overdue_loans = 0
    running = fine_balance_by_patron.get(patron_id, 0.0)

    for loan in loans.values():
        if loan.patron_id != patron_id:
            continue
        if loan.status == "active" and now > loan.due_date:
            overdue_loans += 1
            running += calculate_overdue_fine(loan.due_date, now, daily_rate=10.0)
    return round(max(running, 0.0), 2), overdue_loans


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/loans/checkout")
async def checkout(request: LoanCheckoutRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "circulation:checkout")
    if request.material_id in material_loans:
        loan_id = material_loans[request.material_id]
        active_loan = loans.get(loan_id)
        if active_loan and active_loan.status == "active":
            raise HTTPException(status_code=409, detail="Material already on loan")

    due_date = datetime.now(UTC) + timedelta(days=request.loan_days)
    loan = LoanRecord(
        loan_id=f"LOAN-{uuid4().hex[:10].upper()}",
        patron_id=request.patron_id,
        material_id=request.material_id,
        due_date=due_date,
    )
    loans[loan.loan_id] = loan
    material_loans[request.material_id] = loan.loan_id

    _audit(request.actor_id, request.actor_role, "loan.checkout", loan.loan_id, {"material_id": request.material_id})
    return loan.model_dump(mode="json")


@app.get("/loans/{loan_id}")
async def get_loan(loan_id: str) -> dict[str, Any]:
    loan = loans.get(loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan.model_dump(mode="json")


@app.get("/loans/by-patron/{patron_id}")
async def list_patron_loans(patron_id: str, active_only: bool = False) -> dict[str, Any]:
    items = []
    for loan in loans.values():
        if loan.patron_id != patron_id:
            continue
        if active_only and loan.status != "active":
            continue
        items.append(loan.model_dump(mode="json"))
    items.sort(key=lambda item: item["checkout_at"], reverse=True)
    return {"items": items, "count": len(items)}


@app.post("/loans/{loan_id}/renew")
async def renew(loan_id: str, request: LoanRenewRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "circulation:renew")
    loan = loans.get(loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.status != "active":
        raise HTTPException(status_code=409, detail="Only active loans can be renewed")
    if loan.renewals >= 2:
        raise HTTPException(status_code=409, detail="Renewal limit reached")

    loan.due_date = loan.due_date + timedelta(days=request.extension_days)
    loan.renewals += 1
    _audit(request.actor_id, request.actor_role, "loan.renew", loan_id, {"extension_days": request.extension_days})
    return loan.model_dump(mode="json")


@app.post("/loans/{loan_id}/return")
async def return_loan(loan_id: str, request: LoanReturnRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "circulation:return")
    loan = loans.get(loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    if loan.status != "active":
        raise HTTPException(status_code=409, detail="Loan is already closed")

    returned_at = request.returned_at or datetime.now(UTC)
    fine = calculate_overdue_fine(loan.due_date, returned_at, daily_rate=10.0)
    loan.returned_at = returned_at
    loan.fine_rub = fine
    loan.status = "returned"

    fine_balance_by_patron[loan.patron_id] = round(fine_balance_by_patron.get(loan.patron_id, 0.0) + fine, 2)
    material_loans.pop(loan.material_id, None)
    _audit(request.actor_id, request.actor_role, "loan.return", loan_id, {"fine_rub": fine})
    return loan.model_dump(mode="json")


@app.get("/debts/{patron_id}")
async def debts(patron_id: str) -> dict[str, Any]:
    total_debt, overdue_loans = _debt_for_patron(patron_id)
    return {
        "patron_id": patron_id,
        "total_debt_rub": total_debt,
        "overdue_loans": overdue_loans,
    }


@app.post("/debts/{patron_id}/settle")
async def settle_debt(patron_id: str, request: SettleDebtRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "circulation:return")
    current = fine_balance_by_patron.get(patron_id, 0.0)
    fine_balance_by_patron[patron_id] = round(max(0.0, current - max(request.amount_rub, 0.0)), 2)
    _audit(request.actor_id, request.actor_role, "debt.settle", patron_id, {"amount_rub": request.amount_rub})
    total_debt, overdue_loans = _debt_for_patron(patron_id)
    return {
        "patron_id": patron_id,
        "total_debt_rub": total_debt,
        "overdue_loans": overdue_loans,
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.libmanager_common import CheckoutWorkflowResult, Role, Settings, sign_token, verify_token


class GatewaySettings(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8600

    catalog_service_url: str = "http://catalog-service:8601"
    patron_service_url: str = "http://patron-service:8602"
    circulation_service_url: str = "http://circulation-service:8603"
    reservation_service_url: str = "http://reservation-service:8604"
    ebooks_service_url: str = "http://ebooks-service:8605"
    reports_service_url: str = "http://reports-service:8606"
    notification_service_url: str = "http://notification-service:8607"

    jwt_secret: str = Settings().jwt_secret
    token_exp_minutes: int = 240

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = GatewaySettings()
app = FastAPI(title="LibManager API Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5186",
        "http://127.0.0.1:5186",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    user_id: str
    role: Role
    language: str = Field(default="ru", pattern="^(ru|en)$")


class CheckoutWorkflowRequest(BaseModel):
    patron_id: str
    material_id: str
    loan_days: int = Field(default=14, ge=1, le=90)
    actor_id: str = "LIB-001"
    actor_role: Role = Role.LIBRARIAN


class ReturnWorkflowRequest(BaseModel):
    loan_id: str
    actor_id: str = "LIB-001"
    actor_role: Role = Role.LIBRARIAN


class ReserveWorkflowRequest(BaseModel):
    patron_id: str
    material_id: str
    pickup_branch: str
    actor_id: str = "LIB-001"
    actor_role: Role = Role.LIBRARIAN


class RenewWorkflowRequest(BaseModel):
    loan_id: str
    extension_days: int = Field(default=14, ge=1, le=30)
    actor_id: str = "LIB-001"
    actor_role: Role = Role.LIBRARIAN


class EbookReadWorkflowRequest(BaseModel):
    asset_id: str
    patron_id: str
    actor_id: str = "LIB-001"
    actor_role: Role = Role.LIBRARIAN


AuthRequest.model_rebuild()
CheckoutWorkflowRequest.model_rebuild()
ReturnWorkflowRequest.model_rebuild()
ReserveWorkflowRequest.model_rebuild()
RenewWorkflowRequest.model_rebuild()
EbookReadWorkflowRequest.model_rebuild()


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


def _service_urls() -> dict[str, str]:
    return {
        "catalog": settings.catalog_service_url,
        "patron": settings.patron_service_url,
        "circulation": settings.circulation_service_url,
        "reservation": settings.reservation_service_url,
        "ebooks": settings.ebooks_service_url,
        "reports": settings.reports_service_url,
        "notification": settings.notification_service_url,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/token")
async def issue_token(request: AuthRequest) -> dict[str, str]:
    token = sign_token(
        {"sub": request.user_id, "role": request.role.value, "language": request.language},
        settings.jwt_secret,
        exp_minutes=settings.token_exp_minutes,
    )
    return {"access_token": token, "token_type": "Bearer"}


@app.post("/auth/verify")
async def verify_auth(token: str) -> dict[str, Any]:
    payload = verify_token(token, settings.jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/services/health")
async def service_health() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, base_url in _service_urls().items():
            try:
                statuses[name] = await _get_json(client, f"{base_url}/health")
            except HTTPException as exc:
                statuses[name] = {"status": "error", "detail": exc.detail}
            except httpx.HTTPError as exc:
                statuses[name] = {"status": "error", "detail": str(exc)}
    return statuses


@app.get("/catalog/search")
async def catalog_search(
    title: str | None = None,
    author: str | None = None,
    isbn: str | None = None,
    udc: str | None = None,
    bbk: str | None = None,
    material_type: str | None = None,
    only_available: bool = False,
) -> dict[str, Any]:
    params = {
        "title": title,
        "author": author,
        "isbn": isbn,
        "udc": udc,
        "bbk": bbk,
        "material_type": material_type,
        "only_available": only_available,
    }
    params = {key: value for key, value in params.items() if value is not None}

    started = perf_counter()
    async with httpx.AsyncClient(timeout=10.0) as client:
        result = await _get_json(client, f"{settings.catalog_service_url}/materials", params=params)
        elapsed = perf_counter() - started
        await _post_json(
            client,
            f"{settings.reports_service_url}/reports/metrics",
            {
                "metric": "search_time",
                "value": round(elapsed, 3),
                "target": 1.0,
                "unit": "seconds",
                "actor_id": "SYSTEM",
                "actor_role": Role.SYSTEM.value,
            },
        )
    return result


@app.post("/workflow/checkout-book")
async def checkout_book(request: CheckoutWorkflowRequest) -> dict[str, Any]:
    started = perf_counter()
    async with httpx.AsyncClient(timeout=25.0) as client:
        material = await _get_json(client, f"{settings.catalog_service_url}/materials/{request.material_id}")
        if int(material.get("copies_available", 0)) <= 0:
            raise HTTPException(status_code=409, detail="Material is not available")

        debt = await _get_json(client, f"{settings.circulation_service_url}/debts/{request.patron_id}")
        if float(debt.get("total_debt_rub", 0.0)) > 0:
            raise HTTPException(status_code=409, detail="Patron has outstanding debts")

        loan = await _post_json(
            client,
            f"{settings.circulation_service_url}/loans/checkout",
            {
                "patron_id": request.patron_id,
                "material_id": request.material_id,
                "loan_days": request.loan_days,
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        await _post_json(
            client,
            f"{settings.catalog_service_url}/materials/{request.material_id}/availability",
            {
                "copies_available": int(material["copies_available"]) - 1,
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        await _post_json(
            client,
            f"{settings.patron_service_url}/patrons/{request.patron_id}/history",
            {
                "loan": {
                    "loan_id": loan["loan_id"],
                    "material_id": request.material_id,
                    "title": material["title"],
                    "tags": material.get("tags", []),
                    "status": loan["status"],
                    "due_date": loan["due_date"],
                },
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        notification = await _post_json(
            client,
            f"{settings.notification_service_url}/notify/checkout",
            {
                "patron_id": request.patron_id,
                "material_title": material["title"],
                "due_date": loan["due_date"],
                "actor_role": Role.SYSTEM.value,
            },
        )

        await _post_json(
            client,
            f"{settings.reports_service_url}/reports/demand",
            {
                "material_id": request.material_id,
                "event_type": "checkout",
            },
        )

        elapsed = perf_counter() - started
        await _post_json(
            client,
            f"{settings.reports_service_url}/reports/metrics",
            {
                "metric": "checkout_time",
                "value": round(elapsed, 3),
                "target": 10.0,
                "unit": "seconds",
                "actor_id": "SYSTEM",
                "actor_role": Role.SYSTEM.value,
            },
        )

    result = CheckoutWorkflowResult(material=material, debt=debt, loan=loan, notification=notification)
    return result.model_dump(mode="json")


@app.post("/workflow/return-book")
async def return_book(request: ReturnWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        loan = await _get_json(client, f"{settings.circulation_service_url}/loans/{request.loan_id}")
        returned = await _post_json(
            client,
            f"{settings.circulation_service_url}/loans/{request.loan_id}/return",
            {
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        material = await _get_json(client, f"{settings.catalog_service_url}/materials/{loan['material_id']}")
        updated_material = await _post_json(
            client,
            f"{settings.catalog_service_url}/materials/{loan['material_id']}/availability",
            {
                "copies_available": min(int(material["copies_total"]), int(material["copies_available"]) + 1),
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        debt = await _get_json(client, f"{settings.circulation_service_url}/debts/{loan['patron_id']}")
        await _post_json(
            client,
            f"{settings.patron_service_url}/patrons/{loan['patron_id']}/debts/update",
            {
                "total_debt_rub": debt["total_debt_rub"],
                "overdue_loans": debt["overdue_loans"],
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

    return {"loan": returned, "material": updated_material, "debt": debt}


@app.post("/workflow/reserve-book")
async def reserve_book(request: ReserveWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        material = await _get_json(client, f"{settings.catalog_service_url}/materials/{request.material_id}")
        reservation = await _post_json(
            client,
            f"{settings.reservation_service_url}/reservations",
            {
                "patron_id": request.patron_id,
                "material_id": request.material_id,
                "pickup_branch": request.pickup_branch,
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        await _post_json(
            client,
            f"{settings.reports_service_url}/reports/demand",
            {
                "material_id": request.material_id,
                "event_type": "reservation",
            },
        )

    return {"reservation": reservation, "material": material}


@app.post("/workflow/renew-loan")
async def renew_loan(request: RenewWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        renewed = await _post_json(
            client,
            f"{settings.circulation_service_url}/loans/{request.loan_id}/renew",
            {
                "extension_days": request.extension_days,
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )
        material = await _get_json(client, f"{settings.catalog_service_url}/materials/{renewed['material_id']}")
        notification = await _post_json(
            client,
            f"{settings.notification_service_url}/notify/send",
            {
                "channel": "push",
                "recipient": renewed["patron_id"],
                "subject": "Loan renewed",
                "body": f"Loan for {material['title']} renewed until {renewed['due_date']}",
                "actor_role": Role.SYSTEM.value,
            },
        )
    return {"loan": renewed, "notification": notification}


@app.post("/workflow/ebook-read")
async def ebook_read(request: EbookReadWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        grant = await _post_json(
            client,
            f"{settings.ebooks_service_url}/ebooks/grant-access",
            {
                "asset_id": request.asset_id,
                "patron_id": request.patron_id,
                "minutes": 60,
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )
        preview = await _post_json(client, f"{settings.ebooks_service_url}/ebooks/read", {"token": grant["token"]})
    return {"grant": grant, "preview": preview}


@app.get("/dashboard/patron/{patron_id}")
async def patron_dashboard(patron_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        patron = await _get_json(client, f"{settings.patron_service_url}/patrons/{patron_id}")
        history = await _get_json(client, f"{settings.patron_service_url}/patrons/{patron_id}/history")
        debts = await _get_json(client, f"{settings.patron_service_url}/patrons/{patron_id}/debts")
        active_loans = await _get_json(
            client,
            f"{settings.circulation_service_url}/loans/by-patron/{patron_id}",
            {"active_only": True},
        )
        reservations = await _get_json(
            client,
            f"{settings.reservation_service_url}/reservations",
            {"patron_id": patron_id},
        )
        demand = await _get_json(client, f"{settings.reports_service_url}/reports/demand/top", {"limit": 5})
        tag_index = await _get_json(client, f"{settings.catalog_service_url}/materials/tag-index")
        recommendations = await _post_json(
            client,
            f"{settings.patron_service_url}/patrons/{patron_id}/recommendations",
            {"tag_index": tag_index},
        )
        kpi = await _get_json(client, f"{settings.reports_service_url}/reports/metrics/targets")

    return {
        "patron": patron,
        "history": history,
        "debts": debts,
        "active_loans": active_loans,
        "reservations": reservations,
        "recommendations": recommendations,
        "demand": demand,
        "kpi": kpi,
    }

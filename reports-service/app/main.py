from __future__ import annotations

import asyncio
from collections import defaultdict
from statistics import mean
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from shared.libmanager_common import (
    DemandEvent,
    InventorySnapshot,
    Role,
    ServiceMetric,
    Settings,
    VisitEvent,
    build_audit_event,
    demand_score,
    forecast_demand,
    has_permission,
)

settings = Settings(service_name="reports-service", service_port=8606)
app = FastAPI(title="LibManager Reports Service", version="1.0.0")

visit_events: list[VisitEvent] = []
demand_events: list[DemandEvent] = []
inventory_snapshots: list[InventorySnapshot] = []
metrics_log: list[ServiceMetric] = []
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
            object_type="reports",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


class MetricIngestRequest(BaseModel):
    metric: str
    value: float
    target: float
    unit: str
    actor_id: str
    actor_role: Role


MetricIngestRequest.model_rebuild()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/reports/visits")
async def track_visit(event: VisitEvent, actor_id: str = "SYSTEM", actor_role: Role = Role.SYSTEM) -> dict[str, Any]:
    _assert_permission(actor_role, "reports:write")
    visit_events.append(event)
    _audit(actor_id, actor_role, "reports.visit", event.patron_id, {"branch_id": event.branch_id})
    return {"status": "accepted", "items": len(visit_events)}


@app.get("/reports/visits/stats")
async def visits_stats(branch_id: str | None = None) -> dict[str, Any]:
    filtered = [item for item in visit_events if not branch_id or item.branch_id == branch_id]
    by_branch: dict[str, int] = defaultdict(int)
    for item in filtered:
        by_branch[item.branch_id] += 1
    return {
        "total_visits": len(filtered),
        "by_branch": dict(by_branch),
        "unique_patrons": len({item.patron_id for item in filtered}),
    }


@app.post("/reports/demand")
async def track_demand(event: DemandEvent, actor_id: str = "SYSTEM", actor_role: Role = Role.SYSTEM) -> dict[str, Any]:
    _assert_permission(actor_role, "reports:write")
    demand_events.append(event)
    _audit(actor_id, actor_role, "reports.demand", event.material_id, {"event_type": event.event_type.value})
    return {"status": "accepted", "items": len(demand_events)}


@app.get("/reports/demand/top")
async def top_demand(limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: {"checkout": 0, "reservation": 0, "view": 0, "search": 0})
    for event in demand_events:
        matrix[event.material_id][event.event_type.value] += 1

    rows = []
    for material_id, counts in matrix.items():
        score = demand_score(counts["checkout"], counts["reservation"], counts["view"] + counts["search"])
        rows.append({"material_id": material_id, "score": score, **counts})
    rows.sort(key=lambda item: item["score"], reverse=True)
    return {"items": rows[:limit], "count": len(rows)}


@app.get("/reports/demand/forecast")
async def demand_forecast(material_id: str) -> dict[str, Any]:
    per_day = [0] * 30
    recent = [event for event in demand_events if event.material_id == material_id][-200:]
    for event in recent:
        day_index = min(max((event.timestamp.day % 30), 0), 29)
        per_day[day_index] += 1
    value = forecast_demand(per_day)
    return {"material_id": material_id, "forecast_next_3_days": value}


@app.post("/reports/inventory/snapshot")
async def snapshot_inventory(
    snapshot: InventorySnapshot,
    actor_id: str = "SYSTEM",
    actor_role: Role = Role.SYSTEM,
) -> dict[str, Any]:
    _assert_permission(actor_role, "reports:write")
    inventory_snapshots.append(snapshot)
    _audit(actor_id, actor_role, "reports.inventory.snapshot", snapshot.material_type.value)
    return {"status": "accepted", "items": len(inventory_snapshots)}


@app.get("/reports/inventory/latest")
async def latest_inventory() -> dict[str, Any]:
    latest_by_type: dict[str, dict[str, Any]] = {}
    for snapshot in inventory_snapshots:
        latest_by_type[snapshot.material_type.value] = snapshot.model_dump(mode="json")
    return {"items": list(latest_by_type.values()), "count": len(latest_by_type)}


@app.post("/reports/metrics")
async def ingest_metric(request: MetricIngestRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "reports:write")
    metric = ServiceMetric(metric=request.metric, value=request.value, target=request.target, unit=request.unit)
    metrics_log.append(metric)
    _audit(request.actor_id, request.actor_role, "reports.metric.ingest", request.metric)
    return metric.model_dump(mode="json")


@app.get("/reports/metrics/targets")
async def metric_targets() -> dict[str, Any]:
    latest = {}
    for metric in metrics_log:
        latest[metric.metric] = metric.model_dump(mode="json")

    defaults = {
        "search_time": ServiceMetric(
            metric="search_time",
            value=mean([metric.value for metric in metrics_log if metric.metric == "search_time"] or [0.0]),
            target=settings.search_target_seconds,
            unit="seconds",
        ).model_dump(mode="json"),
        "checkout_time": ServiceMetric(
            metric="checkout_time",
            value=mean([metric.value for metric in metrics_log if metric.metric == "checkout_time"] or [0.0]),
            target=settings.checkout_target_seconds,
            unit="seconds",
        ).model_dump(mode="json"),
        "catalog_capacity": ServiceMetric(
            metric="catalog_capacity",
            value=0,
            target=settings.catalog_capacity_target,
            unit="titles",
        ).model_dump(mode="json"),
    }
    defaults.update(latest)
    return {"items": list(defaults.values()), "count": len(defaults)}


@app.get("/reports/export")
async def export_report() -> dict[str, Any]:
    async def build_visits() -> dict[str, Any]:
        await asyncio.sleep(0)
        return await visits_stats()

    async def build_demand() -> dict[str, Any]:
        await asyncio.sleep(0)
        return await top_demand(limit=20)

    async def build_inventory() -> dict[str, Any]:
        await asyncio.sleep(0)
        return await latest_inventory()

    visits, demand, inventory = await asyncio.gather(build_visits(), build_demand(), build_inventory())
    return {
        "generated_in_parallel": True,
        "sections": {
            "visits": visits,
            "demand": demand,
            "inventory": inventory,
        },
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

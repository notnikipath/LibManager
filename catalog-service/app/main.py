from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from shared.libmanager_common import (
    CatalogMaterial,
    CatalogMaterialCreateRequest,
    CatalogMaterialUpdateRequest,
    MaterialType,
    Role,
    Settings,
    TTLCache,
    build_audit_event,
    estimate_search_latency_ms,
    has_permission,
)
from shared.libmanager_common.schemas import ClassificationCode

settings = Settings(service_name="catalog-service", service_port=8601)
app = FastAPI(title="LibManager Catalog Service", version="1.0.0")

search_cache = TTLCache(ttl_seconds=90)
audit_log: list[dict[str, Any]] = []
search_requests = 0
search_cache_hits = 0
index_last_rebuild_at: datetime | None = None


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="catalog",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _seed_materials() -> dict[str, CatalogMaterial]:
    seed_rows = [
        CatalogMaterial(
            material_id="MAT-PRINT-001",
            title="Clean Architecture",
            authors=["Robert C. Martin"],
            material_type=MaterialType.PRINTED_BOOK,
            isbn="9780134494166",
            publication_year=2017,
            classification=ClassificationCode(udc="004.42", bbk="32.973-018"),
            copies_total=6,
            copies_available=4,
            shelf_code="A-12",
            tags=["architecture", "software", "backend"],
            description="Printed book for software architecture fundamentals.",
        ),
        CatalogMaterial(
            material_id="MAT-EBOOK-001",
            title="Python for Data Analysis",
            authors=["Wes McKinney"],
            material_type=MaterialType.EBOOK,
            isbn="9781098104030",
            publication_year=2022,
            classification=ClassificationCode(udc="004.43", bbk="22.18"),
            copies_total=9999,
            copies_available=9999,
            shelf_code="DIGITAL",
            tags=["python", "data", "analytics"],
            description="Digital access edition.",
        ),
        CatalogMaterial(
            material_id="MAT-AUDIO-001",
            title="The Pragmatic Programmer (Audio)",
            authors=["Andrew Hunt", "David Thomas"],
            material_type=MaterialType.AUDIOBOOK,
            isbn="9780135957059",
            publication_year=2019,
            classification=ClassificationCode(udc="004", bbk="32.973"),
            copies_total=120,
            copies_available=120,
            shelf_code="AUDIO-3",
            tags=["programming", "career"],
            description="Audiobook edition.",
        ),
        CatalogMaterial(
            material_id="MAT-MAG-001",
            title="IEEE Software Vol. 43",
            authors=["IEEE"],
            material_type=MaterialType.MAGAZINE,
            publication_year=2026,
            classification=ClassificationCode(udc="004", bbk="32"),
            copies_total=40,
            copies_available=26,
            shelf_code="MAG-04",
            tags=["journal", "software"],
            description="Current issue magazine.",
        ),
        CatalogMaterial(
            material_id="MAT-DISS-001",
            title="Distributed Indexing in Large Digital Libraries",
            authors=["A. Ivanov"],
            material_type=MaterialType.DISSERTATION,
            publication_year=2024,
            classification=ClassificationCode(udc="025.4", bbk="78.37"),
            copies_total=1,
            copies_available=1,
            shelf_code="DISS-11",
            tags=["index", "libraries", "research"],
            description="PhD dissertation.",
        ),
    ]
    return {row.material_id: row for row in seed_rows}


materials: dict[str, CatalogMaterial] = _seed_materials()


class AvailabilityUpdateRequest(BaseModel):
    copies_available: int
    actor_id: str
    actor_role: Role


class MetadataMergeRequest(BaseModel):
    metadata: dict[str, Any]
    actor_id: str
    actor_role: Role


AvailabilityUpdateRequest.model_rebuild()
MetadataMergeRequest.model_rebuild()


def _matches(
    material: CatalogMaterial,
    title: str | None,
    author: str | None,
    isbn: str | None,
    udc: str | None,
    bbk: str | None,
    material_type: MaterialType | None,
    only_available: bool,
) -> bool:
    if title and title.lower() not in material.title.lower():
        return False
    if author and all(author.lower() not in item.lower() for item in material.authors):
        return False
    if isbn and material.isbn != isbn:
        return False
    if udc and udc.lower() not in material.classification.udc.lower():
        return False
    if bbk and bbk.lower() not in material.classification.bbk.lower():
        return False
    if material_type and material.material_type != material_type:
        return False
    if only_available and material.copies_available <= 0:
        return False
    return True


def _rebuild_index() -> None:
    global index_last_rebuild_at
    search_cache.clear()
    index_last_rebuild_at = datetime.now(UTC)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/materials")
async def search_materials(
    title: str | None = None,
    author: str | None = None,
    isbn: str | None = None,
    udc: str | None = None,
    bbk: str | None = None,
    material_type: MaterialType | None = None,
    only_available: bool = False,
) -> dict[str, Any]:
    global search_requests, search_cache_hits

    search_requests += 1
    cache_key = f"{title}|{author}|{isbn}|{udc}|{bbk}|{material_type}|{only_available}"
    cached = search_cache.get(cache_key)
    cache_hit = cached is not None
    if cache_hit:
        search_cache_hits += 1
        items = cached
    else:
        items = [
            material.model_dump(mode="json")
            for material in materials.values()
            if _matches(material, title, author, isbn, udc, bbk, material_type, only_available)
        ]
        search_cache.set(cache_key, items)

    hit_ratio = (search_cache_hits / search_requests) if search_requests else 0.0
    latency_ms = estimate_search_latency_ms(catalog_size=max(len(materials), 1), cache_hit_ratio=hit_ratio)
    return {
        "items": items,
        "count": len(items),
        "metrics": {
            "estimated_latency_ms": latency_ms,
            "target_seconds": settings.search_target_seconds,
            "cache_hit_ratio": round(hit_ratio, 3),
            "cache_hit": cache_hit,
        },
    }


@app.get("/materials/tag-index")
async def tag_index() -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for material in materials.values():
        for tag in material.tags:
            index.setdefault(tag.lower(), []).append(material.material_id)
    return index


@app.get("/materials/{material_id}")
async def get_material(material_id: str) -> dict[str, Any]:
    material = materials.get(material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return material.model_dump(mode="json")


@app.post("/materials")
async def create_material(
    request: CatalogMaterialCreateRequest,
    actor_id: str = "LIB-001",
    actor_role: Role = Role.LIBRARIAN,
) -> dict[str, Any]:
    _assert_permission(actor_role, "catalog:create")
    material = CatalogMaterial(
        material_id=f"MAT-{uuid4().hex[:10].upper()}",
        title=request.title,
        authors=request.authors,
        material_type=request.material_type,
        isbn=request.isbn,
        publication_year=request.publication_year,
        language=request.language,
        classification=request.classification,
        copies_total=request.copies_total,
        copies_available=request.copies_total,
        shelf_code=request.shelf_code,
        tags=request.tags,
        description=request.description,
    )
    materials[material.material_id] = material
    search_cache.clear()
    _audit(actor_id, actor_role, "catalog.material.create", material.material_id)
    return material.model_dump(mode="json")


@app.put("/materials/{material_id}")
async def update_material(
    material_id: str,
    request: CatalogMaterialUpdateRequest,
    actor_id: str = "LIB-001",
    actor_role: Role = Role.LIBRARIAN,
) -> dict[str, Any]:
    _assert_permission(actor_role, "catalog:update")
    material = materials.get(material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")

    payload = request.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(material, key, value)

    if material.copies_total < material.copies_available:
        material.copies_available = material.copies_total
    material.updated_at = datetime.now(UTC)
    search_cache.clear()
    _audit(actor_id, actor_role, "catalog.material.update", material_id, {"fields": list(payload.keys())})
    return material.model_dump(mode="json")


@app.post("/materials/{material_id}/availability")
async def set_availability(material_id: str, request: AvailabilityUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "catalog:availability:update")
    material = materials.get(material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    if request.copies_available < 0 or request.copies_available > material.copies_total:
        raise HTTPException(status_code=400, detail="copies_available out of range")

    material.copies_available = request.copies_available
    material.updated_at = datetime.now(UTC)
    search_cache.clear()
    _audit(
        request.actor_id,
        request.actor_role,
        "catalog.material.availability",
        material_id,
        {"copies_available": request.copies_available},
    )
    return material.model_dump(mode="json")


@app.post("/materials/{material_id}/metadata")
async def merge_metadata(material_id: str, request: MetadataMergeRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "catalog:update")
    material = materials.get(material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    material.metadata.update(request.metadata)
    material.updated_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "catalog.material.metadata", material_id)
    return material.model_dump(mode="json")


@app.post("/materials/index/rebuild")
async def rebuild_index(background_tasks: BackgroundTasks) -> dict[str, str]:
    background_tasks.add_task(_rebuild_index)
    return {"status": "accepted", "message": "Index rebuild started"}


@app.get("/materials/index/status")
async def index_status() -> dict[str, Any]:
    return {
        "last_rebuild_at": index_last_rebuild_at,
        "catalog_size": len(materials),
        "capacity_target": settings.catalog_capacity_target,
    }


@app.get("/inventory/summary")
async def inventory_summary() -> dict[str, Any]:
    groups: dict[str, dict[str, int]] = {}
    for material in materials.values():
        bucket = groups.setdefault(
            material.material_type.value,
            {"titles": 0, "copies_total": 0, "copies_available": 0},
        )
        bucket["titles"] += 1
        bucket["copies_total"] += material.copies_total
        bucket["copies_available"] += material.copies_available
    return {"items": groups, "count": len(groups)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

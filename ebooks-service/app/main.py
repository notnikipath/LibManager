from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.libmanager_common import (
    EbookAccessGrantRequest,
    EbookAccessToken,
    EbookAsset,
    EbookReadRequest,
    EbookUploadRequest,
    Role,
    Settings,
    build_audit_event,
    decrypt_text,
    encrypt_text,
    has_permission,
    sign_token,
    verify_token,
)

settings = Settings(service_name="ebooks-service", service_port=8605)
app = FastAPI(title="LibManager EBooks Service", version="1.0.0")

assets: dict[str, EbookAsset] = {}
content_store: dict[str, str] = {}
access_tokens: dict[str, EbookAccessToken] = {}
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
            object_type="ebooks",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _drm_fingerprint(material_id: str, file_name: str, watermark: bool) -> str:
    source = f"{material_id}|{file_name}|{watermark}|{settings.encryption_key}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/ebooks/upload")
async def upload(request: EbookUploadRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "ebooks:upload")

    asset_id = f"EBOOK-{uuid4().hex[:10].upper()}"
    storage_key = f"{settings.minio_bucket}/{request.material_id}/{asset_id}-{request.file_name}"
    fingerprint = _drm_fingerprint(request.material_id, request.file_name, request.drm_watermark)

    asset = EbookAsset(
        asset_id=asset_id,
        material_id=request.material_id,
        title=request.title,
        author=request.author,
        file_name=request.file_name,
        storage_key=storage_key,
        drm_fingerprint=fingerprint,
    )
    assets[asset_id] = asset
    content_store[asset_id] = encrypt_text(request.content_text, settings.encryption_key)

    _audit(request.actor_id, request.actor_role, "ebooks.upload", asset_id, {"storage_key": storage_key})
    return asset.model_dump(mode="json")


@app.get("/ebooks")
async def list_ebooks(material_id: str | None = None) -> dict[str, Any]:
    items = [
        asset.model_dump(mode="json")
        for asset in assets.values()
        if not material_id or asset.material_id == material_id
    ]
    return {"items": items, "count": len(items)}


@app.get("/ebooks/{asset_id}")
async def get_ebook(asset_id: str) -> dict[str, Any]:
    asset = assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="EBook asset not found")
    return asset.model_dump(mode="json")


@app.post("/ebooks/grant-access")
async def grant_access(request: EbookAccessGrantRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "ebooks:grant")
    asset = assets.get(request.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="EBook asset not found")

    token = sign_token(
        {
            "asset_id": request.asset_id,
            "patron_id": request.patron_id,
            "scope": "ebook_read",
        },
        settings.jwt_secret,
        exp_minutes=request.minutes,
    )
    grant = EbookAccessToken(
        token=token,
        asset_id=request.asset_id,
        patron_id=request.patron_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=request.minutes),
    )
    access_tokens[token] = grant
    _audit(
        request.actor_id,
        request.actor_role,
        "ebooks.grant_access",
        request.asset_id,
        {"patron_id": request.patron_id},
    )
    return grant.model_dump(mode="json")


@app.post("/ebooks/read")
async def read_ebook(request: EbookReadRequest) -> dict[str, Any]:
    payload = verify_token(request.token, settings.jwt_secret)
    if payload is None or payload.get("scope") != "ebook_read":
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    asset_id = str(payload.get("asset_id"))
    asset = assets.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="EBook asset not found")

    encrypted = content_store.get(asset_id, "")
    text = decrypt_text(encrypted, settings.encryption_key) if encrypted else ""
    preview = (text[:1200] + "...") if len(text) > 1200 else text
    watermark = f"DRM:{asset.drm_fingerprint[:16]} | PAT:{payload.get('patron_id')}"
    return {
        "asset": asset.model_dump(mode="json"),
        "preview": preview,
        "watermark": watermark,
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

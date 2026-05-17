from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .schemas import Role

PERMISSIONS: dict[Role, set[str]] = {
    Role.READER: {
        "catalog:read",
        "patron:read",
        "circulation:read",
        "circulation:renew",
        "reservation:create",
        "reservation:read",
        "ebooks:read",
    },
    Role.LIBRARIAN: {
        "catalog:read",
        "catalog:create",
        "catalog:update",
        "catalog:availability:update",
        "patron:create",
        "patron:read",
        "patron:update",
        "circulation:checkout",
        "circulation:return",
        "circulation:renew",
        "circulation:read",
        "reservation:create",
        "reservation:update",
        "reservation:read",
        "ebooks:upload",
        "ebooks:grant",
        "ebooks:read",
        "reports:write",
        "reports:read",
        "notification:send",
    },
    Role.ADMIN: {
        "catalog:read",
        "catalog:create",
        "catalog:update",
        "catalog:availability:update",
        "patron:create",
        "patron:read",
        "patron:update",
        "circulation:checkout",
        "circulation:return",
        "circulation:renew",
        "circulation:read",
        "reservation:create",
        "reservation:update",
        "reservation:read",
        "ebooks:upload",
        "ebooks:grant",
        "ebooks:read",
        "reports:write",
        "reports:read",
        "notification:send",
        "audit:read",
        "workflow:execute",
    },
    Role.SYSTEM: {
        "catalog:read",
        "catalog:create",
        "catalog:update",
        "catalog:availability:update",
        "patron:create",
        "patron:read",
        "patron:update",
        "circulation:checkout",
        "circulation:return",
        "circulation:renew",
        "circulation:read",
        "reservation:create",
        "reservation:update",
        "reservation:read",
        "ebooks:upload",
        "ebooks:grant",
        "ebooks:read",
        "reports:write",
        "reports:read",
        "notification:send",
        "workflow:execute",
    },
}


def has_permission(role: Role | str, action: str) -> bool:
    normalized = Role(role) if isinstance(role, str) else role
    return action in PERMISSIONS.get(normalized, set())


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def sign_token(payload: dict[str, Any], secret: str, exp_minutes: int = 180) -> str:
    data = dict(payload)
    data["exp"] = int((datetime.now(UTC) + timedelta(minutes=exp_minutes)).timestamp())
    encoded = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode("utf-8")).decode("ascii")
    signature = hmac.new(_derive_key(secret), encoded.encode("ascii"), hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii")
    return f"{encoded}.{signature_b64}"


def verify_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        payload_b64, signature_b64 = token.split(".", maxsplit=1)
        expected = hmac.new(_derive_key(secret), payload_b64.encode("ascii"), hashlib.sha256).digest()
        received = base64.urlsafe_b64decode(signature_b64.encode("ascii"))
        if not hmac.compare_digest(expected, received):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
            return None
        return payload
    except Exception:
        return None


def encrypt_text(value: str, key: str) -> str:
    if not value:
        return value
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    raw = value.encode("utf-8")
    encrypted = bytes([raw[i] ^ digest[i % len(digest)] for i in range(len(raw))])
    return base64.urlsafe_b64encode(encrypted).decode("ascii")


def decrypt_text(value: str, key: str) -> str:
    if not value:
        return value
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    encrypted = base64.urlsafe_b64decode(value.encode("ascii"))
    raw = bytes([encrypted[i] ^ digest[i % len(digest)] for i in range(len(encrypted))])
    return raw.decode("utf-8")

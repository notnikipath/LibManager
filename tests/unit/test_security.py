from shared.libmanager_common import decrypt_text, encrypt_text, has_permission, sign_token, verify_token
from shared.libmanager_common.schemas import Role


def test_encrypt_roundtrip() -> None:
    secret = "demo-key"
    value = "reader-private-note"
    encrypted = encrypt_text(value, secret)
    assert encrypted != value
    assert decrypt_text(encrypted, secret) == value


def test_token_roundtrip() -> None:
    token = sign_token({"sub": "LIB-001", "role": "librarian"}, "jwt-secret", exp_minutes=5)
    payload = verify_token(token, "jwt-secret")
    assert payload is not None
    assert payload["sub"] == "LIB-001"


def test_permissions() -> None:
    assert has_permission(Role.LIBRARIAN, "catalog:update")
    assert not has_permission(Role.READER, "catalog:update")


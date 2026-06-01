from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


class AuthError(Exception):
    """Raised when credentials or tokens are invalid."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    salt = _b64decode(salt_b64)
    expected = _b64decode(digest_b64)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(candidate, expected)


def create_token(payload: dict[str, Any], secret: str, ttl_seconds: int) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl_seconds
    body_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded_body = _b64encode(body_bytes)
    signature = hmac.new(secret.encode("utf-8"), encoded_body.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_body}.{_b64encode(signature)}"


def verify_token(token: str, secret: str) -> dict[str, Any]:
    try:
        encoded_body, encoded_signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("Malformed token") from exc

    expected_signature = hmac.new(
        secret.encode("utf-8"), encoded_body.encode("ascii"), hashlib.sha256
    ).digest()
    provided_signature = _b64decode(encoded_signature)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise AuthError("Invalid token signature")

    payload = json.loads(_b64decode(encoded_body))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise AuthError("Token expired")
    return payload


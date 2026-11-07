"""Password hashing and signed bearer tokens (stdlib only).

Tokens are HMAC-SHA256 signed JSON payloads with an expiry, so the API stays stateless.
"""
import base64
import hashlib
import hmac
import json
import os
import time


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return salt.hex() + ":" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split(":")
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 120_000)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(claims: dict, secret: str, ttl: int, now: float | None = None) -> str:
    body = dict(claims, exp=int((now or time.time()) + ttl))
    payload = _b64(json.dumps(body, sort_keys=True).encode())
    sig = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return payload + "." + sig


def read_token(token: str, secret: str, now: float | None = None) -> dict | None:
    try:
        payload, sig = token.split(".")
        expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        claims = json.loads(_unb64(payload))
        if claims.get("exp", 0) < (now or time.time()):
            return None
        return claims
    except (ValueError, json.JSONDecodeError):
        return None

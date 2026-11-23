"""
Phase H & L — Security, Authentication, RBAC, Rate Limiting, Upload Safety & Prompt Sanitization.

Key safeguards:
  - Password hashing uses hashlib.scrypt (N=16384, r=8, p=1) with random 16-byte salts
    and constant-time hmac.compare_digest verification.
  - Signed stateless Bearer tokens use HMAC-SHA256 with a server-side secret from
    GEOS_AUTH_SECRET (falling back to an ephemeral in-memory random 32-byte key if unset).
    Tokens are designed to be held in browser JS/React memory only (never localStorage).
  - First-run admin claim flow prevents hardcoded default admin passwords while keeping
    local/preview environments usable without secrets pre-seeded.
  - Multipart photo uploads verify image magic bytes (JPEG, PNG, WebP), enforce a 5 MB cap,
    and confine writes to the dedicated uploads directory via resolved-path boundary checks.
  - Sliding-window in-memory rate limiter protects auth, upload, and AI routes.
  - Prompt-injection sanitizer strips control directives and wraps untrusted text cleanly.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ephemeral process-local signing secret fallback (never persisted to disk or git)
_EPHEMERAL_SECRET = secrets.token_hex(32)

VALID_ROLES = ("admin", "research_analyst", "field_officer", "public_viewer")
SELF_REGISTER_ALLOWED_ROLES = ("public_viewer", "field_officer")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
TOKEN_TTL_SECONDS = 8 * 3600  # 8 hours

ALLOWED_IMAGE_SIGNATURES: dict[str, tuple[str, str]] = {
    "jpeg": ("image/jpeg", ".jpg"),
    "png": ("image/png", ".png"),
    "webp": ("image/webp", ".webp"),
}


def get_auth_secret() -> bytes:
    env_val = os.environ.get("GEOS_AUTH_SECRET", "").strip()
    return (env_val or _EPHEMERAL_SECRET).encode("utf-8")


def hash_password(password: str) -> str:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be between 8 and 128 characters.")
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, n_s, r_s, p_s, salt_hex, dk_hex = stored_hash.split("$")
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(expected),
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(token_part: str) -> bytes:
    padding = "=" * (-len(token_part) % 4)
    return base64.urlsafe_b64decode(token_part + padding)


def create_access_token(user_id: int, username: str, role: str, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    header = {"alg": "HS256", "typ": "GEOS-Bearer"}
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid.uuid4()),
    }
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(get_auth_secret(), signing_input, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64url_encode(sig)}"


def verify_access_token(token: str) -> dict[str, Any] | None:
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        h_b64, p_b64, s_b64 = parts
        signing_input = f"{h_b64}.{p_b64}".encode("ascii")
        expected_sig = hmac.new(get_auth_secret(), signing_input, hashlib.sha256).digest()
        provided_sig = _b64url_decode(s_b64)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if payload.get("role") not in VALID_ROLES:
            return None
        return payload
    except Exception:
        return None


def detect_image_format(data: bytes) -> tuple[str, str] | None:
    """Validates actual image file magic bytes (never trusts client Content-Type or filename)."""
    if len(data) < 12:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return ALLOWED_IMAGE_SIGNATURES["jpeg"]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ALLOWED_IMAGE_SIGNATURES["png"]
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ALLOWED_IMAGE_SIGNATURES["webp"]
    return None


@dataclass
class SavedUploadMetadata:
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str


def save_validated_photo_upload(raw_bytes: bytes, uploads_dir: Path) -> SavedUploadMetadata:
    """
    Validates image bytes, enforces 5 MB size cap, generates a safe UUID filename,
    and writes strictly inside uploads_dir using resolved path boundary enforcement.
    """
    if not raw_bytes:
        raise ValueError("Uploaded photo file is empty.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Uploaded photo exceeds maximum size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    detected = detect_image_format(raw_bytes)
    if detected is None:
        raise ValueError("Unsupported image format. Only genuine JPEG, PNG, or WebP images are accepted.")
    mime_type, ext = detected

    uploads_dir.mkdir(parents=True, exist_ok=True)
    base_resolved = uploads_dir.resolve()
    safe_filename = f"field_{uuid.uuid4().hex}{ext}"
    target_path = (base_resolved / safe_filename).resolve()

    if not str(target_path).startswith(str(base_resolved) + os.sep):
        raise ValueError("Resolved upload path escapes storage directory.")

    target_path.write_bytes(raw_bytes)
    digest = hashlib.sha256(raw_bytes).hexdigest()
    return SavedUploadMetadata(
        filename=safe_filename,
        mime_type=mime_type,
        size_bytes=len(raw_bytes),
        sha256=digest,
    )


def resolve_confined_upload(filename: str, uploads_dir: Path) -> Path | None:
    """Safely resolves a stored upload filename, rejecting traversal attempts."""
    if not re.fullmatch(r"field_[a-f0-9]{32}\.(jpg|png|webp)", filename or ""):
        return None
    base_resolved = uploads_dir.resolve()
    target = (base_resolved / filename).resolve()
    if not str(target).startswith(str(base_resolved) + os.sep):
        return None
    return target if target.is_file() else None


class SlidingWindowRateLimiter:
    """Lightweight in-memory sliding-window rate limiter keyed by client IP + bucket."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        recent = [ts for ts in self._hits[key] if ts > cutoff]
        if len(recent) >= self.max_requests:
            self._hits[key] = recent
            retry_after = max(1, int(self.window_seconds - (now - recent[0])))
            return False, retry_after
        recent.append(now)
        self._hits[key] = recent
        return True, 0


_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"(disregard|override|bypass)\s+(system|safety|scientific)\s+(rules?|instructions?|guardrails?)", re.IGNORECASE),
    re.compile(r"(you\s+are\s+now|act\s+as\s+an?\s+official\s+(ndma|sdma|imd|government))", re.IGNORECASE),
    re.compile(r"(reveal|print|dump|output)\s+(your\s+)?(system\s+prompt|api\s*key|secret|environment)", re.IGNORECASE),
]


def sanitize_user_question(question: str) -> tuple[str, bool]:
    """
    Sanitizes untrusted user text for Gemini assistant prompts and flags potential
    prompt-injection attempts without silently executing them.
    """
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", question).strip()
    cleaned = cleaned[:1000]
    flagged = any(pat.search(cleaned) for pat in _INJECTION_PATTERNS)
    return cleaned, flagged

"""Password hashing and authentication for the single-landlord MVP."""

import base64
import hashlib
import hmac
import secrets

from .config import Settings

DEMO_USERNAME = "chu-tro"
DEMO_PASSWORD = "RoomCareDemo2026!"
ITERATIONS = 600_000


def _parse_password_hash(encoded: str) -> tuple[int, bytes, bytes] | None:
    try:
        algorithm, rounds, salt_b64, digest_b64 = encoded.split("$")
        iterations = int(rounds)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 2_000_000:
            return None
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(digest_b64, validate=True)
        if len(salt) < 16 or len(expected) != 32:
            return None
        return iterations, salt, expected
    except (ValueError, TypeError, AttributeError):
        return None


def is_password_hash_valid(encoded: str) -> bool:
    return _parse_password_hash(encoded) is not None


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("Mật khẩu cần ít nhất 12 ký tự.")
    if len(password) > 256:
        raise ValueError("Mật khẩu quá dài (tối đa 256 ký tự).")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or len(password) > 256:
        return False
    parsed = _parse_password_hash(encoded)
    if parsed is None:
        return False
    iterations, salt, expected = parsed
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(actual, expected)


def authenticate(username: str, password: str, settings: Settings) -> bool:
    """Caller must additionally enforce Store's persistent login rate limit."""
    if not isinstance(username, str) or not isinstance(password, str):
        return False
    if settings.admin_password_hash:
        valid_password = verify_password(password, settings.admin_password_hash)
        valid_user = hmac.compare_digest(username.strip().encode(), settings.admin_username.encode())
        return valid_password and valid_user
    if settings.demo_mode:
        return hmac.compare_digest(username.strip().encode(), DEMO_USERNAME.encode()) and hmac.compare_digest(password.encode(), DEMO_PASSWORD.encode())
    return False

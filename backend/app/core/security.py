import hashlib
import ipaddress
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.exceptions import AuthenticationError, ValidationFailedError

# Initialize Argon2id password hasher (RFC 9106 recommended parameters)
_pwd_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _pwd_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _pwd_hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def encrypt_secret(plain_text: str, key: str) -> str:
    """Encrypt a secret string using Fernet symmetric encryption."""
    f = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str, key: str) -> str:
    """Decrypt a Fernet-encrypted secret string."""
    try:
        f = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AuthenticationError(
            "Failed to decrypt secret: invalid key or corrupted payload."
        ) from exc


def hash_token(token: str) -> str:
    """Compute SHA-256 hash of a token for safe database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def compute_args_hash(arguments: dict[str, Any]) -> str:
    """
    Compute a deterministic SHA-256 hash of a tool call arguments dictionary.
    Ensures approvals are cryptographically bound to the exact parameters displayed.
    """
    canonical_json = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def create_jwt_token(
    payload: dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT token with expiration timestamp."""
    to_encode = payload.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=15))
    to_encode.update({"iat": now, "exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_jwt_token(token: str, secret_key: str, algorithm: str = "HS256") -> dict[str, Any]:
    """Decode and validate a JWT token signature and expiration."""
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid token.") from exc


def get_default_trusted_windows_dirs() -> list[Path]:
    """Return canonical paths for trusted system execution directories on Windows."""
    trusted = []
    # Program Files
    prog_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    trusted.append(Path(prog_files).resolve())

    # Program Files (x86)
    prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    trusted.append(Path(prog_files_x86).resolve())

    # Windows System32
    windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
    system32 = Path(windir) / "System32"
    trusted.append(system32.resolve())

    # Local AppData Programs (e.g. VS Code, user-installed apps)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        trusted.append((Path(local_app_data) / "Programs").resolve())

    return trusted


DISALLOWED_APP_EXTENSIONS = {".cmd", ".bat", ".vbs", ".ps1", ".sh", ".com"}


def validate_open_app_path(
    target_path_str: str,
    allowed_dirs: list[Path] | None = None,
    allowlisted_exact_files: list[Path] | None = None,
) -> Path:
    """
    Validate and pin an executable path for the open_app skill.
    - Resolves symlinks and canonicalizes the path (Path.resolve).
    - Prevents script wrapper launches (e.g., Code.exe directly, not code.cmd).
    - Ensures target is inside a trusted directory or exact allowlisted path.
    - Fully handles paths containing spaces.
    """
    if not target_path_str.strip():
        raise ValidationFailedError("Executable path cannot be empty.")

    target_path = Path(target_path_str).resolve()

    # Block script wrappers and indirect command files
    ext = target_path.suffix.lower()
    if ext in DISALLOWED_APP_EXTENSIONS:
        raise ValidationFailedError(
            f"Direct execution of script wrapper '{ext}' is forbidden. Launch the primary binary (e.g. .exe) directly."
        )

    if not target_path.exists():
        raise ValidationFailedError(f"Target executable does not exist: {target_path}")

    # Check exact allowlisted file paths
    if allowlisted_exact_files:
        for exact in allowlisted_exact_files:
            if target_path == exact.resolve():
                return target_path

    # Check trusted directories
    search_dirs = allowed_dirs if allowed_dirs is not None else get_default_trusted_windows_dirs()
    is_safe = False
    for directory in search_dirs:
        try:
            if target_path.is_relative_to(directory):
                is_safe = True
                break
        except (ValueError, AttributeError):
            # Fallback for older python or cross-drive comparisons
            try:
                target_path.relative_to(directory)
                is_safe = True
                break
            except ValueError:
                continue

    if not is_safe:
        raise ValidationFailedError(
            f"Executable path '{target_path}' is not within any trusted directory and is not allowlisted."
        )

    return target_path


def validate_url(url_str: str, allow_private: bool = False) -> str:
    """
    Validate a URL for web or YouTube browsing.
    - Strictly enforces https:// schema.
    - Blocks loopback and RFC 1918 private IP addresses unless allow_private is explicitly True.
    """
    parsed = urlparse(url_str)
    if parsed.scheme.lower() not in ("https", "http"):
        raise ValidationFailedError("Only HTTP/HTTPS URLs are supported.")

    hostname = parsed.hostname
    if not hostname:
        raise ValidationFailedError("Invalid URL: missing hostname.")

    # Check for localhost / loopback addresses
    if not allow_private:
        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            raise ValidationFailedError("Access to local network/loopback addresses is blocked.")

        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValidationFailedError("Access to private/internal IP addresses is blocked.")
        except ValueError:
            # Valid domain name (e.g., youtube.com, google.com)
            pass

    return url_str

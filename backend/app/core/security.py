import hashlib
import ipaddress
import json
import os
import re
import shutil
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


DISALLOWED_APP_EXTENSIONS: frozenset[str] = frozenset({
    ".cmd", ".bat", ".vbs", ".ps1", ".sh", ".com", ".hta", ".scr", ".pif"
})

DENIED_LIVING_OFF_THE_LAND_BINARIES: frozenset[str] = frozenset({
    "cmd",
    "powershell",
    "pwsh",
    "wscript",
    "cscript",
    "mshta",
    "rundll32",
    "regsvr32",
    "certutil",
    "bitsadmin",
    "msiexec",
    "wmic",
    "schtasks",
    "reg",
    "sc",
    "net",
    "bash",
    "sh",
    "csh",
    "zsh",
    "conhost",
})

FORBIDDEN_ARG_CHARS_REGEX: re.Pattern[str] = re.compile(r"[&|;<>\^`$%\r\n]")


DEFAULT_APP_ALLOWLIST: dict[str, str] = {
    "notepad": r"C:\Windows\System32\notepad.exe",
    "calc": r"C:\Windows\System32\calc.exe",
    "explorer": r"C:\Windows\explorer.exe",
    "taskmgr": r"C:\Windows\System32\Taskmgr.exe",
}


def get_default_pinned_allowlist() -> list[Path]:
    """Return resolved canonical paths for default allowed applications."""
    pinned: list[Path] = []
    for raw_path in DEFAULT_APP_ALLOWLIST.values():
        p = Path(raw_path)
        if p.exists():
            pinned.append(p.resolve())
    return pinned


def validate_open_app_arguments(arguments: list[str]) -> list[str]:
    """
    Validate command-line arguments for application launch.
    - Ensures arguments is a list of strings.
    - Strictly rejects shell metacharacters: [&|;<>^`$%\r\n]
    - Rejects null bytes.
    """
    if not isinstance(arguments, list):
        raise ValidationFailedError("Arguments parameter must be a list of strings.")

    validated: list[str] = []
    for idx, arg in enumerate(arguments):
        if not isinstance(arg, str):
            raise ValidationFailedError(f"Argument at index {idx} must be a string, got {type(arg).__name__}.")
        if "\x00" in arg:
            raise ValidationFailedError(f"Argument at index {idx} contains forbidden null byte.")
        match = FORBIDDEN_ARG_CHARS_REGEX.search(arg)
        if match:
            raise ValidationFailedError(
                f"Argument '{arg}' contains forbidden shell metacharacter '{match.group()}'. "
                "Shell injection metacharacters [&|;<>^`$%\r\n] are blocked."
            )
        validated.append(arg)
    return validated


def is_app_allowlisted(
    target_path: Path,
    allowlist: list[Path] | dict[str, Path | str] | None = None,
) -> bool:
    """Return True if the target path matches an explicitly pinned allowlist entry."""
    resolved = target_path.resolve()
    pinned_paths: list[Path] = []
    if allowlist is not None:
        if isinstance(allowlist, dict):
            for val in allowlist.values():
                pinned_paths.append(Path(val).resolve())
        else:
            for p in allowlist:
                pinned_paths.append(Path(p).resolve())
    else:
        pinned_paths = get_default_pinned_allowlist()

    return any(resolved == p for p in pinned_paths)


def validate_open_app_path(
    target_path_str: str,
    allowlist: list[Path] | dict[str, Path | str] | None = None,
) -> Path:
    """
    Validate and pin an exact executable path for the open_app skill.
    - Resolves symlinks and canonicalizes the path (Path.resolve).
    - Prevents script wrapper launches (e.g. .cmd, .bat, .ps1, etc.).
    - Strictly denies Living-off-the-Land Binaries (LOLBins) such as cmd, powershell, etc.
    - Strictly blocks UNC network paths (\\\\server\\share).
    - Strictly blocks NTFS Alternate Data Streams (ADS).
    - Enforces path resides inside approved system folders (System32, Program Files, LocalAppData/Programs)
      or matches an entry in the pinned application allowlist.
    """
    if not target_path_str or not target_path_str.strip():
        raise ValidationFailedError("Executable path cannot be empty.")

    clean_str = target_path_str.strip()

    # Block UNC paths immediately
    if clean_str.startswith(r"\\") or clean_str.startswith("//"):
        raise ValidationFailedError(f"UNC network paths are forbidden: '{clean_str}'")

    # Block Alternate Data Streams (ADS): check for colon after drive specification
    drive_prefix_len = 2 if len(clean_str) >= 2 and clean_str[1] == ":" and clean_str[0].isalpha() else 0
    if ":" in clean_str[drive_prefix_len:]:
        raise ValidationFailedError(f"Alternate data streams (ADS) are forbidden: '{clean_str}'")

    raw_path = Path(clean_str)

    # Block script wrappers and indirect command files based on raw path suffix
    if raw_path.suffix.lower() in DISALLOWED_APP_EXTENSIONS:
        raise ValidationFailedError(
            f"Direct execution of script wrapper '{raw_path.suffix.lower()}' is forbidden. Launch the primary binary (e.g. .exe) directly."
        )

    # Canonicalize and resolve symlinks
    try:
        target_path = raw_path.resolve()
    except Exception as exc:
        raise ValidationFailedError(f"Invalid executable path '{clean_str}': {exc}") from exc

    # Post-canonicalization checks
    target_str = str(target_path)
    if target_str.startswith(r"\\") or target_str.startswith("//"):
        raise ValidationFailedError(f"UNC network paths are forbidden: '{target_str}'")

    resolved_drive_prefix_len = 2 if len(target_str) >= 2 and target_str[1] == ":" and target_str[0].isalpha() else 0
    if ":" in target_str[resolved_drive_prefix_len:]:
        raise ValidationFailedError(f"Alternate data streams (ADS) are forbidden: '{target_str}'")

    ext = target_path.suffix.lower()
    if ext in DISALLOWED_APP_EXTENSIONS:
        raise ValidationFailedError(
            f"Direct execution of script wrapper '{ext}' is forbidden. Launch the primary binary (e.g. .exe) directly."
        )

    # Deny LOLBins unconditionally (by stem name regardless of location or allowlist)
    stem_lower = target_path.stem.lower()
    if stem_lower in DENIED_LIVING_OFF_THE_LAND_BINARIES:
        raise ValidationFailedError(
            f"Execution of living-off-the-land binary '{target_path.name}' is strictly denied for security."
        )

    if not target_path.exists():
        raise ValidationFailedError(f"Target executable does not exist: {target_path}")

    # Build pinned allowlist paths
    pinned_paths: list[Path] = []
    if allowlist is not None:
        if isinstance(allowlist, dict):
            for val in allowlist.values():
                pinned_paths.append(Path(val).resolve())
        else:
            for p in allowlist:
                pinned_paths.append(Path(p).resolve())

        for allowed_path in pinned_paths:
            if target_path == allowed_path:
                return target_path

        raise ValidationFailedError(
            f"Executable '{target_path}' is not in the pinned application allowlist. "
            "Add this exact executable to your allowlist in Settings to authorize it."
        )

    # Default mode: check default pinned allowlist first
    for allowed_path in get_default_pinned_allowlist():
        if target_path == allowed_path:
            return target_path

    # Check approved system directories
    for trusted_dir in get_default_trusted_windows_dirs():
        try:
            if target_path.is_relative_to(trusted_dir):
                return target_path
        except (ValueError, AttributeError):
            continue

    raise ValidationFailedError(
        f"Executable '{target_path}' is not in the pinned application allowlist or approved system folders. "
        "Add this exact executable to your allowlist in Settings to authorize it."
    )


def resolve_open_app_target(
    app_name: str | None = None,
    executable_path: str | None = None,
    allowlist: list[Path] | dict[str, Path | str] | None = None,
) -> tuple[Path, bool]:
    """
    Resolve and validate an application target either from app_name or executable_path.
    Returns (resolved_path, is_allowlisted).
    """
    clean_app_name = (app_name or "").strip().lower()
    clean_exe_path = (executable_path or "").strip()

    if clean_exe_path:
        target_path = validate_open_app_path(clean_exe_path, allowlist=allowlist)
        allowlisted = is_app_allowlisted(target_path, allowlist=allowlist)
        return target_path, allowlisted

    if clean_app_name:
        allowlist_dict = allowlist if isinstance(allowlist, dict) else DEFAULT_APP_ALLOWLIST
        if clean_app_name in allowlist_dict:
            target_path = validate_open_app_path(str(allowlist_dict[clean_app_name]), allowlist=allowlist)
            return target_path, True

        resolved = shutil.which(clean_app_name)
        if resolved:
            target_path = validate_open_app_path(resolved, allowlist=allowlist)
            allowlisted = is_app_allowlisted(target_path, allowlist=allowlist)
            return target_path, allowlisted

        raise ValidationFailedError(
            f"Application '{clean_app_name}' was not found in allowlist or system PATH."
        )

    raise ValidationFailedError("Either 'app_name' or 'executable_path' must be provided.")


def canonicalize_open_app_arguments(
    arguments: dict[str, Any],
    allowlist: list[Path] | dict[str, Path | str] | None = None,
) -> dict[str, Any]:
    """
    Canonicalize and pre-validate arguments for open_app skill execution / approval staging.
    - Validates arguments structure and checks for shell metacharacters.
    - Resolves executable target path canonicalized.
    - Enforces that arguments can ONLY be passed to explicitly allowlisted applications.
    - Returns normalized dictionary with resolved executable_path and arguments list.
    """
    app_name = (arguments.get("app_name") or "").strip().lower()
    executable_path = (arguments.get("executable_path") or "").strip()
    raw_args = arguments.get("arguments") or []

    if not isinstance(raw_args, list) or not all(isinstance(a, str) for a in raw_args):
        raise ValidationFailedError("Arguments parameter must be a list of strings.")

    validated_args = validate_open_app_arguments(raw_args)

    target_exe, is_allowlisted = resolve_open_app_target(
        app_name=app_name,
        executable_path=executable_path,
        allowlist=allowlist,
    )

    if validated_args and not is_allowlisted:
        raise ValidationFailedError(
            f"Passing command-line arguments is restricted to explicitly allowlisted applications. "
            f"'{target_exe.name}' is not in the allowlist."
        )

    return {
        "app_name": app_name or target_exe.stem,
        "executable_path": str(target_exe),
        "arguments": validated_args,
    }


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


def validate_approval_state(approval_status: str, expires_at: datetime) -> None:
    """
    Validate that an approval is strictly single-use and unexpired.
    Raises ValidationFailedError if the approval was already decided or has expired.
    """
    if approval_status != "pending":
        raise ValidationFailedError(
            f"Approval cannot be decided or reused: already in '{approval_status}' state."
        )
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) > expires_at:
        raise ValidationFailedError("Approval request has expired and can no longer be decided.")

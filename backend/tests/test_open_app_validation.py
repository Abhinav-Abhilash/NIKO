from pathlib import Path

import pytest

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.security import validate_open_app_path, validate_url


def test_open_app_rejects_script_wrappers() -> None:
    # Must launch binaries directly, not wrapper scripts
    for forbidden_file in ["code.cmd", "run.bat", "script.vbs", "tool.ps1"]:
        with pytest.raises(ValidationFailedError, match="script wrapper"):
            validate_open_app_path(forbidden_file)


def test_open_app_rejects_nonexistent_binary() -> None:
    fake_exe = r"C:\Program Files\NonExistentApp123\fake.exe"
    with pytest.raises(ValidationFailedError, match="does not exist"):
        validate_open_app_path(fake_exe)


def test_open_app_rejects_unallowlisted_binary(tmp_path: Path) -> None:
    # Executable created in unallowlisted location
    untrusted_exe = tmp_path / "malicious.exe"
    untrusted_exe.write_text("dummy binary content")

    # Only SafeApp.exe is in the allowlist
    safe_exe = tmp_path / "SafeApp.exe"
    safe_exe.write_text("safe binary")

    with pytest.raises(ValidationFailedError, match="not in the pinned application allowlist"):
        validate_open_app_path(str(untrusted_exe), allowlist=[safe_exe])


def test_open_app_pins_exact_resolved_path(tmp_path: Path) -> None:
    # Simulate an allowlisted executable with spaces
    app_dir = tmp_path / "Program Files" / "Sub Dir"
    app_dir.mkdir(parents=True)
    valid_exe = app_dir / "Code.exe"
    valid_exe.write_text("binary")

    # Validated against explicit allowlist
    resolved = validate_open_app_path(str(valid_exe), allowlist={"vscode": valid_exe})
    assert resolved == valid_exe.resolve()


def test_open_app_allows_explicitly_allowlisted_binary(tmp_path: Path) -> None:
    custom_exe = tmp_path / "CustomTool.exe"
    custom_exe.write_text("binary")

    resolved = validate_open_app_path(
        str(custom_exe),
        allowlist=[custom_exe],
    )
    assert resolved == custom_exe.resolve()


def test_validate_url_allows_https_public_domain() -> None:
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    validated = validate_url(url)
    assert validated == url


def test_validate_url_blocks_localhost_and_private_ips() -> None:
    with pytest.raises(ValidationFailedError, match="blocked"):
        validate_url("http://127.0.0.1:8000/admin")

    with pytest.raises(ValidationFailedError, match="blocked"):
        validate_url("http://localhost:3000")

    with pytest.raises(ValidationFailedError, match="blocked"):
        validate_url("http://192.168.1.10/api")


def test_validate_url_allows_private_ip_with_explicit_setting() -> None:
    url = "http://192.168.1.10:8080/dashboard"
    validated = validate_url(url, allow_private=True)
    assert validated == url

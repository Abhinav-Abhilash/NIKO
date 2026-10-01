from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.security import (
    DENIED_LIVING_OFF_THE_LAND_BINARIES,
    canonicalize_open_app_arguments,
    validate_open_app_arguments,
    validate_open_app_path,
    validate_url,
)
from backend.app.services.skill_service import SkillService
from backend.app.skills.base import SkillContext


def test_open_app_rejects_script_wrappers() -> None:
    # Must launch binaries directly, not wrapper scripts
    for forbidden_file in ["code.cmd", "run.bat", "script.vbs", "tool.ps1", "app.hta", "app.scr", "app.pif"]:
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


def test_open_app_rejects_all_lolbins(tmp_path: Path) -> None:
    """Every living-off-the-land binary must be unconditionally rejected, even if allowlisted."""
    for lolbin in sorted(DENIED_LIVING_OFF_THE_LAND_BINARIES):
        fake_binary = tmp_path / f"{lolbin}.exe"
        fake_binary.write_text("dummy binary content")

        # Rejection via direct path
        with pytest.raises(ValidationFailedError, match="living-off-the-land"):
            validate_open_app_path(str(fake_binary))

        # Rejection even if an attacker attempts to inject into custom allowlist
        with pytest.raises(ValidationFailedError, match="living-off-the-land"):
            validate_open_app_path(str(fake_binary), allowlist=[fake_binary])


def test_open_app_rejects_path_traversal(tmp_path: Path) -> None:
    """Path traversal sequences resolving to unallowlisted or denied binaries are blocked."""
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_exe = outside_dir / "secret.exe"
    secret_exe.write_text("payload")

    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    allowed_exe = allowed_dir / "ok.exe"
    allowed_exe.write_text("ok")

    traversal_path = str(allowed_dir / ".." / "outside" / "secret.exe")
    with pytest.raises(ValidationFailedError, match="not in the pinned application allowlist"):
        validate_open_app_path(traversal_path, allowlist=[allowed_exe])


def test_open_app_rejects_unc_network_paths() -> None:
    """UNC network shares and remote SMB paths are strictly blocked."""
    unc_paths = [
        r"\\192.168.1.100\tools\malicious.exe",
        r"\\attacker-domain.com\share\payload.exe",
        r"\\localhost\c$\Windows\notepad.exe",
        r"//10.0.0.1/share/tool.exe",
    ]
    for unc in unc_paths:
        with pytest.raises(ValidationFailedError, match="UNC network paths are forbidden"):
            validate_open_app_path(unc)


def test_open_app_rejects_alternate_data_streams() -> None:
    """NTFS Alternate Data Streams (ADS) are strictly rejected."""
    ads_paths = [
        r"C:\Windows\System32\notepad.exe:evil.exe",
        r"notepad.exe:hidden_stream",
        r"C:\Program Files\App\app.exe:stream:$DATA",
    ]
    for ads in ads_paths:
        with pytest.raises(ValidationFailedError, match="Alternate data streams"):
            validate_open_app_path(ads)


def test_open_app_arguments_metacharacter_rejection() -> None:
    """Shell metacharacters and control characters in command-line arguments are blocked."""
    forbidden_chars = ["&", "|", ";", "<", ">", "^", "`", "$", "%", "\r", "\n", "\x00"]
    for char in forbidden_chars:
        bad_arg = f"sample{char}arg"
        with pytest.raises(ValidationFailedError, match="forbidden"):
            validate_open_app_arguments([bad_arg])


def test_open_app_arguments_allowed_characters() -> None:
    """Safe, standard command-line flags and parameters pass argument validation."""
    valid_args = ["--profile", "default", "-v", "C:\\docs\\file.txt", "key=value", "/safe"]
    validated = validate_open_app_arguments(valid_args)
    assert validated == valid_args


def test_open_app_arguments_forbidden_for_non_allowlisted_apps(tmp_path: Path) -> None:
    """Passing arguments is restricted strictly to explicitly allowlisted applications."""
    unallowlisted_exe = tmp_path / "Helper.exe"
    unallowlisted_exe.write_text("helper binary")

    # In approved folder mock or custom allowlist
    with patch("backend.app.core.security.get_default_trusted_windows_dirs", return_value=[tmp_path]):
        with pytest.raises(ValidationFailedError, match="restricted to explicitly allowlisted applications"):
            canonicalize_open_app_arguments({
                "executable_path": str(unallowlisted_exe),
                "arguments": ["--run-flag"],
            })


def test_open_app_arguments_allowed_for_allowlisted_apps() -> None:
    """Allowlisted applications like notepad permit validated arguments."""
    canonical = canonicalize_open_app_arguments({
        "app_name": "notepad",
        "arguments": ["my_document.txt"],
    })
    assert canonical["app_name"] == "notepad"
    assert "notepad.exe" in canonical["executable_path"].lower()
    assert canonical["arguments"] == ["my_document.txt"]


def test_open_app_symlink_resolves_and_enforces_security(tmp_path: Path) -> None:
    """Symlinks resolve to canonical target and enforce LOLBin and allowlist rules."""
    malicious_target = tmp_path / "cmd.exe"
    malicious_target.write_text("fake cmd")

    symlink_exe = tmp_path / "SafeAlias.exe"
    try:
        symlink_exe.symlink_to(malicious_target)
    except OSError:
        # Fallback if Windows non-admin privileges prevent actual symlink creation
        with patch.object(Path, "resolve", return_value=malicious_target):
            with pytest.raises(ValidationFailedError, match="living-off-the-land"):
                validate_open_app_path(str(symlink_exe))
            return

    with pytest.raises(ValidationFailedError, match="living-off-the-land"):
        validate_open_app_path(str(symlink_exe))


@pytest.mark.asyncio
async def test_open_app_approval_payload_contains_resolved_path_and_args(
    db_session: AsyncSession,
) -> None:
    """When open_app requires confirmation, approval payload contains resolved absolute path and arguments."""
    service = SkillService(db_session)
    ctx = SkillContext(request_id="req_test_payload", provenance="direct")

    result = await service.execute_skill(
        name="open_app",
        arguments={"app_name": "notepad", "arguments": ["report.txt"]},
        context=ctx,
    )

    assert result.success is False
    assert result.error == "CONFIRMATION_REQUIRED"
    assert result.data is not None

    approval_id = result.data.get("approval_id")
    assert approval_id is not None

    payload_args = result.data.get("arguments", {})
    assert payload_args.get("app_name") == "notepad"
    assert Path(payload_args.get("executable_path", "")).is_absolute()
    assert "notepad.exe" in payload_args.get("executable_path", "").lower()
    assert payload_args.get("arguments") == ["report.txt"]

    # Verify database tool call record also captured the resolved arguments
    approval = await service.approval_service.get_approval(approval_id)
    assert approval is not None
    assert approval.tool_call is not None
    import json
    saved_args = json.loads(approval.tool_call.arguments_json)
    assert saved_args == payload_args


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

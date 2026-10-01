import re
import subprocess
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"AQ\.Ab8[0-9A-Za-z_-]{20,}"),
    re.compile(r"gsk_[0-9A-Za-z]{20,}"),
    re.compile(r"sk-or-v1-[0-9a-f]{20,}"),
]


def test_tracked_files_contain_no_secrets() -> None:
    """Verify that no tracked git files contain real API keys or embedded secrets."""
    repo_root = Path(__file__).resolve().parents[2]

    # Get list of all tracked files
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    for file_rel in tracked_files:
        # Ignore test files that test secret detection pattern matching
        if file_rel in (
            "backend/tests/test_secret_leak_guard.py",
            "backend/tests/test_memory_safety.py",
            "backend/tests/test_memory_service.py",
        ):
            continue

        file_path = repo_root / file_rel
        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern in SECRET_PATTERNS:
            matches = pattern.findall(content)
            assert not matches, (
                f"Secret pattern '{pattern.pattern}' detected in tracked file: {file_rel}!"
            )

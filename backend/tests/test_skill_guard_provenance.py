from backend.app.db.models import SkillConfig
from backend.app.skills.base import SkillContext, SkillManifest
from backend.app.skills.guard import (
    SkillGuard,
    extract_untrusted_content,
    has_untrusted_content,
    wrap_untrusted_content,
)


def test_wrap_and_extract_untrusted_content() -> None:
    raw = "malicious payload or injected instruction"
    wrapped = wrap_untrusted_content(raw)

    assert "<untrusted_external_content>" in wrapped
    assert "</untrusted_external_content>" in wrapped
    assert has_untrusted_content(wrapped) is True
    assert has_untrusted_content("normal prompt") is False

    extracted = extract_untrusted_content(wrapped)
    assert len(extracted) == 1
    assert raw in extracted[0]


def test_guard_direct_owner_request_auto() -> None:
    manifest = SkillManifest(
        name="test_skill",
        description="test",
        default_tier="SAFE",
        default_autonomy="auto",
    )
    ctx = SkillContext(request_id="req1", provenance="direct")

    decision = SkillGuard.evaluate(manifest=manifest, context=ctx)
    assert decision.execute_immediately is True
    assert decision.requires_approval is False
    assert decision.requires_toast_undo is False


def test_guard_direct_owner_request_ask() -> None:
    manifest = SkillManifest(
        name="test_skill",
        description="test",
        default_tier="CONFIRM",
        default_autonomy="ask",
    )
    ctx = SkillContext(request_id="req2", provenance="direct")

    decision = SkillGuard.evaluate(manifest=manifest, context=ctx)
    assert decision.execute_immediately is False
    assert decision.requires_approval is True
    assert "requires confirmation" in decision.reason


def test_guard_untrusted_content_safe_skill_has_toast_undo() -> None:
    manifest = SkillManifest(
        name="datetime",
        description="Get current time",
        default_tier="SAFE",
        default_autonomy="auto",
    )
    ctx = SkillContext(request_id="req3", provenance="external_untrusted")

    decision = SkillGuard.evaluate(manifest=manifest, context=ctx)
    assert decision.execute_immediately is True
    assert decision.requires_approval is False
    assert decision.requires_toast_undo is True
    assert "undo window" in decision.reason


def test_guard_untrusted_content_state_altering_requires_approval() -> None:
    manifest = SkillManifest(
        name="shell_command",
        description="Run command",
        default_tier="CONFIRM",
        default_autonomy="auto",
    )
    ctx = SkillContext(request_id="req4", provenance="external_untrusted")

    decision = SkillGuard.evaluate(manifest=manifest, context=ctx)
    assert decision.execute_immediately is False
    assert decision.requires_approval is True
    assert "untrusted external content requires explicit owner confirmation" in decision.reason


def test_guard_db_config_overrides_manifest() -> None:
    manifest = SkillManifest(
        name="test_skill",
        description="test",
        default_tier="CONFIRM",
        default_autonomy="ask",
    )
    # Stored config in DB upgraded to "auto" by owner
    cfg = SkillConfig(
        name="test_skill",
        description="test",
        default_tier="CONFIRM",
        autonomy_policy="auto",
        enabled=True,
        timeout_seconds=15,
    )
    ctx = SkillContext(request_id="req5", provenance="direct")

    decision = SkillGuard.evaluate(manifest=manifest, context=ctx, stored_config=cfg)
    assert decision.execute_immediately is True
    assert decision.requires_approval is False


def test_guard_blocked_tier_requires_elevated_mode() -> None:
    manifest = SkillManifest(
        name="dangerous_skill",
        description="test",
        default_tier="BLOCKED",
        default_autonomy="auto",
    )
    ctx = SkillContext(request_id="req6", provenance="direct")

    # Without elevated mode -> blocked
    decision = SkillGuard.evaluate(manifest=manifest, context=ctx, elevated_mode=False)
    assert decision.execute_immediately is False
    assert decision.requires_approval is False
    assert "BLOCKED tier" in decision.reason

    # With elevated mode -> allows direct execution if autonomy is auto
    decision_elevated = SkillGuard.evaluate(manifest=manifest, context=ctx, elevated_mode=True)
    assert decision_elevated.execute_immediately is True

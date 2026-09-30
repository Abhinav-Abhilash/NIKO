import re

from pydantic import BaseModel, Field

from backend.app.core.logging import get_logger
from backend.app.db.models import SkillConfig
from backend.app.skills.base import AutonomyPolicy, SkillContext, SkillManifest, SkillTier

logger = get_logger("skill_guard")

UNTRUSTED_CONTENT_TAG_START = "<untrusted_external_content>"
UNTRUSTED_CONTENT_TAG_END = "</untrusted_external_content>"
_UNTRUSTED_REGEX = re.compile(
    rf"{re.escape(UNTRUSTED_CONTENT_TAG_START)}(.*?){re.escape(UNTRUSTED_CONTENT_TAG_END)}",
    re.DOTALL,
)


def wrap_untrusted_content(content: str) -> str:
    """Enclose untrusted external text (web searches, downloads, screen OCR) in containment delimiters."""
    return f"{UNTRUSTED_CONTENT_TAG_START}\n{content}\n{UNTRUSTED_CONTENT_TAG_END}"


def extract_untrusted_content(text: str) -> list[str]:
    """Extract all untrusted external content blocks from a prompt or string."""
    return _UNTRUSTED_REGEX.findall(text)


def has_untrusted_content(text: str) -> bool:
    """Return True if the text contains untrusted external content delimiters."""
    return bool(_UNTRUSTED_REGEX.search(text))


class GuardDecision(BaseModel):
    """Evaluation result for whether a skill may execute immediately or requires human confirmation."""

    execute_immediately: bool = Field(..., description="Whether the executor may immediately run the skill")
    requires_approval: bool = Field(default=False, description="Whether human approval is required first")
    requires_toast_undo: bool = Field(
        default=False,
        description="Whether a non-blocking toast notification with 5-second undo is required",
    )
    effective_tier: SkillTier
    effective_autonomy: AutonomyPolicy
    reason: str


class SkillGuard:
    """
    Evaluates skill executions against autonomy policies and provenance tracking.
    Enforces that direct owner requests run with maximum chosen autonomy, while
    actions downstream of untrusted external content receive appropriate safety checks.
    """

    @staticmethod
    def evaluate(
        manifest: SkillManifest,
        context: SkillContext,
        stored_config: SkillConfig | None = None,
        elevated_mode: bool = False,
    ) -> GuardDecision:
        # Determine effective tier and autonomy policy (allowing DB settings and context overrides)
        effective_tier: SkillTier = (
            stored_config.default_tier  # type: ignore[assignment]
            if stored_config
            else manifest.default_tier
        )

        effective_autonomy: AutonomyPolicy = context.autonomy_override or (
            stored_config.autonomy_policy  # type: ignore[assignment]
            if stored_config
            else manifest.default_autonomy
        )

        # 1. Blocked tier check: BLOCKED tier skills are strictly forbidden and non-runnable under any mode
        if effective_tier == "BLOCKED":
            logger.warning(
                "Skill strictly blocked by BLOCKED tier",
                skill_name=manifest.name,
                provenance=context.provenance,
            )
            return GuardDecision(
                execute_immediately=False,
                requires_approval=False,
                effective_tier=effective_tier,
                effective_autonomy=effective_autonomy,
                reason=f"Skill '{manifest.name}' is in BLOCKED tier and cannot be executed.",
            )

        # 2. Elevated mode / explicitly approved: authorized for immediate execution
        if elevated_mode:
            return GuardDecision(
                execute_immediately=True,
                requires_approval=False,
                requires_toast_undo=False,
                effective_tier=effective_tier,
                effective_autonomy=effective_autonomy,
                reason="Execution authorized via elevated owner mode / user approval.",
            )

        # 3. Provenance Rule: Actions proposed after reading untrusted external data
        if context.provenance == "external_untrusted":
            logger.info(
                "Evaluating external untrusted action",
                skill_name=manifest.name,
                tier=effective_tier,
                autonomy=effective_autonomy,
            )
            # If safe and autonomous, execute with non-blocking toast notification & undo window
            if effective_tier == "SAFE" and effective_autonomy in ("auto", "auto+log"):
                return GuardDecision(
                    execute_immediately=True,
                    requires_approval=False,
                    requires_toast_undo=True,
                    effective_tier=effective_tier,
                    effective_autonomy=effective_autonomy,
                    reason="Proposed downstream of untrusted external content. Executing with 5-second undo window.",
                )
            # If state-altering (CONFIRM/BLOCKED) or policy is ask, require explicit confirmation
            return GuardDecision(
                execute_immediately=False,
                requires_approval=True,
                requires_toast_undo=False,
                effective_tier=effective_tier,
                effective_autonomy=effective_autonomy,
                reason="Action proposed by untrusted external content requires explicit owner confirmation.",
            )

        # 3. Direct owner requests: Execute according to owner's chosen autonomy
        if effective_autonomy in ("auto", "auto+log"):
            return GuardDecision(
                execute_immediately=True,
                requires_approval=False,
                requires_toast_undo=False,
                effective_tier=effective_tier,
                effective_autonomy=effective_autonomy,
                reason="Direct owner request authorized for immediate autonomous execution.",
            )

        # Default fallback: requires confirmation ('ask' policy)
        return GuardDecision(
            execute_immediately=False,
            requires_approval=True,
            requires_toast_undo=False,
            effective_tier=effective_tier,
            effective_autonomy=effective_autonomy,
            reason=f"Skill '{manifest.name}' requires confirmation under autonomy policy '{effective_autonomy}'.",
        )

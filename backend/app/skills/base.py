from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

SkillTier = Literal["SAFE", "CONFIRM", "BLOCKED"]
AutonomyPolicy = Literal["ask", "auto", "auto+log"]
ProvenanceType = Literal["direct", "external_untrusted"]


class SkillManifest(BaseModel):
    """Declarative specification for a skill's parameters, timeouts, and default autonomy."""

    name: str = Field(..., description="Unique skill identifier, e.g. 'datetime', 'system_stats'")
    description: str = Field(..., description="Human- and LLM-readable summary of capability")
    default_tier: SkillTier = Field(
        default="SAFE",
        description="Default permission tier (SAFE=read-only, CONFIRM=state-altering, BLOCKED=elevated-only)",
    )
    default_autonomy: AutonomyPolicy = Field(
        default="auto",
        description="Default autonomy behavior (ask=prompt owner, auto=execute immediately, auto+log=execute with non-blocking toast)",
    )
    timeout_seconds: int = Field(default=15, ge=1, le=300, description="Execution timeout barrier")
    parameters_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema describing expected tool arguments",
    )


class SkillResult(BaseModel):
    """Structured response from skill execution."""

    success: bool
    data: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


class SkillContext(BaseModel):
    """Invocation context carrying request tracing, actor identity, and provenance."""

    request_id: str
    user_id: str | None = None
    provenance: ProvenanceType = Field(
        default="direct",
        description="Origin of trigger: 'direct' from owner vs 'external_untrusted' from web/file/OCR",
    )
    autonomy_override: AutonomyPolicy | None = None


class BaseSkill(ABC):
    """Abstract base class implemented by all built-in and dynamic NIKO skills."""

    @property
    @abstractmethod
    def manifest(self) -> SkillManifest:
        """Return the static declarative manifest for this skill."""
        ...

    @abstractmethod
    async def execute(self, arguments: dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with provided validated arguments and invocation context."""
        ...


class SkillExecutor(ABC):
    """
    Abstract interface for executing skills.
    Abstracts all PC-controlling automation behind an executor interface so a
    remote agent or sandboxed container can replace it seamlessly.
    """

    @abstractmethod
    async def execute(
        self,
        skill: BaseSkill,
        arguments: dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """Execute the skill under enforcement of timeouts, isolation, and process supervision."""
        ...

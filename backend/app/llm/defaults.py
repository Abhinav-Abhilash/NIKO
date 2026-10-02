from backend.app.llm.types import ModelRolesConfig, ProviderRateLimit, RoleModelTarget

# Verified Free-Tier Rate Limits per (provider, model)
# Source: "AI Studio rate-limit page, read by owner, 2026-10-02" and Groq/OpenRouter documentation
VERIFIED_RATE_LIMITS: dict[tuple[str, str], ProviderRateLimit] = {
    # Gemini 3.x Series (Separate pools per model in AI Studio)
    ("gemini", "gemini-3.5-flash-lite"): ProviderRateLimit(
        rpm=15,
        rpd=500,
        tpm=250_000,
        tpd=0,
        source="AI Studio rate-limit page, read by owner, 2026-10-02",
    ),
    ("gemini", "gemini-3.8-flash"): ProviderRateLimit(
        rpm=5,
        rpd=20,
        tpm=250_000,
        tpd=0,
        source="AI Studio rate-limit page, read by owner, 2026-10-02",
    ),
    ("gemini", "gemini-3.7-flash"): ProviderRateLimit(
        rpm=5,
        rpd=20,
        tpm=250_000,
        tpd=0,
        source="AI Studio rate-limit page, read by owner, 2026-10-02",
    ),
    ("gemini", "gemini-3.5-flash"): ProviderRateLimit(
        rpm=5,
        rpd=20,
        tpm=250_000,
        tpd=0,
        source="AI Studio rate-limit page, read by owner, 2026-10-02",
    ),
    ("gemini", "gemini-flash-lite-latest"): ProviderRateLimit(
        rpm=15,
        rpd=500,
        tpm=250_000,
        tpd=0,
        source="AI Studio rate-limit page, read by owner, 2026-10-02",
    ),
    ("gemini", "gemini-flash-latest"): ProviderRateLimit(
        rpm=5,
        rpd=20,
        tpm=250_000,
        tpd=0,
        source="AI Studio rate-limit page, read by owner, 2026-10-02",
    ),
    # Dead Gemini 2.x Models
    ("gemini", "gemini-2.0-flash"): ProviderRateLimit(
        rpm=0,
        rpd=0,
        tpm=0,
        tpd=0,
        source="AI Studio rate-limit page, read by owner, 2026-10-02 (dead)",
    ),
    ("gemini", "gemini-2.0-flash-lite"): ProviderRateLimit(
        rpm=0,
        rpd=0,
        tpm=0,
        tpd=0,
        source="AI Studio rate-limit page, read by owner, 2026-10-02 (dead)",
    ),
    # Groq (Verified active production endpoints)
    ("groq", "openai/gpt-oss-20b"): ProviderRateLimit(
        rpm=30,
        rpd=1000,
        tpm=8000,
        tpd=200_000,
        source="https://console.groq.com/docs/rate-limits (Checked: 2026-10-02)",
    ),
    ("groq", "openai/gpt-oss-120b"): ProviderRateLimit(
        rpm=30,
        rpd=1000,
        tpm=8000,
        tpd=200_000,
        source="https://console.groq.com/docs/rate-limits (Checked: 2026-10-02)",
    ),
    # OpenRouter
    ("openrouter", "openrouter/free"): ProviderRateLimit(
        rpm=20,
        rpd=200,
        tpm=10_000,
        tpd=0,
        source="https://openrouter.ai/models/openrouter/free (Checked: 2026-10-02)",
    ),
    ("openrouter", "cohere/north-mini-code:free"): ProviderRateLimit(
        rpm=20,
        rpd=200,
        tpm=10_000,
        tpd=0,
        source="https://openrouter.ai/models (Checked: 2026-10-02)",
    ),
}

# Conservative fallback limits if an unlisted model is specified
DEFAULT_PROVIDER_LIMITS: dict[str, ProviderRateLimit] = {
    "gemini": ProviderRateLimit(
        rpm=15, rpd=500, tpm=250_000, tpd=0, source="AI Studio rate-limit page, read by owner, 2026-10-02"
    ),
    "groq": ProviderRateLimit(
        rpm=30, rpd=1000, tpm=8000, tpd=200_000, source="Groq Console Default"
    ),
    "openrouter": ProviderRateLimit(
        rpm=20, rpd=200, tpm=10_000, tpd=0, source="OpenRouter Free Default"
    ),
}


def get_default_roles_config() -> ModelRolesConfig:
    return ModelRolesConfig(
        light=[
            RoleModelTarget(
                provider="groq",
                model="openai/gpt-oss-20b",
                max_output_tokens=1024,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.5-flash-lite",
                max_output_tokens=1024,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="openrouter",
                model="openrouter/free",
                max_output_tokens=1024,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-flash-lite-latest",
                max_output_tokens=1024,
                reasoning_effort="low",
            ),
        ],
        chat=[
            RoleModelTarget(
                provider="groq",
                model="openai/gpt-oss-20b",
                max_output_tokens=4096,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.5-flash-lite",
                max_output_tokens=4096,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="openrouter",
                model="openrouter/free",
                max_output_tokens=4096,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-flash-lite-latest",
                max_output_tokens=4096,
                reasoning_effort="low",
            ),
        ],
        code=[
            # Short code goes to Groq 120b; long code/fallback enters Flash ladder
            RoleModelTarget(
                provider="groq",
                model="openai/gpt-oss-120b",
                max_output_tokens=8192,
                reasoning_effort="default",
            ),
            # Flash Ladder: 3.8 -> 3.7 -> 3.5 Flash
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.8-flash",
                max_output_tokens=8192,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.7-flash",
                max_output_tokens=8192,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.5-flash",
                max_output_tokens=8192,
                reasoning_effort="default",
            ),
            # Then Flash-Lite
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.5-flash-lite",
                max_output_tokens=8192,
                reasoning_effort="low",
            ),
            # Then OpenRouter coding model, then free router
            RoleModelTarget(
                provider="openrouter",
                model="cohere/north-mini-code:free",
                max_output_tokens=8192,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="openrouter",
                model="openrouter/free",
                max_output_tokens=4096,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-flash-latest",
                max_output_tokens=8192,
                reasoning_effort="default",
            ),
        ],
        search=[
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.5-flash-lite",
                max_output_tokens=2048,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.8-flash",
                max_output_tokens=2048,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.7-flash",
                max_output_tokens=2048,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.5-flash",
                max_output_tokens=2048,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-flash-lite-latest",
                max_output_tokens=2048,
                reasoning_effort="low",
            ),
        ],
    )

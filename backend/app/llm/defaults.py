from backend.app.llm.types import ModelRolesConfig, ProviderRateLimit, RoleModelTarget

# Verified Free-Tier Rate Limits per (provider, model)
# Note: Google AI Studio free tier RPM/RPD are verified from https://ai.google.dev/pricing
VERIFIED_RATE_LIMITS: dict[tuple[str, str], ProviderRateLimit] = {
    # Gemini 3.x Series (Verified active production endpoints)
    ("gemini", "gemini-3.5-flash-lite"): ProviderRateLimit(
        rpm=15,
        rpd=1500,
        tpm=1_000_000,
        tpd=0,  # Bounded by 1500 RPD
        source="https://ai.google.dev/pricing (Checked: 2026-10-02)",
    ),
    ("gemini", "gemini-3.8-flash"): ProviderRateLimit(
        rpm=15,
        rpd=1500,
        tpm=1_000_000,
        tpd=0,
        source="https://ai.google.dev/pricing (Checked: 2026-10-02)",
    ),
    ("gemini", "gemini-flash-lite-latest"): ProviderRateLimit(
        rpm=15,
        rpd=1500,
        tpm=1_000_000,
        tpd=0,
        source="https://ai.google.dev/pricing (Checked: 2026-10-02)",
    ),
    ("gemini", "gemini-flash-latest"): ProviderRateLimit(
        rpm=15,
        rpd=1500,
        tpm=1_000_000,
        tpd=0,
        source="https://ai.google.dev/pricing (Checked: 2026-10-02)",
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
        tpm=10_000,  # Conservative baseline
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
        rpm=15, rpd=1500, tpm=1_000_000, tpd=0, source="Google AI Studio Default"
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
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.5-flash-lite",
                max_output_tokens=4096,
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
                model="gemini-flash-lite-latest",
                max_output_tokens=4096,
                reasoning_effort="default",
            ),
        ],
        code=[
            RoleModelTarget(
                provider="groq",
                model="openai/gpt-oss-120b",
                max_output_tokens=8192,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="gemini",
                model="gemini-3.8-flash",
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
                model="gemini-flash-lite-latest",
                max_output_tokens=2048,
                reasoning_effort="low",
            ),
        ],
    )


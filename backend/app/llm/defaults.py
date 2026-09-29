from backend.app.llm.types import ModelRolesConfig, ProviderRateLimit, RoleModelTarget

# Verified Free-Tier Rate Limits per (provider, model)
VERIFIED_RATE_LIMITS: dict[tuple[str, str], ProviderRateLimit] = {
    # Gemini
    ("gemini", "gemini-2.0-flash-lite"): ProviderRateLimit(
        rpm=15,
        rpd=1500,
        tpm=1_000_000,
        tpd=0,  # Bounded by 1500 RPD
        source="https://ai.google.dev/pricing",
    ),
    ("gemini", "gemini-2.0-flash"): ProviderRateLimit(
        rpm=15,
        rpd=1500,
        tpm=1_000_000,
        tpd=0,
        source="https://ai.google.dev/pricing",
    ),
    ("gemini", "gemini-2.5-flash"): ProviderRateLimit(
        rpm=15,
        rpd=1500,
        tpm=1_000_000,
        tpd=0,
        source="https://ai.google.dev/pricing",
    ),
    # Groq
    ("groq", "openai/gpt-oss-20b"): ProviderRateLimit(
        rpm=30,
        rpd=1000,
        tpm=8000,
        tpd=200_000,
        source="https://console.groq.com/docs/rate-limits",
    ),
    ("groq", "openai/gpt-oss-120b"): ProviderRateLimit(
        rpm=30,
        rpd=1000,
        tpm=8000,
        tpd=200_000,
        source="https://console.groq.com/docs/rate-limits",
    ),
    ("groq", "llama-3.1-8b-instant"): ProviderRateLimit(
        rpm=30,
        rpd=14_400,
        tpm=6000,
        tpd=500_000,
        source="https://console.groq.com/docs/rate-limits",
    ),
    ("groq", "llama-3.3-70b-versatile"): ProviderRateLimit(
        rpm=30,
        rpd=1000,
        tpm=12_000,
        tpd=100_000,
        source="https://console.groq.com/docs/rate-limits",
    ),
    # OpenRouter
    ("openrouter", "openrouter/free"): ProviderRateLimit(
        rpm=20,
        rpd=200,
        tpm=10_000,  # Conservative baseline
        tpd=0,
        source="https://openrouter.ai/models/openrouter/free",
    ),
    ("openrouter", "qwen/qwen-2.5-coder-32b-instruct:free"): ProviderRateLimit(
        rpm=20,
        rpd=200,
        tpm=10_000,
        tpd=0,
        source="https://openrouter.ai/models",
    ),
}

# Conservative fallback limits if an unlisted model is specified
DEFAULT_PROVIDER_LIMITS: dict[str, ProviderRateLimit] = {
    "gemini": ProviderRateLimit(
        rpm=15, rpd=1500, tpm=1_000_000, tpd=0, source="Google AI Studio Default"
    ),
    "groq": ProviderRateLimit(
        rpm=30, rpd=1000, tpm=6000, tpd=100_000, source="Groq Console Default"
    ),
    "openrouter": ProviderRateLimit(
        rpm=20, rpd=200, tpm=8000, tpd=0, source="OpenRouter Free Default"
    ),
}


def get_default_roles_config() -> ModelRolesConfig:
    return ModelRolesConfig(
        light=[
            RoleModelTarget(
                provider="gemini",
                model="gemini-2.0-flash-lite",
                max_output_tokens=1024,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="groq",
                model="openai/gpt-oss-20b",
                max_output_tokens=1024,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="groq",
                model="llama-3.1-8b-instant",
                max_output_tokens=1024,
                reasoning_effort="low",
            ),
        ],
        chat=[
            RoleModelTarget(
                provider="gemini",
                model="gemini-2.0-flash",
                max_output_tokens=4096,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="groq",
                model="openai/gpt-oss-120b",
                max_output_tokens=4096,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="groq",
                model="llama-3.3-70b-versatile",
                max_output_tokens=4096,
                reasoning_effort="default",
            ),
        ],
        code=[
            RoleModelTarget(
                provider="gemini",
                model="gemini-2.0-flash",
                max_output_tokens=8192,
                reasoning_effort="default",
            ),
            RoleModelTarget(
                provider="groq",
                model="openai/gpt-oss-120b",
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
                provider="openrouter",
                model="qwen/qwen-2.5-coder-32b-instruct:free",
                max_output_tokens=4096,
                reasoning_effort="default",
            ),
        ],
        search=[
            RoleModelTarget(
                provider="gemini",
                model="gemini-2.0-flash-lite",
                max_output_tokens=2048,
                reasoning_effort="low",
            ),
            RoleModelTarget(
                provider="groq",
                model="openai/gpt-oss-20b",
                max_output_tokens=2048,
                reasoning_effort="low",
            ),
        ],
    )

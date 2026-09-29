class LLMException(Exception):
    """Base exception for all LLM operations."""
    pass


class ProviderRateLimitError(LLMException):
    """Upstream 429 rate limit exceeded."""

    def __init__(self, provider: str, model: str, retry_after: float = 60.0, message: str | None = None):
        self.provider = provider
        self.model = model
        self.retry_after = retry_after
        super().__init__(message or f"Rate limit exceeded for {provider}/{model}. Backoff: {retry_after}s")


class ProviderModelNotFoundError(LLMException):
    """Upstream 404 model not found or disappeared."""

    def __init__(self, provider: str, model: str, message: str | None = None):
        self.provider = provider
        self.model = model
        super().__init__(message or f"Model {model} not found on provider {provider} (404/retired)")


class ProviderAuthError(LLMException):
    """Upstream 401/403 authentication error."""

    def __init__(self, provider: str, message: str | None = None):
        self.provider = provider
        super().__init__(message or f"Authentication failed for provider {provider}")


class AllProvidersExhaustedError(LLMException):
    """All providers/models in the role sequence are exhausted or in cooldown."""

    def __init__(self, role: str, attempts: list[dict[str, str]]):
        self.role = role
        self.attempts = attempts
        super().__init__(f"All providers exhausted for role '{role}'. Attempts: {attempts}")

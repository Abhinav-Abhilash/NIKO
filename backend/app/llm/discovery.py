import asyncio
from typing import Any
import httpx

from backend.app.core.logging import get_logger

logger = get_logger("niko.llm.discovery")


class ModelDiscoveryService:
    """
    Discovers live available models from Gemini, Groq, and OpenRouter endpoints.
    Catches and logs warnings if any endpoint 404s, times out, or fails,
    ensuring startup and runtime are never blocked.
    """

    def __init__(self) -> None:
        self._discovered: dict[str, set[str]] = {
            "gemini": set(),
            "groq": set(),
            "openrouter": set(),
        }
        self._provider_checked: set[str] = set()

    def is_model_available(self, provider: str, model: str) -> bool:
        prov = provider.lower()
        if prov not in self._provider_checked:
            # Not yet checked, permit execution so startup isn't blocked
            return True
        known = self._discovered.get(prov, set())
        if not known:
            # Endpoint returned empty or failed to connect, allow fallback attempt
            return True
        return model.lower() in known or model in known

    def mark_model_missing(self, provider: str, model: str, reason: str = "404 or disappeared") -> None:
        prov = provider.lower()
        if prov in self._discovered and model.lower() in self._discovered[prov]:
            self._discovered[prov].discard(model.lower())
        logger.warning(
            "Model marked unavailable/missing",
            provider=provider,
            model=model,
            reason=reason,
        )

    async def discover_gemini(self, api_key: str | None) -> list[str]:
        if not api_key:
            return []
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    models = [
                        m["name"].replace("models/", "").lower()
                        for m in data.get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    self._discovered["gemini"] = set(models)
                    self._provider_checked.add("gemini")
                    logger.info("Discovered Gemini models", count=len(models))
                    return models
                else:
                    logger.warning(
                        "Gemini model discovery endpoint returned non-200",
                        status_code=res.status_code,
                        response=res.text[:200],
                    )
        except Exception as e:
            logger.warning("Failed to discover Gemini models", error=str(e))
        self._provider_checked.add("gemini")
        return []

    async def discover_groq(self, api_key: str | None) -> list[str]:
        if not api_key:
            return []
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    models = [m["id"].lower() for m in data.get("data", []) if m.get("active", True)]
                    self._discovered["groq"] = set(models)
                    self._provider_checked.add("groq")
                    logger.info("Discovered Groq models", count=len(models))
                    return models
                else:
                    logger.warning(
                        "Groq model discovery endpoint returned non-200",
                        status_code=res.status_code,
                        response=res.text[:200],
                    )
        except Exception as e:
            logger.warning("Failed to discover Groq models", error=str(e))
        self._provider_checked.add("groq")
        return []

    async def discover_openrouter(self, api_key: str | None = None) -> list[str]:
        url = "https://openrouter.ai/api/v1/models"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    # Filter for free models with tool support or free coding models
                    free_models: list[str] = ["openrouter/free"]
                    for m in data.get("data", []):
                        m_id = m.get("id", "").lower()
                        pricing = m.get("pricing", {})
                        is_free = (
                            ":free" in m_id
                            or (str(pricing.get("prompt", "1")) == "0" and str(pricing.get("completion", "1")) == "0")
                        )
                        supported_params = m.get("supported_parameters", [])
                        has_tools = "tools" in supported_params or ":free" in m_id
                        if is_free and has_tools:
                            free_models.append(m_id)
                    self._discovered["openrouter"] = set(free_models)
                    self._provider_checked.add("openrouter")
                    logger.info("Discovered OpenRouter free models", count=len(free_models))
                    return free_models
                else:
                    logger.warning(
                        "OpenRouter model discovery endpoint returned non-200",
                        status_code=res.status_code,
                        response=res.text[:200],
                    )
        except Exception as e:
            logger.warning("Failed to discover OpenRouter models", error=str(e))
        self._discovered["openrouter"] = {"openrouter/free"}
        self._provider_checked.add("openrouter")
        return ["openrouter/free"]

    async def refresh_all(self, provider_keys: dict[str, str]) -> dict[str, list[str]]:
        tasks = [
            self.discover_gemini(provider_keys.get("gemini")),
            self.discover_groq(provider_keys.get("groq")),
            self.discover_openrouter(provider_keys.get("openrouter")),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            "gemini": list(self._discovered.get("gemini", set())),
            "groq": list(self._discovered.get("groq", set())),
            "openrouter": list(self._discovered.get("openrouter", set())),
        }

    def get_discovered_summary(self) -> dict[str, list[str]]:
        return {k: sorted(list(v)) for k, v in self._discovered.items()}


# Global discovery instance
model_discovery = ModelDiscoveryService()

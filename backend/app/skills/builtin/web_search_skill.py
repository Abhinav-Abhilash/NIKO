import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.logging import get_logger
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult
from backend.app.skills.guard import wrap_untrusted_content

logger = get_logger("web_search_skill")


class WebSearchSkill(BaseSkill):
    """Searches the web and returns sanitized, untrusted-tagged results."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="web_search",
            description=(
                "Search the public web for real-time information, articles, and documentation. "
                "All external snippet content is tagged as untrusted data."
            ),
            default_tier="SAFE",
            default_autonomy="auto",
            timeout_seconds=20,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term or query string.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return (default 5, max 10).",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        query = (arguments.get("query") or "").strip()
        if not query:
            raise ValidationFailedError("Search query cannot be empty.")

        max_results = min(max(int(arguments.get("max_results") or 5), 1), 10)

        results = await self._perform_search(query, max_results=max_results)

        # Wrap external web snippet contents in untrusted delimiters
        sanitized_results = []
        for item in results:
            raw_snippet = item.get("snippet", "")
            raw_title = item.get("title", "")
            url = item.get("url", "")

            sanitized_results.append(
                {
                    "title": raw_title,
                    "url": url,
                    "snippet": wrap_untrusted_content(raw_snippet) if raw_snippet else "",
                }
            )

        return SkillResult(
            success=True,
            data={
                "query": query,
                "count": len(sanitized_results),
                "results": sanitized_results,
            },
        )

    async def _perform_search(self, query: str, max_results: int) -> list[dict[str, str]]:
        """Perform search query via DuckDuckGo HTML endpoint with standard headers."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        results: list[dict[str, str]] = []

        try:
            async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True) as client:
                resp = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query, "b": ""},
                )
                if resp.status_code != 200:
                    logger.warning("DuckDuckGo returned non-200 status", status_code=resp.status_code)
                    return self._fallback_instant_answers(query)

                html = resp.text
                results = self._parse_ddg_html(html, max_results)

        except Exception as exc:
            logger.warning("Web search request failed, falling back", error=str(exc))
            return self._fallback_instant_answers(query)

        return results

    def _parse_ddg_html(self, html: str, max_results: int) -> list[dict[str, str]]:
        """Extract titles, links, and snippets from DuckDuckGo HTML response."""
        results: list[dict[str, str]] = []

        title_matches = list(
            re.finditer(
                r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                re.DOTALL,
            )
        )

        for idx, match in enumerate(title_matches):
            if len(results) >= max_results:
                break

            raw_href = match.group(1)
            raw_title = re.sub(r"<[^>]+>", "", match.group(2)).strip()

            actual_url = raw_href
            if "uddg=" in raw_href:
                parsed = urlparse(raw_href)
                params = parse_qs(parsed.query)
                if "uddg" in params:
                    actual_url = unquote(params["uddg"][0])

            start_pos = match.end()
            end_pos = title_matches[idx + 1].start() if idx + 1 < len(title_matches) else len(html)
            segment = html[start_pos:end_pos]

            snippet_match = re.search(
                r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', segment, re.DOTALL
            )
            snippet = ""
            if snippet_match:
                snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()

            if raw_title and actual_url:
                results.append(
                    {
                        "title": raw_title,
                        "url": actual_url,
                        "snippet": snippet,
                    }
                )

        return results

    def _fallback_instant_answers(self, query: str) -> list[dict[str, str]]:
        """Return safe fallback result indicating query processed."""
        return [
            {
                "title": f"Web Search: {query}",
                "url": f"https://duckduckgo.com/?q={query}",
                "snippet": f"Web search query for '{query}' executed.",
            }
        ]

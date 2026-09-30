import asyncio
import urllib.parse
import webbrowser
from typing import Any
from urllib.parse import urlparse

from backend.app.core.exceptions import ValidationFailedError
from backend.app.core.security import validate_url
from backend.app.skills.base import BaseSkill, SkillContext, SkillManifest, SkillResult

YOUTUBE_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


class YouTubePlaySkill(BaseSkill):
    """Searches for or opens YouTube videos in the default system browser."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="youtube_play",
            description="Search for and play a YouTube video or search query in the default browser.",
            default_tier="CONFIRM",
            default_autonomy="auto+log",
            timeout_seconds=15,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Song title, artist, topic, or search query to open on YouTube.",
                    },
                    "url": {
                        "type": "string",
                        "description": "Direct YouTube URL (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...).",
                    },
                },
                "additionalProperties": False,
            },
        )

    async def execute(self, arguments: dict[str, Any], _context: SkillContext) -> SkillResult:
        raw_url = (arguments.get("url") or "").strip()
        query = (arguments.get("query") or "").strip()

        if not raw_url and not query:
            raise ValidationFailedError("Either 'url' or 'query' must be provided for YouTube playback.")

        target_url: str

        if raw_url:
            validated = validate_url(raw_url)
            parsed = urlparse(validated)
            host = (parsed.hostname or "").lower()
            if host not in YOUTUBE_ALLOWED_HOSTS:
                raise ValidationFailedError(
                    f"URL host '{host}' is not an authorized YouTube domain."
                )
            target_url = validated
        else:
            encoded_query = urllib.parse.quote_plus(query)
            target_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        # Open in default browser in background thread
        opened = await asyncio.to_thread(webbrowser.open, target_url)

        return SkillResult(
            success=True,
            data={
                "played": True,
                "opened_in_browser": opened,
                "target_url": target_url,
                "query": query or None,
            },
        )

import re

from backend.app.llm.types import LLMMessage, ModelRole

# Pre-compiled regex patterns for cheap heuristic classification
_CODE_BLOCK_REGEX = re.compile(r"```[a-zA-Z0-9_\-]*\n[\s\S]*?```", re.MULTILINE)
_CODE_KEYWORDS_REGEX = re.compile(
    r"\b(def|class|async\s+def|import|from\s+[a-zA-Z0-9_]+\s+import|function|const|let|var|return|"
    r"public\s+class|private|protected|namespace|SELECT\s+.*?\s+FROM|UPDATE\s+.*?\s+SET|INSERT\s+INTO|"
    r"git\s+(commit|push|pull|checkout|branch|diff|rebase|merge|status)|traceback|stack\s*trace|"
    r"nullpointerexception|typeerror|attributeerror|syntaxerror|segmentation\s+fault|dockerfile|"
    r"pip\s+install|npm\s+(install|run)|cargo\s+(build|run)|uv\s+run)\b",
    re.IGNORECASE,
)
_CODE_INTENT_REGEX = re.compile(
    r"\b(write\s+(a\s+)?(function|script|code|program|test|unit\s*test)|implement|refactor|"
    r"debug\s+(this|my|the)?|fix\s+(the\s+)?(bug|error|issue|code)|syntax|regex|regular\s+expression|"
    r"pull\s*request|review\s+code|code\s+snippet)\b",
    re.IGNORECASE,
)
_FILE_EXT_REGEX = re.compile(
    r"\b[a-zA-Z0-9_\-\./\\]+\.(py|js|ts|tsx|jsx|html|css|json|yaml|yml|toml|sql|sh|ps1|go|rs|c|cpp|h|java)\b",
    re.IGNORECASE,
)

_SEARCH_INTENT_REGEX = re.compile(
    r"\b(search\s+(the\s+)?web|google|look\s*up\s+online|find\s+online|browse\s+the\s+web|"
    r"what\s+is\s+the\s+latest\s+news|current\s+weather|stock\s+price|latest\s+version\s+of|"
    r"search\s+for|web\s+search)\b",
    re.IGNORECASE,
)
_URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)

_LIGHT_GREETINGS_REGEX = re.compile(
    r"^(hi|hello|hey|good\s+(morning|afternoon|evening|day)|greetings|howdy|"
    r"ping|pong|status|uptime|help|who\s+are\s+you|what\s+can\s+you\s+do|"
    r"what\s+time\s+is\s+it|what\s+is\s+the\s+date|today'?s\s+date|"
    r"thanks|thank\s+you|cheers|bye|goodbye)[.!?\s]*$",
    re.IGNORECASE,
)


def route_prompt_role(
    prompt: str,
    _history: list[LLMMessage] | None = None,
    tool_hint: str | None = None,
) -> ModelRole:
    """
    Route an incoming user prompt to a ModelRole using fast, cheap heuristics
    (regex matching, token length, syntax indicators, tool hints) without making
    any LLM call.
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return ModelRole.LIGHT

    # 1. Tool hint override (e.g. if explicitly passed by an agent or skill)
    if tool_hint:
        hint_lower = tool_hint.lower()
        if "code" in hint_lower or "script" in hint_lower:
            return ModelRole.CODE
        if "search" in hint_lower or "web" in hint_lower:
            return ModelRole.SEARCH
        if "light" in hint_lower:
            return ModelRole.LIGHT

    # 2. Check for Code: code blocks, code keywords, intent, or file paths
    if _CODE_BLOCK_REGEX.search(clean_prompt):
        return ModelRole.CODE
    if _CODE_INTENT_REGEX.search(clean_prompt):
        return ModelRole.CODE
    if _CODE_KEYWORDS_REGEX.search(clean_prompt):
        return ModelRole.CODE
    if _FILE_EXT_REGEX.search(clean_prompt) and ("error" in clean_prompt.lower() or "line" in clean_prompt.lower() or "file" in clean_prompt.lower()):
        return ModelRole.CODE

    # 3. Check for Search: external web queries, URLs, live lookup
    if _SEARCH_INTENT_REGEX.search(clean_prompt):
        return ModelRole.SEARCH
    if _URL_REGEX.search(clean_prompt) and any(
        kw in clean_prompt.lower() for kw in ("check", "summarize", "read", "fetch", "what does", "look at")
    ):
        return ModelRole.SEARCH

    # 4. Check for Light: short (< 80 chars) and matches common greetings/simple queries
    if len(clean_prompt) < 80 and _LIGHT_GREETINGS_REGEX.match(clean_prompt):
        return ModelRole.LIGHT

    # 5. Default: conversational chat
    return ModelRole.CHAT


route_role_heuristically = route_prompt_role


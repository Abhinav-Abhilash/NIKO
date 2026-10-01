import re
from collections.abc import AsyncIterator

# Common abbreviations to avoid premature sentence splitting
ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "sr.",
    "jr.",
    "vs.",
    "etc.",
    "e.g.",
    "i.e.",
    "al.",
    "fig.",
    "no.",
    "approx.",
    "dept.",
    "est.",
}

# Regex to detect potential sentence boundaries: punctuation followed by space or newline
SENTENCE_SPLIT_REGEX = re.compile(r'([.!?]+(?:\s+|$))|\n+')


class SentenceDivider:
    """
    Splits streaming LLM tokens into complete sentences with minimum latency.
    Enables low-latency Time-To-First-Audio (TTFA < 500ms) for streaming TTS synthesis.
    """

    def __init__(self, min_sentence_length: int = 10) -> None:
        self.buffer = ""
        self.min_sentence_length = min_sentence_length

    def feed(self, text_chunk: str) -> list[str]:
        """Feed a new text chunk and return any newly completed sentences."""
        self.buffer += text_chunk
        sentences: list[str] = []
        search_start = 0

        while True:
            match = SENTENCE_SPLIT_REGEX.search(self.buffer, search_start)
            if not match:
                break

            split_pos = match.end()
            candidate = self.buffer[:split_pos].strip()
            remainder = self.buffer[split_pos:]

            if not candidate:
                self.buffer = remainder
                search_start = 0
                continue

            # Check if candidate ends with an abbreviation (e.g. "e.g.", "Dr.")
            candidate_lower = candidate.lower()
            words = candidate_lower.split()
            last_word = words[-1] if words else ""
            if last_word in ABBREVIATIONS and remainder and not remainder.startswith("\n"):
                # Premature split on abbreviation; search for next punctuation further in buffer
                search_start = split_pos
                continue

            # Check if it was a trailing decimal dot mid-number (e.g. candidate ends with "3." and remainder starts with "14")
            if re.search(r'\d+\.$', candidate) and remainder and remainder[0].isdigit():
                search_start = split_pos
                continue

            # If candidate is very short and not ending with a newline, wait for more text if remainder exists
            if len(candidate) < self.min_sentence_length and "\n" not in (match.group(0) or "") and remainder:
                search_start = split_pos
                continue

            sentences.append(candidate)
            self.buffer = remainder
            search_start = 0

        return sentences

    def flush(self) -> list[str]:
        """Flush any remaining text in the buffer as the final sentence."""
        remaining = self.buffer.strip()
        self.buffer = ""
        if remaining:
            return [remaining]
        return []


async def split_stream_sentences(
    token_stream: AsyncIterator[str],
    min_sentence_length: int = 10,
) -> AsyncIterator[str]:
    """Async generator that consumes tokens and yields complete sentences as they arrive."""
    divider = SentenceDivider(min_sentence_length=min_sentence_length)
    async for chunk in token_stream:
        for sentence in divider.feed(chunk):
            yield sentence

    for sentence in divider.flush():
        yield sentence

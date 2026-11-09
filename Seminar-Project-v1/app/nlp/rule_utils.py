"""Check that no unsupported conditions are discarded during rule matching."""
import re


def unconsumed_text(text: str, phrases: list[str], fillers: list[str]) -> str:
    consumed = [False] * len(text)
    for phrase in phrases:
        if phrase:
            for hit in re.finditer(re.escape(phrase), text):
                consumed[hit.start():hit.end()] = [True] * len(hit.group())
    rest = "".join(" " if consumed[i] else c for i, c in enumerate(text))
    for phrase in sorted(fillers, key=len, reverse=True):
        rest = rest.replace(phrase, " ")
    return re.sub(r"[\s?？,，.!！]+", "", rest)

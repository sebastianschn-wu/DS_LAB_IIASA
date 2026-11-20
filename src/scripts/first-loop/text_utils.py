"""Small text helpers shared by all first-loop modules."""

from __future__ import annotations

import re
from typing import Any


def as_text(value: Any) -> str:
    """Return a stripped string; ``None`` becomes an empty string."""
    if value is None:
        return ""
    return str(value).strip()


def normalize_text(text: str) -> str:
    """Collapse whitespace inside lines and drop empty lines."""
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def fold_label(value: str) -> str:
    """Case- and subscript-insensitive form of a category label, used for matching."""
    folded = value.replace("CO₂", "CO2").replace("₂", "2")
    return re.sub(r"\s+", " ", folded).strip().casefold()


def estimate_tokens(text: str) -> int:
    """Approximate a Qwen token count.

    English and similar scripts are counted at about four characters per token.
    CJK, kana and hangul characters are counted as one token each.
    """
    cjk = 0
    other = 0
    for char in text:
        code = ord(char)
        if (
            0x3400 <= code <= 0x9FFF
            or 0x3040 <= code <= 0x30FF
            or 0xAC00 <= code <= 0xD7AF
            or 0xF900 <= code <= 0xFAFF
        ):
            cjk += 1
        else:
            other += 1
    return cjk + (other + 3) // 4

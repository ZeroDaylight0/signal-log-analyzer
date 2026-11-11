"""Mask likely secrets in a log before any of it leaves the machine.

The model is also told to redact, but by then the data has already been sent.
Masking keeps the line structure intact, so line numbers in the analysis still
match the original file.
"""

import re

MASK = "[REDACTED]"

_KEY_NAMES = (
    r"pass(?:word|wd|phrase)?|pwd|secret|client[_-]?secret|token|auth[_-]?token|"
    r"access[_-]?token|refresh[_-]?token|api[_-]?key|apikey|access[_-]?key|"
    r"secret[_-]?key|private[_-]?key|session[_-]?id|cookie"
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Authorization: Bearer abc / Basic abc
    (re.compile(r"(?i)\b(authorization\s*[:=]\s*(?:bearer|basic|token)\s+)[^\s\"',;]+"), rf"\1{MASK}"),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{12,}"), rf"\1{MASK}"),
    # password=..., "api_key": "...", token: ...
    (
        re.compile(
            rf"(?i)((?:\b|_)(?:{_KEY_NAMES})[\"']?\s*[:=]\s*[\"']?)([^\s\"',;&]+)"
        ),
        rf"\1{MASK}",
    ),
    # scheme://user:password@host
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@/]+(@)"), rf"\1{MASK}\2"),
    # Well-known token formats
    (re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}"), MASK),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"), MASK),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"), MASK),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), MASK),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), MASK),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), MASK),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"), MASK),  # Telegram bot token
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), MASK),  # JWT
)

_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL
)


def _mask_block(match: re.Match[str]) -> str:
    # Keep one line per original line so line numbers do not shift.
    return "\n".join(MASK for _ in match.group(0).split("\n"))


def redact_secrets(text: str) -> tuple[str, int]:
    """Return the masked text and how many values were replaced."""
    text, count = _PRIVATE_KEY_BLOCK.subn(_mask_block, text)
    for pattern, replacement in _PATTERNS:
        text, replaced = pattern.subn(replacement, text)
        count += replaced
    return text, count

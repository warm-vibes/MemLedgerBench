from __future__ import annotations

import re
import unicodedata
from collections import Counter


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def tokenize(value: str, *, drop_stopwords: bool = False) -> list[str]:
    tokens = normalize_text(value).split()
    if drop_stopwords:
        tokens = [token for token in tokens if token not in STOPWORDS]
    return tokens


def token_f1(prediction: str, reference: str) -> float:
    predicted = Counter(tokenize(prediction))
    expected = Counter(tokenize(reference))
    if not predicted and not expected:
        return 1.0
    if not predicted or not expected:
        return 0.0
    overlap = sum((predicted & expected).values())
    if overlap == 0:
        return 0.0
    precision = overlap / sum(predicted.values())
    recall = overlap / sum(expected.values())
    return 2 * precision * recall / (precision + recall)


def contains_alias(text: str, aliases: list[str]) -> bool:
    normalized_text = f" {normalize_text(text)} "
    return any(
        normalized_alias and f" {normalized_alias} " in normalized_text
        for normalized_alias in map(normalize_text, aliases)
    )


def is_abstention(answer: str, decision: str = "") -> bool:
    if decision.casefold() in {"abstain", "deny", "clarify"}:
        return True
    normalized = normalize_text(answer)
    phrases = (
        "cannot answer",
        "can t answer",
        "cannot access",
        "don t have access",
        "do not have access",
        "not enough information",
        "insufficient information",
        "i don t know",
        "i do not know",
        "unknown",
    )
    return not normalized or any(phrase in normalized for phrase in phrases)


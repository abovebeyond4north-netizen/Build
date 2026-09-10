"""Local data skills: ingestion, retrieval, and simple summarization."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import log, sqrt
import math
import re
from typing import Iterable

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return [token.lower() for token in _TOKEN_RE.findall(text)]


@dataclass
class Document:
    id: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RetrievalHit:
    document: Document
    score: float


class KnowledgeBase:
    """Tiny TF-IDF knowledge base with no external dependencies."""

    def __init__(self) -> None:
        self._docs: list[Document] = []
        self._doc_freq: dict[str, int] = {}

    @property
    def documents(self) -> tuple[Document, ...]:
        return tuple(self._docs)

    @staticmethod
    def _validate_nonnegative_int(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        return value

    @staticmethod
    def _validate_nonempty_text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value

    def add(self, doc_id: str, text: str, **metadata: str) -> None:
        doc_id = self._validate_nonempty_text(doc_id, "doc_id")
        text = self._validate_nonempty_text(text, "text")
        if any(doc.id == doc_id for doc in self._docs):
            raise ValueError(f"Duplicate document id: {doc_id}")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in metadata.items()):
            raise ValueError("metadata keys and values must be strings")

        doc = Document(doc_id, text, dict(metadata))
        self._docs.append(doc)
        for token in set(tokenize(text)):
            self._doc_freq[token] = self._doc_freq.get(token, 0) + 1

    def ingest(self, items: Iterable[tuple[str, str]]) -> None:
        for doc_id, text in items:
            self.add(doc_id, text)

    def _vector(self, text: str) -> dict[str, float]:
        tokens = tokenize(text)
        if not tokens:
            return {}
        n_docs = max(1, len(self._docs))
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        vec: dict[str, float] = {}
        token_count = len(tokens)
        for token, count in counts.items():
            tf = count / token_count
            idf = log((1 + n_docs) / (1 + self._doc_freq.get(token, 0))) + 1
            vec[token] = tf * idf
        return vec

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0

        # Iterate the smaller vector: O(min(|a|, |b|)) dot-product work instead
        # of materializing the full union of keys.
        smaller, larger = (a, b) if len(a) <= len(b) else (b, a)
        dot = sum(value * larger.get(key, 0.0) for key, value in smaller.items())
        norm_a = sqrt(sum(value * value for value in a.values()))
        norm_b = sqrt(sum(value * value for value in b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        score = dot / (norm_a * norm_b)
        return score if math.isfinite(score) else 0.0

    def search(self, query: str, top_k: int = 3) -> list[RetrievalHit]:
        top_k = self._validate_nonnegative_int(top_k, "top_k")
        if top_k == 0 or not self._docs:
            return []

        qv = self._vector(query)
        if not qv:
            return []

        hits = [
            RetrievalHit(doc, self._cosine(qv, self._vector(doc.text)))
            for doc in self._docs
        ]
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return [hit for hit in hits[:top_k] if hit.score > 0.0]

    def summarize_hits(
        self,
        hits: Iterable[RetrievalHit],
        max_chars: int = 900,
    ) -> str:
        max_chars = self._validate_nonnegative_int(max_chars, "max_chars")
        if max_chars == 0:
            return ""

        parts: list[str] = []
        for hit in hits:
            snippet = hit.document.text.strip().replace("\n", " ")
            parts.append(f"[{hit.document.id} score={hit.score:.2f}] {snippet}")
        summary = "\n".join(parts)
        return summary[:max_chars]

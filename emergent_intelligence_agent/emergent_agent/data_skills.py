"""Local data skills: ingestion, retrieval, and simple summarization."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import log, sqrt
import re
from typing import Iterable

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


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

    def add(self, doc_id: str, text: str, **metadata: str) -> None:
        if any(doc.id == doc_id for doc in self._docs):
            raise ValueError(f"Duplicate document id: {doc_id}")
        doc = Document(doc_id, text, metadata)
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
        for token, count in counts.items():
            tf = count / len(tokens)
            idf = log((1 + n_docs) / (1 + self._doc_freq.get(token, 0))) + 1
            vec[token] = tf * idf
        return vec

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in set(a) | set(b))
        norm_a = sqrt(sum(v * v for v in a.values()))
        norm_b = sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 3) -> list[RetrievalHit]:
        qv = self._vector(query)
        hits = [RetrievalHit(doc, self._cosine(qv, self._vector(doc.text))) for doc in self._docs]
        hits.sort(key=lambda h: h.score, reverse=True)
        return [h for h in hits[:top_k] if h.score > 0]

    def summarize_hits(self, hits: Iterable[RetrievalHit], max_chars: int = 900) -> str:
        parts: list[str] = []
        for hit in hits:
            snippet = hit.document.text.strip().replace("\n", " ")
            parts.append(f"[{hit.document.id} score={hit.score:.2f}] {snippet}")
        summary = "\n".join(parts)
        return summary[:max_chars]

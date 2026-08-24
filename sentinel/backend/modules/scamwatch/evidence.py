"""Evidence store: vector retrieval over previously confirmed scam patterns.

This is RAG in the literal sense - retrieved evidence is injected into the
reasoning prompt and cited by the verdict. Retrieval quality is measured by
the evaluation harness (tests/evals), not asserted here.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

_SIMILARITY_FLOOR = 0.35


@dataclass(frozen=True)
class EvidenceItem:
    doc_id: str
    text: str
    metadata: dict
    similarity: float | None


class EvidenceBackend(Protocol):
    def add(self, doc_id: str, text: str, metadata: dict) -> None: ...
    def query(self, text: str, k: int = 3) -> list[EvidenceItem]: ...


class ChromaEvidenceBackend:
    """ChromaDB + sentence-transformers. Degrades to empty results on failure."""

    def __init__(self, persist_dir: str, collection: str = "scam_patterns_v2"):
        self._persist_dir = persist_dir
        self._collection_name = collection
        self._lock = threading.Lock()
        self._client = None
        self._collection = None
        self._encoder = None

    def _ensure(self) -> bool:
        if self._collection is not None:
            return True
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            from sentence_transformers import SentenceTransformer

            with self._lock:
                if self._collection is not None:
                    return True
                self._client = chromadb.PersistentClient(
                    path=self._persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._collection = self._client.get_or_create_collection(
                    self._collection_name
                )
                if self._encoder is None:
                    self._encoder = SentenceTransformer(
                        "all-MiniLM-L6-v2", device="cpu"
                    )
            return True
        except Exception as exc:
            logger.warning("evidence backend unavailable: %s", exc)
            return False

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._encoder.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def add(self, doc_id: str, text: str, metadata: dict) -> None:
        if not self._ensure():
            return
        try:
            self._collection.add(
                ids=[doc_id],
                embeddings=self._embed([text]),
                documents=[text],
                metadatas=[metadata],
            )
        except Exception as exc:
            logger.warning("evidence add failed for %s: %s", doc_id, exc)

    def query(self, text: str, k: int = 3) -> list[EvidenceItem]:
        if not self._ensure() or self._collection.count() == 0:
            return []
        try:
            raw = self._collection.query(
                query_embeddings=self._embed([text]), n_results=k
            )
            items = []
            ids = raw.get("ids", [[]])[0]
            docs = raw.get("documents", [[]])[0]
            metas = raw.get("metadatas", [[]])[0]
            dists = (raw.get("distances") or [[None] * len(ids)])[0]
            for doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
                similarity = (1.0 - dist) if isinstance(dist, (int, float)) else None
                if similarity is not None and similarity < _SIMILARITY_FLOOR:
                    continue
                items.append(
                    EvidenceItem(
                        doc_id=doc_id,
                        text=doc or "",
                        metadata=meta or {},
                        similarity=similarity,
                    )
                )
            return items
        except Exception as exc:
            logger.warning("evidence query failed: %s", exc)
            return []


class InMemoryEvidenceBackend:
    """Deterministic backend for tests and offline runs."""

    def __init__(self):
        self.docs: dict[str, tuple[str, dict]] = {}

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(text.lower().split())

    def add(self, doc_id: str, text: str, metadata: dict) -> None:
        self.docs[doc_id] = (text, metadata)

    def query(self, text: str, k: int = 3) -> list[EvidenceItem]:
        query_tokens = self._tokens(text)
        scored = []
        for doc_id, (doc, meta) in self.docs.items():
            overlap = len(query_tokens & self._tokens(doc))
            if overlap == 0:
                continue
            jaccard = overlap / len(query_tokens | self._tokens(doc))
            if jaccard >= _SIMILARITY_FLOOR:
                scored.append(
                    EvidenceItem(
                        doc_id=doc_id,
                        text=doc,
                        metadata=meta,
                        similarity=round(jaccard, 3),
                    )
                )
        scored.sort(key=lambda item: item.similarity or 0.0, reverse=True)
        return scored[:k]


_store: EvidenceBackend | None = None


def get_evidence_backend() -> EvidenceBackend:
    global _store
    if _store is None:
        from backend.core.config import get_settings

        settings = get_settings()
        if settings.app_env == "test":
            _store = InMemoryEvidenceBackend()
        else:
            _store = ChromaEvidenceBackend(settings.chroma_persist_dir)
    return _store


def set_evidence_backend(backend: EvidenceBackend | None) -> None:
    global _store
    _store = backend

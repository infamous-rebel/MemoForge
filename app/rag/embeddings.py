"""Embeddings abstraction with TF-IDF fallback.

Supports multiple embedding providers (VoyageAI, OpenAI, Cohere) with
a TF-IDF fallback for offline demos when no API key is available.

Design decision: The TF-IDF fallback ensures the system can run end-to-end
in demo mode without any external API dependencies, while still providing
meaningful similarity search results on the ingested corpus.
"""

from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from collections import Counter
from typing import Dict, List, Optional

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts into vectors."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...


class TFIDFProvider(EmbeddingProvider):
    """TF-IDF based embedding provider for offline/demo use.

    Uses a simple TF-IDF vectorization with fixed vocabulary built
    from the corpus. Produces deterministic, reproducible embeddings.
    """

    def __init__(self, dim: int = 384):
        self._dim = dim
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._fitted = False

    def fit(self, documents: List[str]) -> None:
        """Build vocabulary and IDF from a corpus of documents."""
        if not documents:
            self._fitted = True
            return

        # Build vocabulary from all unique words
        word_doc_count: Counter = Counter()
        total_docs = len(documents)

        for doc in documents:
            words = set(doc.lower().split())
            for w in words:
                word_doc_count[w] += 1

        # Select top-k words by document frequency for fixed dimension
        sorted_words = sorted(word_doc_count.items(), key=lambda x: -x[1])
        self._vocab = {w: i for i, (w, _) in enumerate(sorted_words[:self._dim])}

        # Compute IDF
        self._idf = {}
        for word, idx in self._vocab.items():
            df = word_doc_count.get(word, 1)
            self._idf[word] = math.log((total_docs + 1) / (df + 1)) + 1

        self._fitted = True
        logger.info("TF-IDF fitted with %d vocabulary terms", len(self._vocab))

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using TF-IDF."""
        if not self._fitted:
            # Auto-fit on first call if not already fitted
            self.fit(texts)

        results = []
        for text in texts:
            vec = np.zeros(self._dim, dtype=np.float32)
            words = text.lower().split()
            word_counts = Counter(words)
            total_words = max(len(words), 1)

            for word, count in word_counts.items():
                if word in self._vocab:
                    idx = self._vocab[word]
                    tf = count / total_words
                    idf = self._idf.get(word, 1.0)
                    vec[idx] = tf * idf

            # L2 normalize
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            results.append(vec.tolist())

        return results

    def dimension(self) -> int:
        return self._dim


class VoyageProvider(EmbeddingProvider):
    """VoyageAI embedding provider."""

    def __init__(self, api_key: str, model: str = "voyage-finance-2"):
        import httpx
        self._client = httpx.Client(
            base_url="https://api.voyageai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        self._model = model
        self._dim = 1024

    def embed(self, texts: List[str]) -> List[List[float]]:
        resp = self._client.post(
            "/embeddings",
            json={"input": texts, "model": self._model},
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    def dimension(self) -> int:
        return self._dim


class OpenAIEmbedProvider(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        import openai
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self._dim = 1536

    def embed(self, texts: List[str]) -> List[List[float]]:
        resp = self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in resp.data]

    def dimension(self) -> int:
        return self._dim


def get_embedding_provider() -> EmbeddingProvider:
    """Factory: create embedding provider based on configuration."""
    settings = get_settings()
    provider = settings.embedding_provider.lower()

    if provider == "tfidf" or settings.mock_mode:
        logger.info("Using TF-IDF embedding provider")
        return TFIDFProvider()

    elif provider == "voyage":
        if not settings.embedding_api_key:
            logger.warning("No EMBEDDING_API_KEY — falling back to TF-IDF")
            return TFIDFProvider()
        return VoyageProvider(api_key=settings.embedding_api_key, model=settings.embedding_model)

    elif provider == "openai":
        if not settings.embedding_api_key:
            logger.warning("No EMBEDDING_API_KEY — falling back to TF-IDF")
            return TFIDFProvider()
        return OpenAIEmbedProvider(api_key=settings.embedding_api_key, model=settings.embedding_model)

    else:
        logger.warning("Unknown embedding provider '%s' — using TF-IDF", provider)
        return TFIDFProvider()

from __future__ import annotations
# AnimaWorks - Digital Anima Framework
# Copyright (C) 2026 AnimaWorks Authors
# SPDX-License-Identifier: Apache-2.0

"""Process-level singletons for RAG components.

Ensures ChromaVectorStore and SentenceTransformer embedding model
are initialized only once per process, avoiding costly repeated
model loading (~6 seconds per initialization).

When the environment variable ``ANIMAWORKS_EMBEDDING_SERVER_URL`` is set,
embedding generation is delegated to the main server process via HTTP,
so worker processes (supervisor runners) never load the model locally.
"""

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.rag.store import ChromaVectorStore
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_vector_stores: dict[str | None, ChromaVectorStore] = {}
_embedding_model: SentenceTransformer | None = None
_embedding_model_name: str | None = None

# ── Remote embedding client ──────────────────────────────────────────

_remote_model: RemoteEmbeddingModel | None = None
_remote_model_name: str | None = None

# ── LM Studio / OpenAI-compatible embedding client ───────────────────

_openai_compat_model: OpenAICompatibleEmbeddingModel | None = None
_openai_compat_model_name: str | None = None


class OpenAICompatibleEmbeddingModel:
    """Embedding client for OpenAI-compatible APIs (e.g. LM Studio).

    Calls the /v1/embeddings endpoint and returns numpy arrays,
    compatible with the SentenceTransformer interface used in AnimaWorks.
    """

    def __init__(self, api_base: str, model_name: str, api_key: str = "lm-studio") -> None:
        self._embed_url = api_base.rstrip("/") + "/embeddings"
        self._model_name = model_name
        self._api_key = api_key
        self._dimension: int | None = None

    def encode(
        self,
        texts: list[str],
        *,
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
        **_kwargs: Any,
    ):
        """Call OpenAI-compatible /v1/embeddings and return embeddings."""
        import json as _json
        payload = _json.dumps({
            "model": self._model_name,
            "input": texts,
        }).encode()
        req = urllib.request.Request(
            self._embed_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = _json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"LM Studio embedding API unreachable at {self._embed_url}: {exc}"
            ) from exc

        embeddings = [item["embedding"] for item in data["data"]]
        if embeddings:
            self._dimension = len(embeddings[0])

        if convert_to_numpy:
            import numpy as np
            return np.array(embeddings, dtype=np.float32)
        return embeddings

    def get_sentence_embedding_dimension(self) -> int:
        if self._dimension is None:
            self.encode(["__dim_probe__"])
        return self._dimension  # type: ignore[return-value]


class RemoteEmbeddingModel:
    """Thin HTTP client that delegates encode() to the embedding server.

    Implements the subset of the SentenceTransformer interface used by
    AnimaWorks (encode + get_sentence_embedding_dimension), so it can be
    used as a drop-in replacement without loading the model locally.
    """

    def __init__(self, server_url: str, model_name: str) -> None:
        self._embed_url = server_url.rstrip("/") + "/api/internal/embed"
        self._model_name = model_name
        self._dimension: int | None = None

    def encode(
        self,
        texts: list[str],
        *,
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
        **_kwargs: Any,
    ):
        """Send texts to the embedding server and return embeddings."""
        payload = json.dumps({"texts": texts, "model_name": self._model_name}).encode()
        req = urllib.request.Request(
            self._embed_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Embedding server unreachable at {self._embed_url}: {exc}"
            ) from exc

        self._dimension = data["dimension"]

        if convert_to_numpy:
            import numpy as np
            return np.array(data["embeddings"], dtype=np.float32)
        return data["embeddings"]

    def get_sentence_embedding_dimension(self) -> int:
        if self._dimension is None:
            self.encode(["__dim_probe__"])
        return self._dimension  # type: ignore[return-value]


def get_vector_store(anima_name: str | None = None) -> ChromaVectorStore:
    """Return process-level singleton ChromaVectorStore per anima.

    Args:
        anima_name: Anima name for per-anima DB isolation.
            When ``None``, uses the legacy shared directory.
    """
    if anima_name not in _vector_stores:
        with _lock:
            if anima_name not in _vector_stores:
                from core.memory.rag.store import ChromaVectorStore
                if anima_name:
                    from core.paths import get_anima_vectordb_dir
                    persist_dir = get_anima_vectordb_dir(anima_name)
                else:
                    persist_dir = None  # ChromaVectorStore defaults to ~/.animaworks/vectordb
                _vector_stores[anima_name] = ChromaVectorStore(persist_dir=persist_dir)
    return _vector_stores[anima_name]


def _get_configured_model_name() -> str:
    """Read embedding model name from config.json, falling back to default."""
    try:
        from core.config import load_config
        config = load_config()
        return config.rag.embedding_model
    except Exception:
        return "intfloat/multilingual-e5-small"


def _get_configured_embedding_api() -> tuple[str, str]:
    """Read embedding_api_base and embedding_api_key from config.json."""
    try:
        from core.config import load_config
        config = load_config()
        return config.rag.embedding_api_base, config.rag.embedding_api_key
    except Exception:
        return "", ""


def get_embedding_model(model_name: str | None = None) -> SentenceTransformer:
    """Return the embedding model for this process.

    Priority:
    1. ``rag.embedding_api_base`` in config.json → :class:`OpenAICompatibleEmbeddingModel`
       (e.g. LM Studio running locally)
    2. ``ANIMAWORKS_EMBEDDING_SERVER_URL`` env var → :class:`RemoteEmbeddingModel`
       (AnimaWorks internal embedding server)
    3. Local SentenceTransformer model (default behaviour)

    Args:
        model_name: Explicit model name override.  When ``None``,
            the model is resolved from ``config.json``
            (``rag.embedding_model``).
    """
    global _embedding_model, _embedding_model_name
    global _remote_model, _remote_model_name
    global _openai_compat_model, _openai_compat_model_name

    # Priority 1: OpenAI-compatible API (LM Studio etc.)
    api_base, api_key = _get_configured_embedding_api()
    if api_base:
        resolved_name = model_name or _get_configured_model_name()
        if _openai_compat_model is None or _openai_compat_model_name != resolved_name:
            with _lock:
                if _openai_compat_model is None or _openai_compat_model_name != resolved_name:
                    logger.info(
                        "Using OpenAI-compatible embedding API: %s (model=%s)",
                        api_base, resolved_name,
                    )
                    _openai_compat_model = OpenAICompatibleEmbeddingModel(
                        api_base, resolved_name, api_key or "lm-studio"
                    )
                    _openai_compat_model_name = resolved_name
        return _openai_compat_model  # type: ignore[return-value]

    # Priority 2: AnimaWorks internal embedding server
    server_url = os.environ.get("ANIMAWORKS_EMBEDDING_SERVER_URL")
    if server_url:
        resolved_name = model_name or _get_configured_model_name()
        if _remote_model is None or _remote_model_name != resolved_name:
            with _lock:
                if _remote_model is None or _remote_model_name != resolved_name:
                    logger.info(
                        "Using remote embedding server: %s (model=%s)",
                        server_url, resolved_name,
                    )
                    _remote_model = RemoteEmbeddingModel(server_url, resolved_name)
                    _remote_model_name = resolved_name
        return _remote_model  # type: ignore[return-value]

    resolved_name = model_name or _get_configured_model_name()

    # Fast path: already loaded with the same model name
    if _embedding_model is not None and _embedding_model_name == resolved_name:
        return _embedding_model

    with _lock:
        # Double-check after acquiring lock
        if _embedding_model is not None and _embedding_model_name == resolved_name:
            return _embedding_model

        # Different model requested → discard and reload
        if _embedding_model is not None and _embedding_model_name != resolved_name:
            logger.info(
                "Embedding model changed: %s → %s; reloading",
                _embedding_model_name, resolved_name,
            )

        from sentence_transformers import SentenceTransformer
        from core.paths import get_data_dir
        cache_dir = get_data_dir() / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Loading embedding model (singleton): %s", resolved_name)
        _embedding_model = SentenceTransformer(
            resolved_name, cache_folder=str(cache_dir)
        )
        _embedding_model_name = resolved_name
        logger.info("Embedding model loaded (singleton)")
    return _embedding_model


def get_embedding_dimension() -> int:
    """Return the dimensionality of the current embedding model.

    Loads the model if not yet initialized, then queries it for
    the sentence embedding dimension.
    """
    model = get_embedding_model()
    dim = model.get_sentence_embedding_dimension()
    if dim is None:
        raise RuntimeError("Embedding model did not report a dimension")
    return dim


def get_embedding_model_name() -> str:
    """Return the name of the currently loaded (or configured) embedding model."""
    if _embedding_model_name is not None:
        return _embedding_model_name
    return _get_configured_model_name()


def _reset_for_testing():
    """Reset singletons for test isolation."""
    global _embedding_model, _embedding_model_name
    with _lock:
        _vector_stores.clear()
        _embedding_model = None
        _embedding_model_name = None

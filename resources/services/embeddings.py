"""
Embedding backends for vector ingestion and search.

Primary path: try `sentence-transformers` (all-MiniLM-L6-v2).
Fallback: Chroma's bundled ONNX MiniLM model (avoids TensorFlow/Keras import issues on some dev machines).

TODO: wire OpenAIEmbeddingFunction to env-based client for production scale.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class EmbeddingFunction(Protocol):
    """Minimal interface compatible with Chroma-style usage."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalSentenceTransformerEmbeddingFunction:
    """Local embeddings via sentence-transformers (lazy model load)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        # Reduce accidental TensorFlow imports on broken global installs.
        os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
        os.environ.setdefault("USE_TF", "0")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            ) from exc
        logger.info("Loading SentenceTransformer model: %s", self.model_name)
        self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [v.astype(float).tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class ChromaOnnxMiniLmEmbeddingFunction:
    """
    Chroma-shipped ONNX model (downloads once to ~/.cache/chroma/onnx_models).

    This is the hackathon-friendly default when `sentence_transformers` imports fail
    due to optional TensorFlow/Keras conflicts in the global Python environment.
    """

    def __init__(self):
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self._inner = ONNXMiniLM_L6_V2()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._inner(texts)
        return [list(map(float, v)) for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class OpenAIEmbeddingFunction:
    """
    Placeholder for OpenAI (or compatible) embeddings.

    TODO: implement using openai.OpenAI() and settings.OPENAI_API_KEY
    TODO: pick model (e.g. text-embedding-3-small) and dimension alignment with Chroma collection
    """

    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - stub
        raise NotImplementedError("OpenAIEmbeddingFunction is not implemented yet.")

    def embed_query(self, text: str) -> list[float]:  # pragma: no cover - stub
        raise NotImplementedError("OpenAIEmbeddingFunction is not implemented yet.")


def get_embedding_function() -> EmbeddingFunction | None:
    """
    Return the active embedding function, or None if all backends fail.

    Swap implementation here (env flag) without touching ingestion/vector_store.
    """
    try:
        fn = LocalSentenceTransformerEmbeddingFunction()
        # Smoke test (catches many global-environment import failures early).
        _ = fn.embed_query("healthcheck")
        return fn
    except Exception as exc:
        logger.warning(
            "SentenceTransformers backend unavailable (%s) — falling back to Chroma ONNX MiniLM.",
            exc,
        )
    try:
        fn = ChromaOnnxMiniLmEmbeddingFunction()
        _ = fn.embed_query("healthcheck")
        return fn
    except Exception as exc:
        logger.error("Chroma ONNX embedding backend unavailable: %s", exc)
        return None

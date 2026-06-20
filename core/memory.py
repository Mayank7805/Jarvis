"""
core/memory.py — Long-Term Memory with ChromaDB

Provides persistent, semantically-searchable memory for Jarvis using:
  • ChromaDB     — vector store for embedding-based retrieval
  • sentence-transformers — lightweight CPU-optimized embeddings

Memory types:
  • Episodic  — every conversation turn (auto-saved by the router)
  • Semantic  — explicit facts the user tells Jarvis to remember
"""

import uuid
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Prevent transformers from attempting to load TensorFlow/Keras
# (we only use PyTorch for sentence-transformers embeddings)
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings


def _safe_print(msg: str) -> None:
    """Print with fallback for terminals that can't render certain Unicode (e.g. cp1252)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

PERSIST_DIR = Path("data") / "memory"
COLLECTION_NAME = "jarvis_memory"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# ──────────────────────────────────────────────
#  Embedding Function (wraps sentence-transformers)
# ──────────────────────────────────────────────

class _SentenceTransformerEF(EmbeddingFunction[Documents]):
    """
    Custom ChromaDB embedding function backed by sentence-transformers.

    Loads the model once on init and reuses it for all embed calls.
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = self._model.encode(input, convert_to_numpy=True)
        return embeddings.tolist()


# ──────────────────────────────────────────────
#  JarvisMemory
# ──────────────────────────────────────────────

class JarvisMemory:
    """
    Persistent long-term memory for the Jarvis assistant.

    Uses ChromaDB with sentence-transformer embeddings to store and
    retrieve conversation history (episodic) and explicit facts (semantic).
    """

    def __init__(
        self,
        persist_dir: str | Path = PERSIST_DIR,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        # Generate a unique session ID for this runtime
        self._session_id = str(uuid.uuid4())

        # Load embedding model (downloads ~80 MB on first run, then cached)
        _safe_print(f"\U0001f9e0  Loading embedding model: {EMBEDDING_MODEL} ...")
        self._embedding_fn = _SentenceTransformerEF(EMBEDDING_MODEL)
        _safe_print(f"\u2705  Embedding model ready.")

        # ChromaDB persistent client
        self._client = chromadb.PersistentClient(path=str(self._persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
        )

        doc_count = self._collection.count()
        _safe_print(f"\U0001f4be  Memory loaded \u2014 {doc_count} memories in store.")

    # ── Episodic Memory (auto-saved conversation turns) ──

    def save(self, role: str, content: str) -> None:
        """
        Save a conversation turn to episodic memory.

        Args:
            role:    "user" or "assistant".
            content: The message text.
        """
        if not content or not content.strip():
            return

        doc_id = str(uuid.uuid4())
        metadata = {
            "role": role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "type": "episodic",
        }

        self._collection.add(
            documents=[content.strip()],
            metadatas=[metadata],
            ids=[doc_id],
        )

    def search(self, query: str, n: int = 3) -> list[str]:
        """
        Semantic search across all stored memories.

        Args:
            query: Natural language search query.
            n:     Number of results to return.

        Returns:
            List of relevant past exchanges (most similar first).
        """
        if self._collection.count() == 0:
            return []

        # Don't request more results than documents in the collection
        actual_n = min(n, self._collection.count())

        results = self._collection.query(
            query_texts=[query],
            n_results=actual_n,
        )

        documents = results.get("documents", [[]])[0]
        return documents

    # ── Semantic Memory (explicit facts) ──────

    def remember(self, key: str, value: str) -> None:
        """
        Store an explicit fact the user wants Jarvis to remember.

        Examples:
            remember("laptop password", "hunter2")
            remember("birthday", "March 15")

        Args:
            key:   A short label/key for the fact.
            value: The fact content to remember.
        """
        if not value or not value.strip():
            return

        doc_id = str(uuid.uuid4())
        # Store as "key: value" for better retrieval
        document = f"{key}: {value}"
        metadata = {
            "type": "explicit",
            "key": key.strip().lower(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
        }

        self._collection.add(
            documents=[document],
            metadatas=[metadata],
            ids=[doc_id],
        )

    def recall(self, query: str) -> str | None:
        """
        Search explicit memories first, returning the best match.

        Args:
            query: What the user is trying to recall.

        Returns:
            A formatted string with the recalled fact, or None.
        """
        if self._collection.count() == 0:
            return None

        # Count how many explicit memories exist
        try:
            explicit_results = self._collection.get(
                where={"type": "explicit"},
            )
            explicit_count = len(explicit_results.get("ids", []))
        except Exception:
            explicit_count = 0

        if explicit_count == 0:
            return None

        actual_n = min(3, explicit_count)

        results = self._collection.query(
            query_texts=[query],
            n_results=actual_n,
            where={"type": "explicit"},
        )

        documents = results.get("documents", [[]])[0]
        if not documents:
            return None

        # Return the top match
        return f"I remember: {documents[0]}"

    # ── Context Builder (combines both memory types) ──

    def get_context(self, query: str) -> str:
        """
        Build a combined context string from explicit recall + semantic search.

        This string is prepended to the LLM system prompt to give Jarvis
        awareness of past interactions and stored facts.

        Args:
            query: The current user query to find relevant memories for.

        Returns:
            Formatted context string (may be empty if no relevant memories).
        """
        parts: list[str] = []

        # 1. Check explicit memories first
        explicit = self.recall(query)
        if explicit:
            parts.append(f"[Explicit Memory] {explicit}")

        # 2. Semantic search across all memories
        related = self.search(query, n=3)
        if related:
            parts.append("[Related Past Conversations]")
            for i, mem in enumerate(related, 1):
                # Truncate very long memories to keep context lean
                truncated = mem[:300] + "..." if len(mem) > 300 else mem
                parts.append(f"  {i}. {truncated}")

        if not parts:
            return ""

        return "\n".join(parts)

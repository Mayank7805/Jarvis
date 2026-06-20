"""
llm/ollama_client.py — Local LLM Client via Ollama

Provides a conversational interface to the Ollama-hosted phi3.5 model.
Used for general-purpose queries that don't require internet access.
Maintains conversation history for multi-turn dialogue.
"""

import ollama


# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

DEFAULT_MODEL = "phi3.5"

SYSTEM_PROMPT = (
    "You are Jarvis, an AI assistant. Rules:\n"
    "- MAXIMUM 2 sentences per response. No exceptions.\n"
    "- Be direct and precise. No filler words.\n"
    "- No bullet points. Plain conversational speech only.\n"
    "- If answer needs more detail, give summary + offer to elaborate.\n"
    "- User's name is Mayank."
)


# ──────────────────────────────────────────────
#  OllamaClient
# ──────────────────────────────────────────────

class OllamaClient:
    """
    Chat client for a locally-running Ollama model.

    Args:
        model:         Ollama model tag (default: phi3.5).
        system_prompt: System-level instruction injected at the start of every conversation.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self._history: list[dict[str, str]] = []

        # Verify that Ollama is reachable and the model exists
        self._verify_connection()

    # ── Public API ──────────────────────────

    def chat(self, prompt: str, history: list[dict[str, str]] | None = None, memory_context: str = "") -> str:
        """
        Send a user message and return the assistant's reply.

        Args:
            prompt:         The user's text input.
            history:        Optional external history to use instead of internal state.
                            Each entry is ``{"role": "user"|"assistant", "content": "..."}``.
            memory_context: Optional context from long-term memory to prepend to system prompt.

        Returns:
            The assistant's response string.

        Raises:
            ConnectionError: If the Ollama server is not running or unreachable.
            RuntimeError:    If the model returns an empty or invalid response.
        """
        # Use provided history or fall back to internal history
        working_history = history if history is not None else self._history

        # Build effective system prompt with memory context
        effective_prompt = self.system_prompt
        if memory_context:
            effective_prompt = (
                f"Relevant context from memory:\n{memory_context}\n\n"
                f"{self.system_prompt}"
            )

        # Build the full message list: system → history → new user turn
        messages = [{"role": "system", "content": effective_prompt}]
        messages.extend(working_history)
        messages.append({"role": "user", "content": prompt})

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                stream=False,
            )
        except ollama.ResponseError as e:
            raise RuntimeError(
                f"Ollama response error (model={self.model}): {e}"
            ) from e
        except Exception as e:
            raise ConnectionError(
                f"Cannot reach Ollama server. Is it running? "
                f"Start it with 'ollama serve'. Error: {e}"
            ) from e

        # Extract the reply text based on response type (SDK v0.2+ returns objects, older returns dicts)
        if hasattr(response, "message"):
            reply = response.message.content.strip()
        else:
            reply = response["message"]["content"].strip()

        if not reply:
            raise RuntimeError("Ollama returned an empty response.")

        # Persist the turn in internal history (only if we used it)
        if history is None:
            self._history.append({"role": "user", "content": prompt})
            self._history.append({"role": "assistant", "content": reply})

        return reply

    def stream_chat(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
        memory_context: str = "",
    ):
        """
        Stream the assistant's reply sentence-by-sentence.

        Uses Ollama's native streaming mode. Accumulates chunks and
        yields complete sentences split on `.`, `?`, `!` boundaries.

        Args:
            prompt:         The user's text input.
            history:        Optional external history (caller-managed).
            memory_context: Optional context from long-term memory.

        Yields:
            str — One complete sentence at a time.
        """
        import re

        working_history = history if history is not None else self._history

        # Build effective system prompt with memory context
        effective_prompt = self.system_prompt
        if memory_context:
            effective_prompt = (
                f"Relevant context from memory:\n{memory_context}\n\n"
                f"{self.system_prompt}"
            )

        messages = [{"role": "system", "content": effective_prompt}]
        messages.extend(working_history)
        messages.append({"role": "user", "content": prompt})

        try:
            stream = ollama.chat(
                model=self.model,
                messages=messages,
                stream=True,
            )

            buffer = ""
            full_response = ""
            sentence_re = re.compile(r'(?<=[.!?])\s+')

            for chunk in stream:
                # Extract text from chunk (handles both SDK object and dict)
                if hasattr(chunk, "message"):
                    text = chunk.message.content or ""
                else:
                    text = chunk.get("message", {}).get("content", "")
                if not text:
                    continue
                buffer += text
                full_response += text

                # Split buffer into sentences
                parts = sentence_re.split(buffer)
                for sentence in parts[:-1]:
                    sentence = sentence.strip()
                    if sentence:
                        yield sentence
                buffer = parts[-1] if parts else ""

            # Yield remaining text
            if buffer.strip():
                yield buffer.strip()

            # Persist the turn in internal history (only when using it)
            full_text = full_response.strip()
            if history is None and full_text:
                self._history.append({"role": "user", "content": prompt})
                self._history.append({"role": "assistant", "content": full_text})

        except ollama.ResponseError as e:
            raise RuntimeError(
                f"Ollama streaming error (model={self.model}): {e}"
            ) from e
        except Exception as e:
            raise ConnectionError(
                f"Cannot reach Ollama server during streaming. Error: {e}"
            ) from e

    def reset_history(self) -> None:
        """Clear the conversation history to start a fresh session."""
        self._history.clear()

    @property
    def history(self) -> list[dict[str, str]]:
        """Return a copy of the current conversation history."""
        return list(self._history)

    # ── Internal helpers ────────────────────

    def _verify_connection(self) -> None:
        """Ping the Ollama server to confirm it's reachable and pull the model if needed."""
        try:
            ollama.list()
        except Exception as e:
            raise ConnectionError(
                "Ollama is not running or not reachable on this machine. "
                "Please start it with 'ollama serve'. "
                f"Error: {e}"
            ) from e

        # Check if the required model is pulled
        try:
            ollama.show(self.model)
        except ollama.ResponseError:
            print(f"📥 Model '{self.model}' not found locally. Pulling it now... (this may take a while)")
            try:
                ollama.pull(self.model)
                print(f"✅ Successfully pulled '{self.model}'.")
            except Exception as e:
                raise RuntimeError(f"Failed to pull Ollama model '{self.model}': {e}")

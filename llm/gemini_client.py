"""
llm/gemini_client.py — Cloud LLM Client via Google Gemini

Provides a conversational interface to Gemini 2.5 Flash for queries that
benefit from internet access or grounded search (weather, news, prices, etc.).
Loads the API key from the .env file via python-dotenv.
"""

import os
from google import genai
from google.genai import types


# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

DEFAULT_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are Jarvis, an AI assistant. Rules:\n"
    "- MAXIMUM 2 sentences per response. No exceptions.\n"
    "- Be direct and precise. No filler words.\n"
    "- No bullet points. Plain conversational speech only.\n"
    "- If answer needs more detail, give summary + offer to elaborate.\n"
    "- User's name is Mayank."
)


# ──────────────────────────────────────────────
#  GeminiClient
# ──────────────────────────────────────────────

class GeminiClient:
    """
    Chat client backed by Google's new Gemini API SDK.

    Args:
        model:         Gemini model name (default: gemini-2.5-flash).
        system_prompt: System-level instruction for the model.
        api_key:       Explicit API key override; if None, reads GEMINI_API_KEY from env.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        system_prompt: str = SYSTEM_PROMPT,
        api_key: str | None = None,
    ) -> None:
        self.model_name = model
        self.system_prompt = system_prompt
        self._history: list[dict[str, str]] = []

        # Resolve API key
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise EnvironmentError(
                "GEMINI_API_KEY not found. Set it in your .env file or pass it explicitly."
            )

        # Initialize the new SDK client
        self.client = genai.Client(api_key=key)

    # ── Public API ──────────────────────────

    def chat(self, prompt: str, history: list[dict[str, str]] | None = None, memory_context: str = "") -> str:
        """
        Send a user message and return the assistant's reply.
        """
        working_history = history if history is not None else self._history

        # Build effective system prompt with memory context
        effective_prompt = self.system_prompt
        if memory_context:
            effective_prompt = (
                f"Relevant context from memory:\n{memory_context}\n\n"
                f"{self.system_prompt}"
            )

        # Build new SDK history using types.Content and types.Part
        contents = []
        for msg in working_history:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
            )

        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=effective_prompt,
                )
            )
            reply = response.text.strip()
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}") from e

        if not reply:
            raise RuntimeError("Gemini returned an empty response.")

        # Persist the turn in internal history (only when using it)
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

        Yields complete sentences as they become available from the
        Gemini streaming API. After the generator is fully consumed,
        the turn is persisted in internal history (when no external
        history is provided).

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

        # Build contents list (same structure as chat())
        contents = []
        for msg in working_history:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
            )
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        )

        try:
            response_stream = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=effective_prompt,
                ),
            )

            buffer = ""
            full_response = ""
            # Regex: split keeping the delimiter attached to the sentence
            sentence_re = re.compile(r'(?<=[.!?])\s+')

            for chunk in response_stream:
                text = chunk.text if chunk.text else ""
                if not text:
                    continue
                buffer += text
                full_response += text

                # Split buffer into sentences
                parts = sentence_re.split(buffer)
                # All parts except the last are complete sentences
                for sentence in parts[:-1]:
                    sentence = sentence.strip()
                    if sentence:
                        yield sentence
                # Keep the incomplete part in the buffer
                buffer = parts[-1] if parts else ""

            # Yield any remaining text in the buffer
            if buffer.strip():
                yield buffer.strip()

            # Persist the turn in internal history (only when using it)
            full_text = full_response.strip()
            if history is None and full_text:
                self._history.append({"role": "user", "content": prompt})
                self._history.append({"role": "assistant", "content": full_text})

        except Exception as e:
            raise RuntimeError(f"Gemini streaming API error: {e}") from e

    def search_and_answer(self, query: str) -> str:
        """
        Perform a grounded Google Search query via Gemini.

        Uses Gemini's built-in google_search tool so the model can fetch
        live information (weather, news, stock prices, etc.) before answering.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=query,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    tools=[{"google_search": {}}]
                )
            )
            reply = response.text.strip()
        except Exception as e:
            # Fall back to regular chat if grounded search fails
            print(f"⚠️  Grounded search failed, falling back to regular chat: {e}")
            return self.chat(query)

        if not reply:
            return self.chat(query)

        return reply

    def reset_history(self) -> None:
        """Clear the conversation history to start a fresh session."""
        self._history.clear()

    @property
    def history(self) -> list[dict[str, str]]:
        """Return a copy of the current conversation history."""
        return list(self._history)

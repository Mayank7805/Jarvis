"""
skills/clipboard.py — Clipboard Skill

Read and write the system clipboard using ``pyperclip``.

Dependencies:
    pip install pyperclip
"""

import pyperclip

from skills.base_skill import BaseSkill


class ClipboardSkill(BaseSkill):
    """Reads and sets the system clipboard contents."""

    @property
    def name(self) -> str:
        return "Clipboard"

    @property
    def keywords(self) -> list[str]:
        return ["clipboard", "copy that", "paste", "what did i copy"]

    def execute(self, query: str) -> str:
        """Route to read or write based on query intent."""
        q = query.lower()

        # Read clipboard
        if any(phrase in q for phrase in (
            "what did i copy", "clipboard", "paste",
            "read clipboard", "show clipboard", "what's copied",
            "what is copied", "what's in clipboard", "what is in clipboard",
        )):
            return self._get_clipboard()

        # Write clipboard — "copy that" or "copy <text>"
        if "copy" in q:
            text = self._extract_copy_text(query)
            if text:
                return self._set_clipboard(text)

        # Default to reading
        return self._get_clipboard()

    # ── Core Operations ────────────────────────

    @staticmethod
    def _get_clipboard() -> str:
        """Read current clipboard text."""
        try:
            content = pyperclip.paste()
            if not content or not content.strip():
                return "The clipboard is empty."

            # Truncate for voice readout if very long
            if len(content) > 200:
                preview = content[:200].strip()
                return f"Your clipboard contains: {preview} ... and more. It's quite long."

            return f"Your clipboard contains: {content}"

        except Exception as e:
            return f"Sorry, I couldn't read the clipboard. Error: {e}"

    @staticmethod
    def _set_clipboard(text: str) -> str:
        """Copy text to the clipboard."""
        try:
            pyperclip.copy(text)
            # Truncate confirmation for voice
            preview = text[:80] if len(text) > 80 else text
            return f"Copied to clipboard: {preview}"
        except Exception as e:
            return f"Sorry, I couldn't copy to the clipboard. Error: {e}"

    # ── Helpers ─────────────────────────────────

    @staticmethod
    def _extract_copy_text(query: str) -> str:
        """
        Extract text to copy from the query.

        "copy hello world"   → "hello world"
        "copy that"          → "" (means read, not write)
        """
        q = query.strip()
        q_lower = q.lower()

        # "copy that" / "copy this" = read operation, not write
        if q_lower in ("copy that", "copy this"):
            return ""

        for prefix in ("copy ", "copy this: ", "copy that: "):
            if q_lower.startswith(prefix):
                return q[len(prefix):].strip()

        return ""

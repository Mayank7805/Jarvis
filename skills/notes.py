"""
skills/notes.py — Notes Skill

Allows the user to dictate quick notes which are persisted to disk
with timestamps, and recall their most recent notes.

Storage: ``data/notes.txt`` (created automatically if missing).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from skills.base_skill import BaseSkill

if TYPE_CHECKING:
    from core.memory import JarvisMemory


# Default notes file relative to project root
NOTES_FILE = Path("data") / "notes.txt"


class NotesSkill(BaseSkill):
    """Takes and reads timestamped notes stored in a local text file."""

    # Phrases that indicate the user wants to READ notes
    READ_PHRASES: list[str] = [
        "read notes", "show notes", "what are my notes",
        "read my notes", "show my notes", "i do not see",
        "see notes", "see my notes", "list notes", "list my notes",
    ]

    # Phrases that indicate the user wants to WRITE a note
    WRITE_PHRASES: list[str] = [
        "note down", "note", "remember", "write down",
        "remind me to", "take a note", "make a note", "add note",
    ]

    def __init__(self, notes_file: str | Path | None = None) -> None:
        self._notes_file = Path(notes_file) if notes_file else NOTES_FILE
        # Ensure parent directory exists
        self._notes_file.parent.mkdir(parents=True, exist_ok=True)
        self._memory: JarvisMemory | None = None

    def set_memory(self, memory: JarvisMemory) -> None:
        """Inject the long-term memory instance for explicit fact storage."""
        self._memory = memory

    @property
    def name(self) -> str:
        return "Notes"

    @property
    def keywords(self) -> list[str]:
        return self.READ_PHRASES + self.WRITE_PHRASES

    def can_handle(self, query: str) -> bool:
        """Match if the query contains any read or write phrase."""
        q = query.lower()
        return any(phrase in q for phrase in self.READ_PHRASES + self.WRITE_PHRASES)

    def execute(self, query: str) -> str:
        """Decide whether to read or write a note based on the query."""
        q = query.lower()

        # Check READ phrases first
        if any(phrase in q for phrase in self.READ_PHRASES):
            return self._read_notes()

        # Check WRITE phrases — extract the note body
        if any(phrase in q for phrase in self.WRITE_PHRASES):
            note_text = self._extract_note_body(query)
            if note_text:
                # Also save to vector memory for semantic recall
                if self._memory is not None and any(
                    kw in q for kw in ("remember", "remind")
                ):
                    try:
                        self._memory.remember("note", note_text)
                    except Exception as e:
                        print(f"⚠️  Failed to save note to memory: {e}")
                return self._add_note(note_text)

        return "Would you like me to add a new note or read your existing notes?"

    # ── Core Operations ────────────────────────

    def _add_note(self, text: str) -> str:
        """Append a timestamped note to the notes file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"[{timestamp}] {text}\n"

        try:
            with open(self._notes_file, "a", encoding="utf-8") as f:
                f.write(entry)
            return f"Got it. I've noted down: {text}"
        except Exception as e:
            return f"Sorry, I couldn't save that note. Error: {e}"

    def _read_notes(self, count: int = 5) -> str:
        """Read and return the last *count* notes."""
        if not self._notes_file.exists():
            return "You don't have any notes yet."

        try:
            with open(self._notes_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            return f"Sorry, I couldn't read your notes. Error: {e}"

        if not lines:
            return "Your notes file is empty."

        recent = lines[-count:]
        # Format as a clean numbered list for voice
        numbered = []
        for i, line in enumerate(recent, start=1):
            # Strip timestamp bracket if present: "[2025-05-30 14:30] Buy groceries" → "Buy groceries"
            body = line
            if line.startswith("[") and "]" in line:
                body = line[line.index("]") + 1:].strip()
            numbered.append(f"{i}. {body}")

        return "Your notes: " + " ".join(numbered)

    # ── Helpers ─────────────────────────────────

    @staticmethod
    def _extract_note_body(query: str) -> str:
        """
        Strip trigger phrases to isolate the note content.

        Examples:
            "note remember to buy milk"      → "remember to buy milk"
            "remind me to call the doctor"   → "call the doctor"
            "write down meeting at 3 PM"     → "meeting at 3 PM"
        """
        q = query.strip()

        # Remove leading trigger phrases (order matters — longest first)
        prefixes = [
            "remind me to ", "remember this ", "write down ",
            "note down ", "take a note ", "make a note ",
            "note ", "add note ",
        ]
        q_lower = q.lower()
        for prefix in prefixes:
            if q_lower.startswith(prefix):
                q = q[len(prefix):]
                break

        return q.strip()

    @staticmethod
    def _humanize_note(line: str) -> str:
        """
        Convert a stored note line into a voice-friendly string.

        Input:  "[2025-05-30 14:30] Buy groceries"
        Output: "On May 30 at 2:30 PM, Buy groceries"
        """
        try:
            if line.startswith("[") and "]" in line:
                bracket_end = line.index("]")
                ts_str = line[1:bracket_end]
                body = line[bracket_end + 2:]
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
                human_ts = dt.strftime("%B %d at %I:%M %p")
                return f"On {human_ts}, {body}"
        except (ValueError, IndexError):
            pass
        return line

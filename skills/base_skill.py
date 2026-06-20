"""
skills/base_skill.py — Abstract Base Skill

Every Jarvis skill inherits from BaseSkill.  The SkillManager uses
``can_handle()`` to decide which skill should process a query and then
calls ``execute()`` on the first match.

Subclasses MUST implement:
    • name       – human-readable skill name (property)
    • keywords   – list of trigger words/phrases (property)
    • execute()  – run the skill and return a voice-friendly string
"""

from abc import ABC, abstractmethod


class BaseSkill(ABC):
    """
    Abstract base class for every Jarvis skill.

    Provides a default keyword-matching ``can_handle()`` that most skills
    can use as-is.  Skills with more nuanced matching (e.g. the calculator)
    should override ``can_handle()`` directly.
    """

    # ── Required properties ────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this skill (e.g. 'System Control')."""
        ...

    @property
    @abstractmethod
    def keywords(self) -> list[str]:
        """Trigger words/phrases that indicate this skill should handle the query."""
        ...

    # ── Matching ───────────────────────────────

    def can_handle(self, query: str) -> bool:
        """
        Return True if this skill should handle the given query.

        Default implementation: checks if ANY keyword appears in the
        lowercased query.  Override for smarter matching.
        """
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.keywords)

    # ── Execution ──────────────────────────────

    @abstractmethod
    def execute(self, query: str) -> str:
        """
        Process the query and return a voice-friendly response string.

        Must be implemented by every concrete skill.
        No markdown, no bullets — plain conversational text only.
        """
        ...

    # ── Repr ───────────────────────────────────

    def __repr__(self) -> str:
        return f"<Skill: {self.name}>"

"""
skills/skill_manager.py — Skill Auto-Discovery & Routing

Scans the ``skills/`` package for all concrete ``BaseSkill`` subclasses,
instantiates them, and provides a single entry-point —
``route_to_skill(query)`` — that finds the first matching skill and
executes it.

Files explicitly excluded from auto-discovery:
    base_skill.py, skill_manager.py, weather.py, news.py, __init__.py
"""

import importlib
import inspect
import pkgutil
from pathlib import Path

from skills.base_skill import BaseSkill


# Files that predate the BaseSkill pattern or are infrastructure
_SKIP_MODULES: set[str] = {
    "base_skill",
    "skill_manager",
    "weather",
    "news",
    "world_briefing",  # called directly by router + /world-data endpoint
    "app_launcher",  # replaced by AgentExecutor (Gemini function calling)
    "__init__",
}


class SkillManager:
    """
    Auto-discovers and manages all BaseSkill subclasses.

    On init, imports every Python module in the ``skills/`` package
    (minus the skip list), finds classes inheriting ``BaseSkill``,
    and stores one instance of each.
    """

    def __init__(self) -> None:
        self._skills: list[BaseSkill] = []
        self._discover_skills()

    # ── Public API ─────────────────────────────

    def route_to_skill(self, query: str) -> str | None:
        """
        Try each registered skill's ``can_handle()``; run the first match.

        Args:
            query: The user's transcribed speech text.

        Returns:
            The skill's response string, or ``None`` if no skill matched
            (so the caller can fall through to the LLM).
        """
        for skill in self._skills:
            try:
                if skill.can_handle(query):
                    print(f"   [+] Skill matched: {skill.name}")
                    result = skill.execute(query)
                    # A skill may return None to signal "matched but can't process"
                    if result is not None:
                        print(f"   [OK] {skill.name} responded.")
                        return result
            except Exception as e:
                print(f"   [!] Skill '{skill.name}' error: {e}")
                continue

        return None  # No skill matched — fall through to LLM

    @property
    def loaded_skills(self) -> list[str]:
        """Return names of all loaded skills."""
        return [s.name for s in self._skills]

    def set_memory(self, memory) -> None:
        """
        Pass the JarvisMemory instance to any skill that supports it.

        Uses duck-typing: if a skill has a ``set_memory`` method, it gets called.
        """
        for skill in self._skills:
            if hasattr(skill, "set_memory") and callable(skill.set_memory):
                try:
                    skill.set_memory(memory)
                    print(f"   [+] Memory linked to skill: {skill.name}")
                except Exception as e:
                    print(f"   [!] Failed to set memory on {skill.name}: {e}")

    # ── Auto-discovery ─────────────────────────

    def _discover_skills(self) -> None:
        """
        Dynamically import all modules in the ``skills`` package and
        collect concrete ``BaseSkill`` subclasses.
        """
        skills_dir = Path(__file__).resolve().parent

        for module_info in pkgutil.iter_modules([str(skills_dir)]):
            if module_info.name in _SKIP_MODULES:
                continue

            try:
                module = importlib.import_module(f"skills.{module_info.name}")
            except Exception as e:
                print(f"   [!] Failed to import skills.{module_info.name}: {e}")
                continue

            # Find all BaseSkill subclasses defined in this module
            for _attr_name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseSkill)
                    and obj is not BaseSkill
                    and not inspect.isabstract(obj)
                ):
                    try:
                        instance = obj()
                        self._skills.append(instance)
                        print(f"   [+] Loaded skill: {instance.name}")
                    except Exception as e:
                        print(f"   [!] Failed to instantiate {obj.__name__}: {e}")

        print(f"[Skills] SkillManager ready -- {len(self._skills)} skill(s) loaded.")

"""
skills/calculator.py — Calculator Skill

Evaluates math expressions safely using ``sympy`` (no raw ``eval``).
Converts natural-language math ("5 plus 3") to symbolic expressions
and solves them.

Dependencies:
    pip install sympy

Smart "what is" guard:
    The keyword "what is" only triggers this skill when the query also
    contains digits OR math words (plus, minus, times, etc.).
    Pure "what is X" without numbers → returns False, falls through to LLM.
"""

import re

from skills.base_skill import BaseSkill


# Words that confirm a "what is" query is actually math
MATH_WORDS: set[str] = {
    "plus", "minus", "times", "divided", "multiply", "multiplied",
    "percent", "percentage", "square root", "sqrt", "power",
    "raised", "modulo", "mod", "factorial",
}


class CalculatorSkill(BaseSkill):
    """Evaluates math expressions safely using sympy."""

    @property
    def name(self) -> str:
        return "Calculator"

    @property
    def keywords(self) -> list[str]:
        return [
            "calculate", "what is", "math",
            "plus", "minus", "times", "divided",
            "percent", "square root",
        ]

    def can_handle(self, query: str) -> bool:
        """
        Smart matching: "what is" only triggers when the query also
        contains numbers or math-specific words.

        "what is 5 plus 3"    → True  (has digits + math word)
        "what is the time"    → False (no digits, no math word)
        "calculate 2 * 5"     → True  (explicit "calculate" keyword)
        "square root of 144"  → True  (math word keyword)
        """
        q = query.lower()

        # "what is" requires extra validation
        if "what is" in q:
            has_digits = bool(re.search(r"\d", q))
            has_math_word = any(mw in q for mw in MATH_WORDS)
            return has_digits or has_math_word

        # All other keywords are unambiguous math triggers
        other_keywords = [kw for kw in self.keywords if kw != "what is"]
        return any(kw in q for kw in other_keywords)

    def execute(self, query: str) -> str:
        """Parse the math expression and evaluate it."""
        expression = self._nl_to_expression(query)
        if not expression:
            return "I couldn't find a math expression in that. Try saying calculate 5 plus 3."

        return self._evaluate(expression)

    # ── Evaluation ─────────────────────────────

    @staticmethod
    def _evaluate(expression: str) -> str:
        """
        Evaluate a math expression string safely using sympy.

        Returns a voice-friendly result string.
        """
        try:
            from sympy import sympify, N, SympifyError
            from sympy import sqrt, pi, E, oo  # noqa: F401  — needed in namespace

            # sympify safely parses the expression (no eval)
            result = sympify(expression)

            # Evaluate to a numeric value
            numeric = float(N(result))

            # Format nicely for voice
            # If it's an integer, drop the decimal
            if numeric == int(numeric):
                answer = str(int(numeric))
            else:
                # Round to 6 decimal places for voice readout
                answer = str(round(numeric, 6))

            return f"The answer is {answer}."

        except (SympifyError, TypeError, ValueError):
            return f"Sorry, I couldn't calculate that expression: {expression}"
        except Exception as e:
            return f"Math error: {e}"

    # ── Natural Language → Expression ──────────

    @staticmethod
    def _nl_to_expression(query: str) -> str:
        """
        Convert natural-language math to a sympy-compatible expression.

        Examples:
            "what is 5 plus 3"           → "5 + 3"
            "calculate 10 divided by 2"  → "10 / 2"
            "square root of 144"         → "sqrt(144)"
            "2 raised to the power 8"    → "2 ** 8"
            "15 percent of 200"          → "(15/100) * 200"
            "what is 50% of 300"         → "(50/100) * 300"
        """
        q = query.lower().strip()

        # Remove trigger phrases
        for prefix in (
            "calculate ", "compute ", "solve ", "evaluate ",
            "what is ", "what's ", "how much is ", "math ",
        ):
            if q.startswith(prefix):
                q = q[len(prefix):]

        # Remove trailing filler
        for suffix in (" please", " for me", " equals"):
            if q.endswith(suffix):
                q = q[: -len(suffix)]

        q = q.strip()

        # ── Percentage: "X percent of Y" → "(X/100) * Y"
        pct_match = re.match(r"(\d+(?:\.\d+)?)\s*(?:percent|%)\s*(?:of)\s*(\d+(?:\.\d+)?)", q)
        if pct_match:
            return f"({pct_match.group(1)}/100) * {pct_match.group(2)}"

        # ── Square root: "square root of X" or "sqrt X"
        sqrt_match = re.match(r"(?:square\s*root\s*(?:of)?|sqrt)\s*(\d+(?:\.\d+)?)", q)
        if sqrt_match:
            return f"sqrt({sqrt_match.group(1)})"

        # ── Power: "X raised to the power Y" / "X to the power Y" / "X power Y"
        pow_match = re.match(
            r"(\d+(?:\.\d+)?)\s*(?:raised\s+to\s+(?:the\s+)?power\s+(?:of\s+)?|"
            r"to\s+the\s+power\s+(?:of\s+)?|power\s+)(\d+(?:\.\d+)?)", q
        )
        if pow_match:
            return f"{pow_match.group(1)} ** {pow_match.group(2)}"

        # ── Word replacements for arithmetic
        replacements = [
            (r"\bplus\b", "+"),
            (r"\bminus\b", "-"),
            (r"\btimes\b", "*"),
            (r"\bmultiplied\s+by\b", "*"),
            (r"\bmultiply\s+by\b", "*"),
            (r"\bmultiply\b", "*"),
            (r"\bdivided\s+by\b", "/"),
            (r"\bover\b", "/"),
            (r"\bmod\b", "%"),
            (r"\bmodulo\b", "%"),
            (r"\bx\b", "*"),           # "5 x 3" → "5 * 3"
            (r"\binto\b", "*"),         # "5 into 3" → "5 * 3"
        ]
        for pattern, replacement in replacements:
            q = re.sub(pattern, replacement, q)

        # Remove any remaining non-math characters (keep digits, operators, parens, dots)
        q = re.sub(r"[^0-9+\-*/().%\s]", "", q).strip()

        # Collapse whitespace
        q = re.sub(r"\s+", " ", q).strip()

        return q if q else ""

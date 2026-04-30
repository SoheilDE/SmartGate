import re
from enum import Enum


class Intent(str, Enum):
    CONVERSATIONAL = "conversational"  # greetings, small talk, acknowledgements
    FACTUAL = "factual"                # simple lookup — "What is X?"
    ANALYTICAL = "analytical"          # reasoning, explanation, comparison
    CODE = "code"                      # generation, debugging, review, refactor
    MATH = "math"                      # calculation, proofs, equations
    CREATIVE = "creative"              # stories, emails, copy, brainstorming


# Score modifier applied on top of complexity score — negative pulls toward fast model
INTENT_MODIFIER: dict[Intent, float] = {
    Intent.CONVERSATIONAL: -0.30,
    Intent.FACTUAL:        -0.10,
    Intent.CREATIVE:        0.00,
    Intent.MATH:            0.15,
    Intent.ANALYTICAL:      0.15,
    Intent.CODE:            0.20,
}

_CONVERSATIONAL_RE = re.compile(
    r"^(hi+|hello|hey|thanks|thank you|ok|okay|sure|great|cool|"
    r"bye|goodbye|how are you|nice to meet you|"
    r"good (morning|afternoon|evening|night))[\s!.,?]*$"
)

_CODE_PATTERNS = [
    r"```",
    r"\b(write|generate|create|build|implement|code|script|program|algorithm)\b",
    r"\b(bug|error|exception|traceback|stack trace|debug|fix this|broken|failing|crash)\b",
    r"\b(refactor|optimize|review|lint|unittest|test this)\b",
    r"\b(function|class|method|endpoint|query|schema|api|library|module)\b",
]

_MATH_PATTERNS = [
    r"\b(calculate|compute|solve|simplify|integrate|differentiate|derive)\b",
    r"\b(equation|matrix|probability|statistics|algebra|geometry|calculus|theorem|proof)\b",
    r"\d+\s*[\+\-\*\/\^]\s*\d+",   # arithmetic expressions like 3 + 4
]

_ANALYTICAL_PATTERNS = [
    r"\b(explain|analyze|analyse|compare|evaluate|assess|discuss|summarize|review)\b",
    r"\b(why|how does|what are the (reasons|causes|effects|implications|tradeoffs?))\b",
    r"\b(pros and cons|advantages|disadvantages|design|architect|strategy|plan)\b",
    r"\b(deep dive|walk (me )?through|step[- ]by[- ]step|in detail)\b",
]

_FACTUAL_PATTERNS = [
    r"\b(what is|what are|what was|who is|who was|where is|when (was|did|is))\b",
    r"\bdefine\b",
    r"\bwhat does .+ (mean|stand for)\b",
    r"\blist (the |some |a few )?\w+",
]

_CREATIVE_PATTERNS = [
    r"\b(write (a |an )?(story|poem|essay|email|letter|blog|article|tweet|caption|slogan|bio|summary))\b",
    r"\b(creative|fiction|narrative|imagine|brainstorm|ideas? for|suggest)\b",
]


def classify(prompt: str) -> tuple[Intent, float]:
    """Return (intent, score_modifier) for the prompt."""
    text = prompt.lower().strip()

    if _CONVERSATIONAL_RE.match(text):
        return Intent.CONVERSATIONAL, INTENT_MODIFIER[Intent.CONVERSATIONAL]

    pattern_scores: dict[Intent, int] = {
        Intent.CODE:       sum(1 for p in _CODE_PATTERNS if re.search(p, text)),
        Intent.MATH:       sum(1 for p in _MATH_PATTERNS if re.search(p, text)),
        Intent.ANALYTICAL: sum(1 for p in _ANALYTICAL_PATTERNS if re.search(p, text)),
        Intent.FACTUAL:    sum(1 for p in _FACTUAL_PATTERNS if re.search(p, text)),
        Intent.CREATIVE:   sum(1 for p in _CREATIVE_PATTERNS if re.search(p, text)),
    }

    best = max(pattern_scores, key=lambda k: pattern_scores[k])
    if pattern_scores[best] == 0:
        return Intent.ANALYTICAL, INTENT_MODIFIER[Intent.ANALYTICAL]

    return best, INTENT_MODIFIER[best]

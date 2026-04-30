import re

_COMPLEXITY_KEYWORDS = [
    "explain", "compare", "analyze", "analyse", "debug", "step by step",
    "write code", "in detail", "why", "how does", "difference between",
    "pros and cons", "evaluate", "design", "architect", "implement",
    "walk me through", "deep dive", "elaborate", "summarize",
]

_TOKEN_CEILING = 500  # prompts above this are treated as max complexity


def score(prompt: str) -> float:
    text = prompt.lower()
    tokens = text.split()
    token_count = len(tokens)

    # Signal 1: length (normalized, capped at ceiling)
    length_signal = min(token_count / _TOKEN_CEILING, 1.0)

    # Signal 2: complexity keyword density
    keyword_hits = sum(1 for kw in _COMPLEXITY_KEYWORDS if kw in text)
    keyword_signal = min(keyword_hits / 3, 1.0)  # 3+ keywords → maxed

    # Signal 3: multi-part questions
    question_marks = text.count("?")
    multi_part_phrases = len(re.findall(r"\b(and also|additionally|furthermore|also)\b", text))
    multipart_signal = min((question_marks + multi_part_phrases) / 3, 1.0)

    # Weighted combination
    raw = 0.4 * length_signal + 0.4 * keyword_signal + 0.2 * multipart_signal
    return round(min(raw, 1.0), 4)

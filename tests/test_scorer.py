import pytest
from app.routing.complexity_scorer import score


# ── Bounds ────────────────────────────────────────────────────────────────────

def test_score_always_in_bounds():
    assert 0.0 <= score("hello") <= 1.0
    assert 0.0 <= score("x " * 1000) <= 1.0


# ── Simple / factual prompts → low score ─────────────────────────────────────

def test_greeting_is_low():
    assert score("hi") < 0.3

def test_simple_factual_is_low():
    assert score("what is Python?") < 0.3

def test_simple_definition_is_low():
    assert score("define recursion") < 0.3

def test_brevity_signal_pulls_score_down():
    assert score("briefly, what is machine learning?") < score("what is machine learning?")

def test_brevity_on_complex_prompt_reduces_score():
    base = score("explain how transformers work in detail")
    brief = score("briefly explain how transformers work")
    assert brief < base

def test_yes_or_no_is_low():
    assert score("yes or no: is Python interpreted?") < 0.3


# ── Complex prompts → high score ─────────────────────────────────────────────

def test_deep_analytical_prompt_is_high():
    prompt = (
        "Explain and compare transformer attention mechanisms step by step in detail. "
        "Analyze the differences between multi-head attention and cross-attention. "
        "Why does self-attention work and how does it scale?"
    )
    assert score(prompt) >= 0.6

def test_code_generation_prompt_is_high():
    assert score("write a function to implement binary search in Python") >= 0.5

def test_code_block_in_prompt_is_high():
    prompt = "debug this code:\n```python\ndef foo():\n    return 1/0\n```"
    assert score(prompt) >= 0.5

def test_implementation_with_constraints_is_high():
    prompt = (
        "Implement a rate limiter using the token bucket algorithm. "
        "It must support concurrent access, ensure thread safety, "
        "and also handle burst traffic correctly."
    )
    assert score(prompt) >= 0.6

def test_technical_domain_raises_score():
    low = score("explain caching")
    high = score("explain cache invalidation in distributed systems with replication")
    assert high > low


# ── Ordering: complex > simple ────────────────────────────────────────────────

def test_complex_beats_simple():
    assert score("explain the theory of relativity in detail") > score("what time is it")

def test_multi_requirement_beats_single():
    single = score("write a login function")
    multi = score(
        "write a login function that must validate the email format, "
        "ensure the password is hashed, and also log failed attempts"
    )
    assert multi > single

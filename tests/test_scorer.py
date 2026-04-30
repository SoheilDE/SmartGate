import pytest
from app.routing.complexity_scorer import score


def test_simple_prompt_is_low():
    assert score("hi") < 0.3


def test_long_complex_prompt_is_high():
    prompt = (
        "Explain and compare transformer attention mechanisms step by step in detail. "
        "Analyze the differences between multi-head attention and cross-attention. "
        "Why does self-attention work and how does it scale? "
        "Additionally, debug this code and walk me through the architecture."
    )
    assert score(prompt) >= 0.6


def test_keyword_signal():
    assert score("explain the theory of relativity in detail") > score("what time is it")


def test_multipart_signal():
    assert score("what is X? and also what is Y? and also Z?") > score("what is X")


def test_score_bounds():
    assert 0.0 <= score("hello world") <= 1.0
    assert 0.0 <= score("x " * 1000) <= 1.0

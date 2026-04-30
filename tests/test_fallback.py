import pytest
from app.fallback.validator import validate


VALID = {
    "choices": [{"message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
}


def test_valid_response():
    assert validate(VALID) is True


def test_missing_choices():
    assert validate({**VALID, "choices": []}) is False


def test_missing_content():
    bad = {"choices": [{"message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}], "usage": {}}
    assert validate(bad) is False


def test_finish_reason_error():
    bad = {**VALID, "choices": [{"message": {"role": "assistant", "content": "x"}, "finish_reason": "error"}]}
    assert validate(bad) is False


def test_missing_usage():
    bad = {"choices": VALID["choices"]}
    assert validate(bad) is False


def test_non_dict_input():
    assert validate(None) is False
    assert validate("string") is False

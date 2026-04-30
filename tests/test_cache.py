import pytest
from unittest.mock import MagicMock, patch


def test_lookup_returns_none_on_miss():
    mock_client = MagicMock()
    mock_client.search.return_value = []

    with patch("app.cache.semantic_cache._client", return_value=mock_client), \
         patch("app.cache.semantic_cache.embed", return_value=[0.0] * 384):
        from app.cache.semantic_cache import lookup
        result = lookup("some prompt")
    assert result is None


def test_lookup_returns_cached_on_hit():
    scored = MagicMock()
    scored.score = 0.99
    scored.payload = {"response": '{"choices":[]}'}

    mock_client = MagicMock()
    mock_client.search.return_value = [scored]

    with patch("app.cache.semantic_cache._client", return_value=mock_client), \
         patch("app.cache.semantic_cache.embed", return_value=[0.0] * 384):
        from app.cache.semantic_cache import lookup
        result = lookup("some prompt")
    assert result == '{"choices":[]}'


def test_store_calls_upsert():
    mock_client = MagicMock()

    with patch("app.cache.semantic_cache._client", return_value=mock_client), \
         patch("app.cache.semantic_cache.embed", return_value=[0.1] * 384):
        from app.cache.semantic_cache import store
        store("prompt", "response")
    mock_client.upsert.assert_called_once()

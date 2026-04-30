import pytest
from unittest.mock import patch, MagicMock
from app.routing.intent_classifier import classify, Intent
from app.routing.model_router import select_model, _match_keyword_rule


# ── Intent classifier ─────────────────────────────────────────────────────────

def test_greeting_is_conversational():
    intent, modifier = classify("hi")
    assert intent == Intent.CONVERSATIONAL
    assert modifier < 0

def test_what_is_is_factual():
    intent, _ = classify("what is Python?")
    assert intent == Intent.FACTUAL

def test_code_prompt_is_code():
    intent, modifier = classify("write a function to sort a list in Python")
    assert intent == Intent.CODE
    assert modifier > 0

def test_debug_prompt_is_code():
    intent, _ = classify("debug this error: IndexError in my loop")
    assert intent == Intent.CODE

def test_math_prompt_is_math():
    intent, _ = classify("solve the equation 3x + 5 = 20")
    assert intent == Intent.MATH

def test_analytical_prompt():
    intent, modifier = classify("explain why microservices are better than monoliths")
    assert intent == Intent.ANALYTICAL
    assert modifier > 0

def test_creative_prompt():
    intent, _ = classify("write a short story about a robot learning to paint")
    assert intent == Intent.CREATIVE

def test_code_modifier_is_highest():
    _, code_mod = classify("implement a binary search tree")
    _, factual_mod = classify("what is a binary search tree")
    assert code_mod > factual_mod


# ── Model router ──────────────────────────────────────────────────────────────

def _mock_gateway(threshold=0.6):
    gw = MagicMock()
    gw.complexity_threshold.return_value = threshold
    gw.fast_model.return_value = {"model": "gpt-3.5-turbo", "base_url": "http://fast"}
    gw.powerful_model.return_value = {"model": "gpt-4", "base_url": "http://powerful"}
    return gw


@patch("app.routing.model_router.gateway_config")
@patch("app.routing.model_router.settings")
def test_simple_routes_to_fast(mock_settings, mock_gw):
    mock_gw.complexity_threshold.return_value = 0.6
    mock_gw.fast_model.return_value = {"model": "gpt-3.5-turbo", "base_url": "http://fast"}
    mock_gw.powerful_model.return_value = {"model": "gpt-4", "base_url": "http://powerful"}
    mock_settings.fast_model = "gpt-3.5-turbo"
    mock_settings.fast_model_base_url = "http://fast"
    mock_settings.fast_model_api_key = "key"
    mock_settings.powerful_model = "gpt-4"
    mock_settings.powerful_model_base_url = "http://powerful"
    mock_settings.powerful_model_api_key = "key"

    model, score, reason = select_model("hi")
    assert model.model == "gpt-3.5-turbo"
    assert "conversational" in reason


@patch("app.routing.model_router.gateway_config")
@patch("app.routing.model_router.settings")
def test_complex_routes_to_powerful(mock_settings, mock_gw):
    mock_gw.complexity_threshold.return_value = 0.6
    mock_gw.fast_model.return_value = {"model": "gpt-3.5-turbo", "base_url": "http://fast"}
    mock_gw.powerful_model.return_value = {"model": "gpt-4", "base_url": "http://powerful"}
    mock_settings.fast_model = "gpt-3.5-turbo"
    mock_settings.fast_model_base_url = "http://fast"
    mock_settings.fast_model_api_key = "key"
    mock_settings.powerful_model = "gpt-4"
    mock_settings.powerful_model_base_url = "http://powerful"
    mock_settings.powerful_model_api_key = "key"

    prompt = (
        "implement a distributed rate limiter using the token bucket algorithm, "
        "ensure thread safety, must handle burst traffic and also log all failures"
    )
    model, score, reason = select_model(prompt)
    assert model.model == "gpt-4"
    assert "powerful" in reason


@patch("app.routing.model_router.gateway_config")
@patch("app.routing.model_router.settings")
def test_force_powerful_overrides(mock_settings, mock_gw):
    mock_gw.complexity_threshold.return_value = 0.6
    mock_gw.fast_model.return_value = {"model": "gpt-3.5-turbo", "base_url": "http://fast"}
    mock_gw.powerful_model.return_value = {"model": "gpt-4", "base_url": "http://powerful"}
    mock_settings.fast_model = "gpt-3.5-turbo"
    mock_settings.fast_model_base_url = "http://fast"
    mock_settings.fast_model_api_key = "key"
    mock_settings.powerful_model = "gpt-4"
    mock_settings.powerful_model_base_url = "http://powerful"
    mock_settings.powerful_model_api_key = "key"

    model, _, _ = select_model("hi", force_powerful=True)
    assert model.model == "gpt-4"


@patch("app.routing.model_router.gateway_config")
@patch("app.routing.model_router.settings")
def test_conversation_depth_biases_toward_powerful(mock_settings, mock_gw):
    mock_gw.complexity_threshold.return_value = 0.6
    mock_gw.fast_model.return_value = {"model": "gpt-3.5-turbo", "base_url": "http://fast"}
    mock_gw.powerful_model.return_value = {"model": "gpt-4", "base_url": "http://powerful"}
    mock_settings.fast_model = "gpt-3.5-turbo"
    mock_settings.fast_model_base_url = "http://fast"
    mock_settings.fast_model_api_key = "key"
    mock_settings.powerful_model = "gpt-4"
    mock_settings.powerful_model_base_url = "http://powerful"
    mock_settings.powerful_model_api_key = "key"

    messages_short = [{"role": "user", "content": "hi"}]
    messages_long = [{"role": "user", "content": "hi"}] * 6

    _, score_short, _ = select_model("explain caching", messages_short)
    _, score_long, _ = select_model("explain caching", messages_long)
    assert score_long > score_short


@patch("app.routing.model_router.gateway_config")
@patch("app.routing.model_router.settings")
def test_routing_reason_contains_all_fields(mock_settings, mock_gw):
    mock_gw.complexity_threshold.return_value = 0.6
    mock_gw.fast_model.return_value = {"model": "gpt-3.5-turbo", "base_url": "http://fast"}
    mock_gw.powerful_model.return_value = {"model": "gpt-4", "base_url": "http://powerful"}
    mock_settings.fast_model = "gpt-3.5-turbo"
    mock_settings.fast_model_base_url = "http://fast"
    mock_settings.fast_model_api_key = "key"
    mock_settings.powerful_model = "gpt-4"
    mock_settings.powerful_model_base_url = "http://powerful"
    mock_settings.powerful_model_api_key = "key"

    _, _, reason = select_model("explain Python")
    for field in ("intent=", "base=", "intent_mod=", "depth_mod=", "final=", "threshold=", "tier="):
        assert field in reason


# ── Keyword rule matching ─────────────────────────────────────────────────────

def test_keyword_any_match():
    rule = {"keywords": ["legal", "GDPR", "compliance"], "tier": "powerful"}
    assert _match_keyword_rule("we need GDPR compliance", rule)

def test_keyword_any_no_match():
    rule = {"keywords": ["legal", "GDPR"], "tier": "powerful"}
    assert not _match_keyword_rule("explain caching", rule)

def test_keyword_case_insensitive():
    rule = {"keywords": ["Python"], "tier": "code"}
    assert _match_keyword_rule("i want to learn python", rule)

def test_keyword_all_match():
    rule = {"keywords": ["security", "audit"], "tier": "powerful", "match": "all"}
    assert _match_keyword_rule("run a security audit", rule)

def test_keyword_all_partial_no_match():
    rule = {"keywords": ["security", "audit"], "tier": "powerful", "match": "all"}
    assert not _match_keyword_rule("run a security check", rule)

def test_keyword_empty_rule_no_match():
    rule = {"keywords": [], "tier": "powerful"}
    assert not _match_keyword_rule("any prompt", rule)


# ── Keyword routing priority in select_model ─────────────────────────────────

def _mock_settings_and_gw(mock_settings, mock_gw, keyword_rules=None, intent_rules=None):
    mock_gw.complexity_threshold.return_value = 0.6
    mock_gw.keyword_routing.return_value = keyword_rules or []
    mock_gw.intent_routing.return_value = intent_rules or {}
    mock_gw.model_by_tier.side_effect = lambda tier: {
        "fast":     {"model": "gpt-3.5-turbo", "base_url": "http://fast",     "api_key_env": "FAST_KEY"},
        "powerful": {"model": "gpt-4",          "base_url": "http://powerful", "api_key_env": "POWERFUL_KEY"},
        "legal":    {"model": "gpt-4-legal",    "base_url": "http://legal",    "api_key_env": "POWERFUL_KEY"},
    }.get(tier, {"model": "gpt-4", "base_url": "http://powerful", "api_key_env": "POWERFUL_KEY"})
    mock_settings.powerful_model = "gpt-4"
    mock_settings.powerful_model_base_url = "http://powerful"
    mock_settings.powerful_model_api_key = "key"


@patch("app.routing.model_router.gateway_config")
@patch("app.routing.model_router.settings")
def test_keyword_rule_overrides_intent_rule(mock_settings, mock_gw):
    _mock_settings_and_gw(
        mock_settings, mock_gw,
        keyword_rules=[{"keywords": ["legal"], "tier": "powerful"}],
        intent_rules={"factual": "fast"},
    )
    # "what is legal compliance" would be factual → fast, but keyword hits first
    _, _, reason = select_model("what is legal compliance")
    assert "keyword_rule" in reason
    assert "matched_keywords" in reason


@patch("app.routing.model_router.gateway_config")
@patch("app.routing.model_router.settings")
def test_first_matching_keyword_rule_wins(mock_settings, mock_gw):
    _mock_settings_and_gw(
        mock_settings, mock_gw,
        keyword_rules=[
            {"keywords": ["legal"], "tier": "powerful"},
            {"keywords": ["legal"], "tier": "fast"},   # second rule never reached
        ],
    )
    model, _, _ = select_model("legal question")
    assert model.model == "gpt-4"


@patch("app.routing.model_router.gateway_config")
@patch("app.routing.model_router.settings")
def test_no_keyword_match_falls_through_to_intent(mock_settings, mock_gw):
    _mock_settings_and_gw(
        mock_settings, mock_gw,
        keyword_rules=[{"keywords": ["legal"], "tier": "powerful"}],
        intent_rules={"conversational": "fast"},
    )
    _, _, reason = select_model("hi")
    assert "intent_rule" in reason

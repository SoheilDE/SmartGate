import os
from dataclasses import dataclass

from app.config import gateway_config
from app.config.settings import settings
from app.routing.complexity_scorer import score as complexity_score
from app.routing.intent_classifier import classify as classify_intent


@dataclass(frozen=True)
class ModelConfig:
    model: str
    base_url: str
    api_key: str


def _model_for_tier(tier: str) -> ModelConfig:
    cfg = gateway_config.model_by_tier(tier)
    # Each model entry declares which env var holds its API key.
    # Fallback order: api_key_env in config → POWERFUL_MODEL_API_KEY
    api_key_env = cfg.get("api_key_env", "POWERFUL_MODEL_API_KEY")
    api_key = os.environ.get(api_key_env) or settings.powerful_model_api_key
    return ModelConfig(
        model=cfg.get("model", settings.powerful_model),
        base_url=cfg.get("base_url", settings.powerful_model_base_url),
        api_key=api_key,
    )


def _match_keyword_rule(text: str, rule: dict) -> bool:
    """Return True if the prompt matches this keyword rule."""
    keywords = [kw.lower() for kw in rule.get("keywords", [])]
    if not keywords:
        return False
    match_mode = rule.get("match", "any")
    if match_mode == "all":
        return all(kw in text for kw in keywords)
    return any(kw in text for kw in keywords)


def select_model(
    prompt: str,
    messages: list | None = None,
    *,
    force_powerful: bool = False,
) -> tuple[ModelConfig, float, str]:
    """
    Returns (model_config, final_score, routing_reason).

    Priority order:
      1. force_powerful override
      2. keyword_routing rules  (first match wins, case-insensitive)
      3. intent_routing rules   (intent → tier)
      4. Complexity score + intent modifier + conversation depth vs threshold
    """
    base_score = complexity_score(prompt)
    intent, intent_modifier = classify_intent(prompt)

    # Longer conversations carry more context — bias toward the powerful model
    depth_modifier = 0.0
    if messages:
        turn_count = sum(1 for m in messages if m.get("role") == "user")
        if turn_count >= 5:
            depth_modifier = 0.10
        elif turn_count >= 3:
            depth_modifier = 0.05

    final_score = round(max(0.0, min(base_score + intent_modifier + depth_modifier, 1.0)), 4)
    threshold = gateway_config.complexity_threshold()
    text = prompt.lower()

    if force_powerful:
        tier = "powerful"
        decision = "forced"
        matched_keywords = []
    else:
        # ── 1. Keyword routing ────────────────────────────────────────────────
        matched_keywords = []
        tier = None
        for rule in gateway_config.keyword_routing():
            if _match_keyword_rule(text, rule):
                tier = rule.get("tier", "powerful")
                matched_keywords = rule.get("keywords", [])
                decision = "keyword_rule"
                break

        # ── 2. Intent routing ─────────────────────────────────────────────────
        if tier is None:
            intent_rules = gateway_config.intent_routing()
            if intent.value in intent_rules:
                tier = intent_rules[intent.value]
                decision = "intent_rule"

        # ── 3. Score threshold ────────────────────────────────────────────────
        if tier is None:
            tier = "powerful" if final_score >= threshold else "fast"
            decision = "score_threshold"

    model = _model_for_tier(tier)

    reason = (
        f"intent={intent.value}, decision={decision}, tier={tier}, "
        f"base={base_score:.3f}, intent_mod={intent_modifier:+.2f}, "
        f"depth_mod={depth_modifier:+.2f}, final={final_score:.3f}, threshold={threshold}"
        + (f", matched_keywords={matched_keywords}" if matched_keywords else "")
    )
    return model, final_score, reason

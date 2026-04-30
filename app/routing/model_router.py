from dataclasses import dataclass

from app.config import gateway_config
from app.config.settings import settings
from app.routing.complexity_scorer import score as complexity_score


@dataclass(frozen=True)
class ModelConfig:
    model: str
    base_url: str
    api_key: str


def _fast() -> ModelConfig:
    cfg = gateway_config.fast_model()
    return ModelConfig(
        model=cfg.get("model", settings.fast_model),
        base_url=cfg.get("base_url", settings.fast_model_base_url),
        api_key=settings.fast_model_api_key,
    )


def _powerful() -> ModelConfig:
    cfg = gateway_config.powerful_model()
    return ModelConfig(
        model=cfg.get("model", settings.powerful_model),
        base_url=cfg.get("base_url", settings.powerful_model_base_url),
        api_key=settings.powerful_model_api_key,
    )


def select_model(prompt: str, *, force_powerful: bool = False) -> tuple[ModelConfig, float]:
    sc = complexity_score(prompt)
    threshold = gateway_config.complexity_threshold()
    if force_powerful or sc >= threshold:
        return _powerful(), sc
    return _fast(), sc

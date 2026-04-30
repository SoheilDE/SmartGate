from dataclasses import dataclass

from app.config.settings import settings
from app.routing.complexity_scorer import score as complexity_score


@dataclass(frozen=True)
class ModelConfig:
    model: str
    base_url: str
    api_key: str


def _fast() -> ModelConfig:
    return ModelConfig(
        model=settings.fast_model,
        base_url=settings.fast_model_base_url,
        api_key=settings.fast_model_api_key,
    )


def _powerful() -> ModelConfig:
    return ModelConfig(
        model=settings.powerful_model,
        base_url=settings.powerful_model_base_url,
        api_key=settings.powerful_model_api_key,
    )


def select_model(prompt: str, *, force_powerful: bool = False) -> tuple[ModelConfig, float]:
    """Return (ModelConfig, complexity_score). Always returns powerful model when force_powerful=True."""
    sc = complexity_score(prompt)
    if force_powerful or sc >= settings.complexity_threshold:
        return _powerful(), sc
    return _fast(), sc

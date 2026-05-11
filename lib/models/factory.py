import os

from lib.models.base import BaseModelClient
from lib.models.openai_compat import OpenAICompatClient
from lib.models.anthropic import AnthropicClient
from lib.config import ModelConfig, AppConfig

_client_cache: dict[tuple, BaseModelClient] = {}


def create_client(config: ModelConfig) -> BaseModelClient:
    cache_key = (config.provider, config.model, config.api_key, config.api_base)
    cached = _client_cache.get(cache_key)
    if cached is not None:
        return cached

    api_key = config.api_key or os.getenv(config.api_key_env, "")
    if not api_key:
        raise ValueError(f"API key not found for model {config.name}")

    if config.provider == "openai_compat":
        client = OpenAICompatClient(
            api_base=config.api_base or "https://api.openai.com/v1",
            api_key=api_key,
            model=config.model,
            supports_vision=config.supports_vision,
        )
    elif config.provider == "anthropic":
        client = AnthropicClient(
            api_key=api_key,
            model=config.model,
            supports_vision=config.supports_vision,
        )
    else:
        raise ValueError(f"Unknown provider: {config.provider}")

    _client_cache[cache_key] = client
    return client


def resolve_model(app_config: AppConfig, model_name: str | None = None) -> tuple[ModelConfig, BaseModelClient]:
    """Resolve model name to config + client. Uses default if None."""
    name = model_name or app_config.default_model
    for m in app_config.models:
        if m.name == name:
            return m, create_client(m)
    raise ValueError(f"Model not found: {name}")

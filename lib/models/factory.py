import os
from lib.models.base import BaseModelClient
from lib.models.openai_compat import OpenAICompatClient
from lib.models.anthropic import AnthropicClient
from lib.config import ModelConfig, AppConfig


def create_client(config: ModelConfig) -> BaseModelClient:
    api_key = config.api_key or os.getenv(config.api_key_env, "")
    if not api_key:
        raise ValueError(f"API key not found for model {config.name}")

    if config.provider == "openai_compat":
        return OpenAICompatClient(
            api_base=config.api_base or "https://api.openai.com/v1",
            api_key=api_key,
            model=config.model,
            supports_vision=config.supports_vision,
        )
    elif config.provider == "anthropic":
        return AnthropicClient(
            api_key=api_key,
            model=config.model,
            supports_vision=config.supports_vision,
        )
    else:
        raise ValueError(f"Unknown provider: {config.provider}")


def resolve_model(app_config: AppConfig, model_name: str | None = None) -> tuple[ModelConfig, BaseModelClient]:
    """Resolve model name to config + client. Uses default if None."""
    name = model_name or app_config.default_model
    for m in app_config.models:
        if m.name == name:
            return m, create_client(m)
    raise ValueError(f"Model not found: {name}")

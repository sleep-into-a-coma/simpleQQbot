import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import yaml

CONFIG_DIR = Path("config")

@dataclass
class ModelConfig:
    name: str
    provider: str
    model: str
    supports_vision: bool = False
    api_base: Optional[str] = None
    api_key_env: str = ""

@dataclass
class PersonalityConfig:
    name: str
    system_prompt: str

@dataclass
class AppConfig:
    default_model: str
    models: list[ModelConfig]
    vision_fallback: ModelConfig
    aliases: dict[str, str]
    search_enabled: bool
    search_max_results: int
    default_personality: str
    personalities: list[PersonalityConfig]
    admins: list[str]
    whitelist_users: list[str]
    whitelist_groups: list[str]
    rate_limit_user_per_minute: int
    rate_limit_group_per_minute: int


def _load_models() -> tuple[str, list[ModelConfig], ModelConfig, dict[str, str], bool, int]:
    with open(CONFIG_DIR / "models.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    models = []
    for name, m in data["models"].items():
        models.append(ModelConfig(
            name=name,
            provider=m["provider"],
            model=m["model"],
            supports_vision=m.get("supports_vision", False),
            api_base=m.get("api_base"),
            api_key_env=m.get("api_key_env", ""),
        ))

    vf = data["vision_fallback"]
    vision_fallback = ModelConfig(
        name="vision_fallback",
        provider=vf["provider"],
        model=vf["model"],
        supports_vision=True,
        api_base=vf.get("api_base"),
        api_key_env=vf.get("api_key_env", ""),
    )

    search = data.get("search", {})
    return (
        data["default"],
        models,
        vision_fallback,
        data.get("aliases", {}),
        search.get("enabled", True),
        search.get("max_results", 5),
    )


def _load_personalities() -> tuple[str, list[PersonalityConfig]]:
    with open(CONFIG_DIR / "personalities.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    personalities = []
    for name, p in data["personalities"].items():
        personalities.append(PersonalityConfig(
            name=name,
            system_prompt=p["system_prompt"],
        ))
    return data["default"], personalities


def _load_permissions() -> tuple[list[str], list[str], list[str], int, int]:
    with open(CONFIG_DIR / "permissions.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return (
        data.get("admins", []),
        data.get("whitelist", {}).get("users", []),
        data.get("whitelist", {}).get("groups", []),
        data.get("rate_limit", {}).get("user_per_minute", 10),
        data.get("rate_limit", {}).get("group_per_minute", 30),
    )


def load_config() -> AppConfig:
    """Load all config and return a single AppConfig object."""
    default_model, models, vision_fallback, aliases, search_enabled, search_max = _load_models()
    default_personality, personalities = _load_personalities()
    admins, wl_users, wl_groups, rl_user, rl_group = _load_permissions()

    return AppConfig(
        default_model=default_model,
        models=models,
        vision_fallback=vision_fallback,
        aliases=aliases,
        search_enabled=search_enabled,
        search_max_results=search_max,
        default_personality=default_personality,
        personalities=personalities,
        admins=admins,
        whitelist_users=wl_users,
        whitelist_groups=wl_groups,
        rate_limit_user_per_minute=rl_user,
        rate_limit_group_per_minute=rl_group,
    )

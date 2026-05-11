# Model Config Migration to .env — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate model configuration from `config/models.yaml` to `.env`, using single-letter identifiers (A/B/C) as model names.

**Architecture:** Replace YAML-based model config loading with env var parsing. Model identifiers become single uppercase letters discovered from `MODEL_*_NAME` env vars. Remove the aliases layer — the letter IS the model name. API keys are stored directly in env per-model for maximum flexibility with custom providers.

**Tech Stack:** Python 3.12+, os.environ, nonebot2, httpx, anthropic SDK

---

## File Structure

| File | Role |
|---|---|
| `.env.example` | Template for all env-based config |
| `lib/config.py` | Env var parsing, validation, `AppConfig` construction |
| `lib/models/factory.py` | Client creation, `api_key` field support |
| `src/plugins/chat/router.py` | Message routing, model prefix matching |
| `src/plugins/chat/handlers.py` | `/model`, `/models`, `/help` commands |
| `config/models.yaml` | **DELETED** |

---

### Task 1: Rewrite `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Replace `.env.example` with new format**

```env
# 默认模型（必须指向下方配置的模型字母）
DEFAULT_MODEL=A

# 模型 A
MODEL_A_NAME=deepseek-chat
MODEL_A_PROVIDER=openai_compat
MODEL_A_API_BASE=https://api.deepseek.com/v1
MODEL_A_API_KEY=sk-your-key
MODEL_A_VISION=false

# 模型 B
MODEL_B_NAME=gpt-4o
MODEL_B_PROVIDER=openai_compat
MODEL_B_API_BASE=https://api.openai.com/v1
MODEL_B_API_KEY=sk-your-key
MODEL_B_VISION=true

# 模型 C
MODEL_C_NAME=claude-3-5-sonnet-20241022
MODEL_C_PROVIDER=anthropic
MODEL_C_API_KEY=sk-ant-your-key
MODEL_C_VISION=true

# Vision 降级（当所选模型不支持图片时自动使用）
VISION_FALLBACK_NAME=gpt-4o-mini
VISION_FALLBACK_PROVIDER=openai_compat
VISION_FALLBACK_API_BASE=https://api.openai.com/v1
VISION_FALLBACK_API_KEY=sk-your-key

# 搜索
SEARCH_ENABLED=true
SEARCH_BACKEND=duckduckgo
SEARCH_MAX_RESULTS=5
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "refactor: rewrite .env.example with per-model env var format"
```

---

### Task 2: Update ModelConfig dataclass and config loading

**Files:**
- Modify: `lib/config.py`

- [ ] **Step 1: Add `api_key` field to `ModelConfig`**

In `lib/config.py` line 8-15, add `api_key` field:

```python
@dataclass
class ModelConfig:
    name: str
    provider: str
    model: str
    supports_vision: bool = False
    api_base: Optional[str] = None
    api_key: str = ""
    api_key_env: str = ""
```

- [ ] **Step 2: Remove `aliases` from `AppConfig`**

In `lib/config.py` line 27, delete the `aliases` line:

```python
@dataclass
class AppConfig:
    default_model: str
    models: list[ModelConfig]
    vision_fallback: ModelConfig
    # aliases: dict[str, str] — REMOVED
    search_enabled: bool
    search_max_results: int
    default_personality: str
    personalities: list[PersonalityConfig]
    admins: list[str]
    whitelist_users: list[str]
    whitelist_groups: list[str]
    rate_limit_user_per_minute: int
    rate_limit_group_per_minute: int
```

- [ ] **Step 3: Replace `_load_models()` with env-based `_load_models_from_env()`**

Replace the entire `_load_models()` function (lines 39-72) with:

```python
def _load_models_from_env() -> tuple[str, list[ModelConfig], ModelConfig, bool, int]:
    import os

    # Discover model IDs from MODEL_*_NAME env vars
    model_ids = set()
    for key in os.environ:
        if key.startswith("MODEL_") and key.endswith("_NAME"):
            mid = key[len("MODEL_"):-len("_NAME")]
            model_ids.add(mid)

    if not model_ids:
        raise ValueError(
            "No models configured. Set MODEL_<ID>_NAME, MODEL_<ID>_PROVIDER, "
            "MODEL_<ID>_API_KEY in .env"
        )

    models = []
    for mid in sorted(model_ids):
        name = os.getenv(f"MODEL_{mid}_NAME", "")
        provider = os.getenv(f"MODEL_{mid}_PROVIDER", "")
        api_key = os.getenv(f"MODEL_{mid}_API_KEY", "")
        api_base = os.getenv(f"MODEL_{mid}_API_BASE") or None
        vision = os.getenv(f"MODEL_{mid}_VISION", "false").lower() == "true"

        if not name or not provider or not api_key:
            missing = []
            if not name:
                missing.append("NAME")
            if not provider:
                missing.append("PROVIDER")
            if not api_key:
                missing.append("API_KEY")
            raise ValueError(
                f"Model '{mid}' is missing required fields: {', '.join(missing)}. "
                f"Set MODEL_{mid}_NAME, MODEL_{mid}_PROVIDER, MODEL_{mid}_API_KEY"
            )

        models.append(ModelConfig(
            name=mid,
            provider=provider,
            model=name,
            supports_vision=vision,
            api_base=api_base,
            api_key=api_key,
        ))

    default_model = os.getenv("DEFAULT_MODEL", "")
    if not default_model:
        raise ValueError("DEFAULT_MODEL is required in .env")

    model_ids_set = {m.name for m in models}
    if default_model not in model_ids_set:
        raise ValueError(
            f"DEFAULT_MODEL='{default_model}' not found in configured models: {model_ids_set}"
        )

    # Vision fallback
    vf_name = os.getenv("VISION_FALLBACK_NAME", "")
    vf_provider = os.getenv("VISION_FALLBACK_PROVIDER", "")
    vf_api_key = os.getenv("VISION_FALLBACK_API_KEY", "")
    if not all([vf_name, vf_provider, vf_api_key]):
        raise ValueError(
            "VISION_FALLBACK_NAME, VISION_FALLBACK_PROVIDER, VISION_FALLBACK_API_KEY are required"
        )

    vision_fallback = ModelConfig(
        name="vision_fallback",
        provider=vf_provider,
        model=vf_name,
        supports_vision=True,
        api_base=os.getenv("VISION_FALLBACK_API_BASE") or None,
        api_key=vf_api_key,
    )

    search_enabled = os.getenv("SEARCH_ENABLED", "true").lower() == "true"
    search_max = int(os.getenv("SEARCH_MAX_RESULTS", "5"))

    return default_model, models, vision_fallback, search_enabled, search_max
```

- [ ] **Step 4: Update `load_config()` to use new function and remove aliases**

In `lib/config.py` lines 101-121, update `load_config()`:

```python
def load_config() -> AppConfig:
    """Load all config and return a single AppConfig object."""
    default_model, models, vision_fallback, search_enabled, search_max = _load_models_from_env()
    default_personality, personalities = _load_personalities()
    admins, wl_users, wl_groups, rl_user, rl_group = _load_permissions()

    return AppConfig(
        default_model=default_model,
        models=models,
        vision_fallback=vision_fallback,
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
```

- [ ] **Step 5: Remove unused `import yaml` and `CONFIG_DIR` if only used for models**

Check if `yaml` and `CONFIG_DIR` are still used by `_load_personalities()` and `_load_permissions()`. They are, so keep `import yaml` and `CONFIG_DIR`. No change needed.

- [ ] **Step 6: Verify the module imports cleanly**

```bash
cd E:/DOCUMENT/WORK/project/p1 && python -c "from lib.config import load_config; print('OK')"
```
Expected: `OK` (requires `.env` with valid config)

- [ ] **Step 7: Commit**

```bash
git add lib/config.py
git commit -m "refactor: load model config from env vars instead of YAML"
```

---

### Task 3: Update factory to use direct api_key

**Files:**
- Modify: `lib/models/factory.py`

- [ ] **Step 1: Update `create_client()` to prefer `config.api_key`**

Replace line 9 in `factory.py`:

```python
def create_client(config: ModelConfig) -> BaseModelClient:
    api_key = config.api_key or os.getenv(config.api_key_env, "")
    if not api_key:
        raise ValueError(f"API key not found for model {config.name}")
```

The rest of `create_client()` stays the same.

- [ ] **Step 2: Verify import**

```bash
cd E:/DOCUMENT/WORK/project/p1 && python -c "from lib.models.factory import create_client, resolve_model; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add lib/models/factory.py
git commit -m "feat: support direct api_key field in ModelConfig"
```

---

### Task 4: Update router to match model prefixes instead of aliases

**Files:**
- Modify: `src/plugins/chat/router.py`

- [ ] **Step 1: Replace alias loop with model name prefix matching**

Replace lines 74-81 in `router.py`:

```python
    # Step 3: Check for model prefix trigger (/A /B /C)
    trigger_model = None
    msg_text = user_text
    for m in app_config.models:
        prefix = f"/{m.name} "
        if user_text.startswith(prefix):
            trigger_model = m.name
            msg_text = user_text[len(prefix):].strip()
            break
```

- [ ] **Step 2: Verify import**

```bash
cd E:/DOCUMENT/WORK/project/p1 && python -c "import src.plugins.chat.router; print('OK')"
```
Expected: `OK` (will trigger config loading, needs `.env`)

- [ ] **Step 3: Commit**

```bash
git add src/plugins/chat/router.py
git commit -m "refactor: match model prefix directly instead of aliases dict"
```

---

### Task 5: Update command handlers

**Files:**
- Modify: `src/plugins/chat/handlers.py`

- [ ] **Step 1: Update `/models` handler to show letter + actual model name**

Replace the `handle_models` function (lines 67-77):

```python
@models_cmd.handle()
async def handle_models(event: MessageEvent):
    lines = ["可用模型："]
    default = app_config.default_model
    for m in app_config.models:
        vision_tag = " [vision]" if m.supports_vision else ""
        default_tag = " [默认]" if m.name == default else ""
        lines.append(f"  {m.name} - {m.model} ({m.provider}){vision_tag}{default_tag}")
    await models_cmd.finish("\n".join(lines))
```

- [ ] **Step 2: Update `/help` handler to remove alias references**

Replace the help text (lines 51-61):

```python
    help_text = """可用指令：
/help - 显示此帮助
/models - 列出可用模型
/model <字母> - 切换当前对话的 AI 模型（如 /model A）
/set <人格名> - 切换 Bot 人格
/字母 消息 - 临时用对应模型回复本条（如 /B 你好）
/status - 查看当前配置
/summarize - 总结当前对话
/clear - 清除对话记忆
/allow @某人 - 允许某人使用 Bot（管理员）
/ban @某人 - 禁止某人使用 Bot（管理员）"""
```

- [ ] **Step 3: Update `/model` handler to show both letter and actual model name**

Replace lines 98-110:

```python
@model_cmd.handle()
async def handle_model(event: MessageEvent, args: Message = CommandArg()):
    mid = args.extract_plain_text().strip()
    if not mid:
        await model_cmd.finish("用法：/model <字母>")

    valid_ids = [m.name for m in app_config.models]
    if mid not in valid_ids:
        await model_cmd.finish(f"未知模型：{mid}。可用：{', '.join(valid_ids)}")

    target_type, target_id = _get_target(event)
    from lib.model_binding import set_model_binding
    await set_model_binding(target_type, target_id, mid)
    display_name = next((m.model for m in app_config.models if m.name == mid), mid)
    await model_cmd.finish(f"模型已切换为：{mid} ({display_name})")
```

- [ ] **Step 4: Verify module imports**

```bash
cd E:/DOCUMENT/WORK/project/p1 && python -c "import src.plugins.chat.handlers; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/plugins/chat/handlers.py
git commit -m "refactor: update /model, /models, /help for env-based config"
```

---

### Task 6: Delete models.yaml and clean up

**Files:**
- Delete: `config/models.yaml`

- [ ] **Step 1: Delete the file**

```bash
rm E:/DOCUMENT/WORK/project/p1/config/models.yaml
```

- [ ] **Step 2: Verify nothing imports models.yaml**

```bash
cd E:/DOCUMENT/WORK/project/p1 && grep -r "models.yaml" --include="*.py" .
```
Expected: no results.

- [ ] **Step 3: Run tests to confirm nothing is broken**

```bash
cd E:/DOCUMENT/WORK/project/p1 && python -m pytest tests/ -v
```
Expected: all tests pass (tests only cover context/DB, not config loading directly)

- [ ] **Step 4: Commit**

```bash
git add config/models.yaml
git commit -m "chore: delete models.yaml, config now in .env"
```

---

## Migration Notes

- **Existing DB bindings are invalidated** — old `model_name` values like `deepseek-v3` won't match new letter identifiers. If users had persistent model bindings set, they'll need to re-run `/model A`.
- **`.env` must be created from `.env.example`** before starting the bot — there is no fallback config file.
- **`config/models.yaml` is deleted** — any deployment scripts or Docker configs referencing it must be updated.

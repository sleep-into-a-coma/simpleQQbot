# think 思维链 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture and display AI reasoning/thinking chains via global toggle `/think on/off` + per-message `<think>` trigger, with cycle-slot history storage.

**Architecture:** Extend `ChatResponse` with `thinking` field. Providers capture reasoning from native API fields (OpenAI `reasoning_content`, Anthropic `thinking` blocks). A per-group slot counter (in-memory) cycles 1→2→3→1, overwriting old entries in `think_history` table. The `/Thistory <N>` command retrieves by group_id + slot.

**Tech Stack:** NoneBot2 + aiosqlite + httpx. No new dependencies.

---

### Task 1: Add think_enabled to config

**Files:**
- Modify: `config/permissions.yaml`
- Modify: `lib/config.py:30-43` (AppConfig)
- Modify: `lib/config.py:139-150` (_load_permissions)
- Modify: `lib/config.py:157-173` (load_config)

- [ ] **Step 1: Add think_enabled to permissions.yaml**

Append to `config/permissions.yaml`:

```yaml

think_enabled: false
```

So the full file becomes:

```yaml
admins: []

whitelist:
  users: []
  groups: []

rate_limit:
  user_per_minute: 10
  group_per_minute: 30

private_chat:
  enabled: true

think_enabled: false
```

- [ ] **Step 2: Add field to AppConfig dataclass**

In `lib/config.py`, after line 43 (`private_chat_enabled: bool`), insert:

```python
    think_enabled: bool
```

- [ ] **Step 3: Update _load_permissions return**

Replace the `_load_permissions` function signature and return tuple. Change the return from:
```python
def _load_permissions() -> tuple[list[str], list[str], list[str], int, int, bool]:
```
to:
```python
def _load_permissions() -> tuple[list[str], list[str], list[str], int, int, bool, bool]:
```

And extend the return statement with:
```python
        data.get("think_enabled", False),
```

So the full function becomes:

```python
def _load_permissions() -> tuple[list[str], list[str], list[str], int, int, bool, bool]:
    with open(CONFIG_DIR / "permissions.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return (
        data.get("admins", []),
        data.get("whitelist", {}).get("users", []),
        data.get("whitelist", {}).get("groups", []),
        data.get("rate_limit", {}).get("user_per_minute", 10),
        data.get("rate_limit", {}).get("group_per_minute", 30),
        data.get("private_chat", {}).get("enabled", True),
        data.get("think_enabled", False),
    )
```

- [ ] **Step 4: Update load_config unpacking**

In `load_config`, change the unpack line from:
```python
    admins, wl_users, wl_groups, rl_user, rl_group, pc_enabled = _load_permissions()
```
to:
```python
    admins, wl_users, wl_groups, rl_user, rl_group, pc_enabled, think_enabled = _load_permissions()
```

And add to the `AppConfig(...)` constructor, after `private_chat_enabled=pc_enabled,`:
```python
        think_enabled=think_enabled,
```

- [ ] **Step 5: Commit**

```bash
git add config/permissions.yaml lib/config.py
git commit -m "feat: add think_enabled to config"
```

---

### Task 2: Add thinking field to ChatResponse

**Files:**
- Modify: `lib/models/base.py:29-32` (ChatResponse)

- [ ] **Step 1: Add thinking field**

In `lib/models/base.py`, change:
```python
@dataclass
class ChatResponse:
    content: str
    thinking: str = ""          # 新增
    tool_calls: list[ToolCall] = field(default_factory=list)
```

Note: `thinking` must come BEFORE `tool_calls` since it has no default, while `tool_calls` uses `field(default_factory=list)` — actually wait, `thinking: str = ""` has a default, so order doesn't matter. But to be clean, add it between content and tool_calls:

```python
@dataclass
class ChatResponse:
    content: str
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
```

- [ ] **Step 2: Commit**

```bash
git add lib/models/base.py
git commit -m "feat: add thinking field to ChatResponse"
```

---

### Task 3: Add think_history table + seed think_enabled in init_db

**Files:**
- Modify: `lib/db.py:16-79` (init_db)

- [ ] **Step 1: Add think_history table to executescript**

In `lib/db.py`, inside `init_db`'s `executescript`, add before the closing `"""`:

```sql

            CREATE TABLE IF NOT EXISTS think_history (
                group_id TEXT NOT NULL,
                slot INTEGER NOT NULL,
                user_msg TEXT,
                thinking TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_id, slot)
            );
```

- [ ] **Step 2: Seed think_enabled in settings table**

In `init_db`, after the existing `private_chat_enabled` seed block (after the `INSERT OR IGNORE` and `await db.commit()` for it), add:

```python
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("think_enabled", "1" if config.think_enabled else "0"),
        )
```

Note: the existing `config` variable is already loaded at this point (from the private_chat_enabled seed), so no need to import again.

- [ ] **Step 3: Commit**

```bash
git add lib/db.py
git commit -m "feat: add think_history table and seed think_enabled"
```

---

### Task 4: Add think helper functions to permission.py

**Files:**
- Modify: `lib/permission.py` (append new functions)

- [ ] **Step 1: Add in-memory slot counter and helpers**

Append to `lib/permission.py`:

```python
# Per-group think slot counter (in-memory, reset on restart)
_think_slot_counter: dict[str, int] = {}


async def get_think_enabled() -> bool:
    """Check if global think toggle is on."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?",
            ("think_enabled",),
        )
        row = await cursor.fetchone()
        if row is None:
            from lib.config import load_config
            return load_config().think_enabled
        return row["value"] == "1"
    finally:
        await db.close()


async def set_think_enabled(enabled: bool) -> None:
    """Set the global think toggle."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("think_enabled", "1" if enabled else "0"),
        )
        await db.commit()
    finally:
        await db.close()


async def save_think_history(group_id: str, user_msg: str, thinking: str) -> int:
    """Save thinking to per-group slot (1/2/3 cycling). Returns the slot number used."""
    counter = _think_slot_counter.get(group_id, 0) + 1
    _think_slot_counter[group_id] = counter
    slot = ((counter - 1) % 3) + 1

    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO think_history (group_id, slot, user_msg, thinking, created_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (group_id, slot, user_msg, thinking),
        )
        await db.commit()
    finally:
        await db.close()
    return slot


async def get_think_history(group_id: str, slot: int) -> dict | None:
    """Retrieve a thinking entry by group_id and slot number (1/2/3)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT slot, user_msg, thinking, created_at FROM think_history WHERE group_id = ? AND slot = ?",
            (group_id, slot),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "slot": row["slot"],
            "user_msg": row["user_msg"],
            "thinking": row["thinking"],
            "created_at": row["created_at"],
        }
    finally:
        await db.close()
```

- [ ] **Step 2: Commit**

```bash
git add lib/permission.py
git commit -m "feat: add think helper functions"
```

---

### Task 5: Update providers to capture thinking

**Files:**
- Modify: `lib/models/base.py:48` (abstract chat method signature)
- Modify: `lib/models/openai_compat.py:16-70` (chat method)
- Modify: `lib/models/anthropic.py:15-80` (chat method)

- [ ] **Step 1: Add enable_thinking param to abstract base**

In `lib/models/base.py`, change the `chat` method signature:

```python
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        enable_thinking: bool = False,
    ) -> ChatResponse:
        """Send messages and return response. May include tool calls."""
        ...
```

- [ ] **Step 2: Capture reasoning_content in OpenAICompatClient**

In `lib/models/openai_compat.py`, update the `chat` method signature to match:

```python
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        enable_thinking: bool = False,
    ) -> ChatResponse:
```

Then, after parsing `content` from the response (around line 60-61), add thinking capture:

```python
        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        thinking = choice.get("reasoning_content") or ""
        tool_calls = []
```

And update the return to include thinking:

```python
        return ChatResponse(content=content, thinking=thinking, tool_calls=tool_calls)
```

- [ ] **Step 3: Capture thinking blocks in AnthropicClient**

In `lib/models/anthropic.py`, update the `chat` method signature:

```python
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        enable_thinking: bool = False,
    ) -> ChatResponse:
```

Then, when `enable_thinking=True`, add thinking config to the API call. After `kwargs["tools"] = anthropic_tools` (line 45), add:

```python
        if enable_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 1024}
            kwargs["max_tokens"] = kwargs.get("max_tokens", 4096) + 1024
```

Then update the response parsing (around lines 68-80) to capture thinking blocks:

```python
        content = ""
        thinking_text = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "thinking":
                thinking_text += block.thinking
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        return ChatResponse(content=content, thinking=thinking_text, tool_calls=tool_calls)
```

- [ ] **Step 4: Commit**

```bash
git add lib/models/base.py lib/models/openai_compat.py lib/models/anthropic.py
git commit -m "feat: capture thinking from OpenAI and Anthropic providers"
```

---

### Task 6: Pass think param through ai_core

**Files:**
- Modify: `lib/ai_core.py:30-124` (process_message)

- [ ] **Step 1: Add think_triggered param to process_message**

Change the function signature (line 30) from:
```python
async def process_message(
    user_text: str,
    image_data: bytes | None,
    group_id: str,
    user_id: str,
    history: list[dict],
    personality_system_prompt: str,
    model_name: str | None,
    app_config: AppConfig,
) -> dict:
```
to:
```python
async def process_message(
    user_text: str,
    image_data: bytes | None,
    group_id: str,
    user_id: str,
    history: list[dict],
    personality_system_prompt: str,
    model_name: str | None,
    app_config: AppConfig,
    think_triggered: bool = False,
) -> dict:
```

- [ ] **Step 2: Pass enable_thinking to client.chat()**

In the tool calling loop, change the `client.chat()` call (around line 78):
```python
        response = await client.chat(messages, tools if tools else None)
```
to:
```python
        response = await client.chat(messages, tools if tools else None, enable_thinking=think_triggered)
```

- [ ] **Step 3: Include thinking in returned result dict**

In the return dict (lines 106-113), add `"thinking"`:

```python
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "content": response.content,
                "thinking": response.thinking,
                "model_name": model_config.name,
                "has_search": has_search,
                "has_image": has_image,
                "response_time_ms": elapsed_ms,
                "sources": sources,
            }
```

Also update the fallback return (lines 117-124) to include `"thinking": ""`.

- [ ] **Step 4: Commit**

```bash
git add lib/ai_core.py
git commit -m "feat: pass think_triggered through ai_core pipeline"
```

---

### Task 7: Integrate think into message router

**Files:**
- Modify: `src/plugins/chat/router.py`

- [ ] **Step 1: Add imports for think helpers**

Change line 11 in `router.py`:
```python
from lib.permission import check_permission, check_rate_limit, check_private_chat_permission
```
to:
```python
from lib.permission import check_permission, check_rate_limit, check_private_chat_permission, get_think_enabled, save_think_history
```

- [ ] **Step 2: Add think detection and stripping before Step 3**

In `handle_chat`, after Step 2 (rate limit check) and before Step 3 (model prefix check), add:

```python
    # Step 2.5: Detect <think> trigger
    THINK_TAG = "<think>"
    think_triggered = False
    if msg_text.endswith(THINK_TAG):
        think_triggered = True
        msg_text = msg_text[:-len(THINK_TAG)].strip()
```

- [ ] **Step 3: Resolve think_triggered with global toggle**

After the `<think>` detection, add global toggle check:

```python
    # Resolve think: per-message trigger OR global toggle
    if not think_triggered:
        think_triggered = await get_think_enabled()
```

- [ ] **Step 4: Pass think_triggered to process_message**

In the `process_message` call (around line 112), add the parameter:

```python
        result = await process_message(
            user_text=msg_text,
            image_data=image_data,
            group_id=group_id,
            user_id=user_id,
            history=history,
            personality_system_prompt=personality.system_prompt,
            model_name=resolved_model,
            app_config=app_config,
            think_triggered=think_triggered,
        )
```

- [ ] **Step 5: Save think history and build response with thinking**

After Step 11 (log_reply), and before Step 12 (build and send reply), add thinking handling:

```python
    # Step 11.5: Handle thinking
    thinking_hint = ""
    if think_triggered and result.get("thinking"):
        slot = await save_think_history(group_id, user_text, result["thinking"])
        thinking_hint = f"\n（输入 /Thistory {slot} 查看本条思维链）"
```

- [ ] **Step 6: Append thinking + hint to reply**

Change the `full_reply` construction (lines 142-151) to include thinking:

```python
    # Step 12: Build and send reply
    reply_text = CQ_PATTERN.sub('', result["content"])
    if think_triggered and result.get("thinking"):
        reply_text = f"{reply_text}\n\n【思维链】\n{result['thinking']}"
    metadata = _format_metadata(
        personality.name,
        result["model_name"],
        result["has_search"],
        result["has_image"],
        result["response_time_ms"],
    )
    sources = format_search_sources(result["sources"]) if result["has_search"] else ""
    full_reply = f"{reply_text}\n\n{metadata}{sources}{thinking_hint}"
```

- [ ] **Step 7: Commit**

```bash
git add src/plugins/chat/router.py
git commit -m "feat: integrate think detection and thinking output into router"
```

---

### Task 8: Add /think and /Thistory commands + update /help

**Files:**
- Modify: `src/plugins/chat/handlers.py`

- [ ] **Step 1: Add imports**

Change line 6 in `handlers.py`:
```python
from lib.permission import check_permission, set_permission, get_rate_limit_status, get_private_chat_enabled, set_private_chat_enabled
```
to:
```python
from lib.permission import check_permission, set_permission, get_rate_limit_status, get_private_chat_enabled, set_private_chat_enabled, get_think_enabled, set_think_enabled, get_think_history
```

- [ ] **Step 2: Add /think command**

Insert BEFORE the `/admin` command block (before `admin_cmd = on_command("admin", priority=10)`):

```python
think_cmd = on_command("think", priority=10)

@think_cmd.handle()
async def handle_think(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await think_cmd.finish("权限不足。")
    action = args.extract_plain_text().strip()
    if action not in ("on", "off"):
        await think_cmd.finish("用法：/think on 或 /think off")
    enabled = action == "on"
    await set_think_enabled(enabled)
    await think_cmd.finish(f"思维链已{'开启' if enabled else '关闭'}。")
```

- [ ] **Step 3: Add /Thistory command**

Insert AFTER `/think` command:

```python
thistory_cmd = on_command("Thistory", priority=10)

@thistory_cmd.handle()
async def handle_thistory(event: MessageEvent, args: Message = CommandArg()):
    group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else "private"
    slot_str = args.extract_plain_text().strip()
    if not slot_str or not slot_str.isdigit():
        await thistory_cmd.finish("用法：/Thistory <1/2/3>")
    slot = int(slot_str)
    if slot not in (1, 2, 3):
        await thistory_cmd.finish("请输入 1、2 或 3。")
    entry = await get_think_history(group_id, slot)
    if entry is None:
        await thistory_cmd.finish(f"槽位 {slot} 暂无思维链记录。")
    await thistory_cmd.finish(
        f"【思维链 #{slot}】\n"
        f"用户消息：{entry['user_msg'][:200]}\n"
        f"时间：{entry['created_at']}\n\n"
        f"{entry['thinking']}"
    )
```

- [ ] **Step 4: Update /help text**

Replace the `help_text` in `handle_help` to include the new commands. Add these lines before `/admin`:

```python
/think on/off - 全局思维链开关（管理员）
/Thistory <1/2/3> - 查看对应槽位的思维链
```

So the full help_text becomes:

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
/ban @某人 - 禁止某人使用 Bot（管理员）
/hire <群号> - 授权群使用 Bot（管理员）
/fire <群号> - 撤销群使用权限（管理员）
/allow-p @某人 - 授权某人私聊 Bot（管理员）
/ban-p @某人 - 撤销某人私聊权限（管理员）
/private on/off - 全局私聊开关（管理员）
/think on/off - 全局思维链开关（管理员）
/Thistory <1/2/3> - 查看对应槽位的思维链
/admin - 查看管理面板（管理员）"""
```

- [ ] **Step 5: Commit**

```bash
git add src/plugins/chat/handlers.py
git commit -m "feat: add /think and /Thistory commands"
```

---

### Task 9: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update command table**

In README, add these 2 rows to the command table before `/admin`:

```markdown
| `/think on/off` | 全局思维链开关（管理员） |
| `/Thistory <1/2/3>` | 查看对应槽位的思维链 |
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with think and Thistory commands"
```

---

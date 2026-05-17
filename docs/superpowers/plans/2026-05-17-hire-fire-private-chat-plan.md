# hire/fire + private chat + /admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add group permission commands (/hire /fire), private chat user controls (/allow-p /ban-p), global private chat toggle (/private on/off), and admin dashboard (/admin).

**Architecture:** Reuse existing `permissions` table with new `target_type` values (`group`, `private_chat`). Add a `settings` key-value table for runtime toggles. New commands follow the same pattern as `/allow` `/ban` — admin gating in the handler, delegation to `set_permission` / new helpers.

**Tech Stack:** NoneBot2 + aiosqlite + PyYAML. No new dependencies.

---

### Task 1: Update permissions.yaml

**Files:**
- Modify: `config/permissions.yaml`

- [ ] **Step 1: Add private_chat section**

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
```

- [ ] **Step 2: Commit**

```bash
git add config/permissions.yaml
git commit -m "feat: add private_chat.enabled to permissions.yaml"
```

---

### Task 2: Update AppConfig and _load_permissions

**Files:**
- Modify: `lib/config.py:30-41` (AppConfig dataclass)
- Modify: `lib/config.py:138-148` (_load_permissions)

- [ ] **Step 1: Add private_chat_enabled to AppConfig**

In `lib/config.py`, after line 41 (`rate_limit_group_per_minute: int`), insert:

```python
    private_chat_enabled: bool
```

- [ ] **Step 2: Update _load_permissions to parse private_chat**

Replace `_load_permissions` function (lines 138-148) with:

```python
def _load_permissions() -> tuple[list[str], list[str], list[str], int, int, bool]:
    with open(CONFIG_DIR / "permissions.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return (
        data.get("admins", []),
        data.get("whitelist", {}).get("users", []),
        data.get("whitelist", {}).get("groups", []),
        data.get("rate_limit", {}).get("user_per_minute", 10),
        data.get("rate_limit", {}).get("group_per_minute", 30),
        data.get("private_chat", {}).get("enabled", True),
    )
```

- [ ] **Step 3: Update load_config to pass the new field**

In `lib/config.py`, update the `load_config` function. Change line 155 from:
```python
    admins, wl_users, wl_groups, rl_user, rl_group = _load_permissions()
```
to:
```python
    admins, wl_users, wl_groups, rl_user, rl_group, pc_enabled = _load_permissions()
```

And in the `AppConfig` constructor (around line 157), add the new field at the end before the closing parenthesis:

```python
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
        private_chat_enabled=pc_enabled,
    )
```

- [ ] **Step 4: Commit**

```bash
git add lib/config.py
git commit -m "feat: add private_chat_enabled to AppConfig and _load_permissions"
```

---

### Task 3: Add settings table to init_db

**Files:**
- Modify: `lib/db.py:16-79` (init_db)

- [ ] **Step 1: Add settings table to init_db**

In `lib/db.py`, inside the `init_db` function's `executescript` block, add after the existing `CREATE INDEX IF NOT EXISTS idx_reply_log_time` statement:

```python
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
```

- [ ] **Step 2: Seed default settings from config in init_db**

In `lib/db.py`, add import for config at top:

```python
from lib.config import load_config
```

After the `executescript` block in `init_db` (but still inside the `try` block, before the `commit`), add:

```python
        config = load_config()
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("private_chat_enabled", "1" if config.private_chat_enabled else "0"),
        )
```

- [ ] **Step 3: Commit**

```bash
git add lib/db.py
git commit -m "feat: add settings table and seed private_chat_enabled"
```

---

### Task 4: Add private chat permission helpers

**Files:**
- Modify: `lib/permission.py`

- [ ] **Step 1: Add get_private_chat_enabled**

Append to `lib/permission.py`:

```python
async def get_private_chat_enabled() -> bool:
    """Check if private chat is globally enabled."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?",
            ("private_chat_enabled",),
        )
        row = await cursor.fetchone()
        if row is None:
            from lib.config import load_config
            return load_config().private_chat_enabled
        return row["value"] == "1"
    finally:
        await db.close()
```

- [ ] **Step 2: Add set_private_chat_enabled**

Append to `lib/permission.py`:

```python
async def set_private_chat_enabled(enabled: bool) -> None:
    """Set the global private chat toggle."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("private_chat_enabled", "1" if enabled else "0"),
        )
        await db.commit()
    finally:
        await db.close()
```

- [ ] **Step 3: Add check_private_chat_permission**

Append to `lib/permission.py`:

```python
async def check_private_chat_permission(user_id: str, config: AppConfig) -> tuple[bool, str]:
    """Check private chat access for a user. Returns (allowed, reason_if_blocked)."""
    # Global toggle
    if not await get_private_chat_enabled():
        return False, "私聊功能已关闭。"

    # Dynamic rules check
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT level FROM permissions WHERE target_type = ? AND target_id = ?",
            ("private_chat", user_id),
        )
        row = await cursor.fetchone()
        if row and row["level"] == "block":
            return False, "你已被禁止使用私聊功能。"
        if row and row["level"] == "allow":
            return True, ""
    finally:
        await db.close()

    # Fall back to existing check_permission (static whitelist logic)
    return await check_permission("private", user_id, config)
```

- [ ] **Step 4: Commit**

```bash
git add lib/permission.py
git commit -m "feat: add private chat permission helpers"
```

---

### Task 5: Add /hire /fire /allow-p /ban-p /private /admin commands

**Files:**
- Modify: `src/plugins/chat/handlers.py`

- [ ] **Step 1: Add imports for new helpers**

Replace line 6 in `handlers.py`:
```python
from lib.permission import check_permission, set_permission, get_rate_limit_status
```
with:
```python
from lib.permission import check_permission, set_permission, get_rate_limit_status, get_private_chat_enabled, set_private_chat_enabled
```

- [ ] **Step 2: Add /hire command**

Insert after the `/ban` handler block (after line 139):

```python
hire_cmd = on_command("hire", priority=10)

@hire_cmd.handle()
async def handle_hire(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await hire_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await hire_cmd.finish("用法：/hire <群号>")
    target_id = target
    await set_permission("group", target_id, "allow")
    await hire_cmd.finish(f"已授权群 {target_id} 使用 Bot。")


fire_cmd = on_command("fire", priority=10)

@fire_cmd.handle()
async def handle_fire(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await fire_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await fire_cmd.finish("用法：/fire <群号>")
    target_id = target
    await set_permission("group", target_id, "block")
    await fire_cmd.finish(f"已禁止群 {target_id} 使用 Bot。")
```

- [ ] **Step 3: Add /allow-p and /ban-p commands**

Insert after the `/fire` block:

```python
allow_p_cmd = on_command("allow-p", priority=10)

@allow_p_cmd.handle()
async def handle_allow_p(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await allow_p_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await allow_p_cmd.finish("用法：/allow-p @某人 或 /allow-p QQ号")
    target_id = _extract_qq(target)
    await set_permission("private_chat", target_id, "allow")
    await allow_p_cmd.finish(f"已授权 {target_id} 私聊使用 Bot。")


ban_p_cmd = on_command("ban-p", priority=10)

@ban_p_cmd.handle()
async def handle_ban_p(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await ban_p_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await ban_p_cmd.finish("用法：/ban-p @某人 或 /ban-p QQ号")
    target_id = _extract_qq(target)
    await set_permission("private_chat", target_id, "block")
    await ban_p_cmd.finish(f"已禁止 {target_id} 私聊使用 Bot。")
```

- [ ] **Step 4: Add /private command**

Insert after `/ban-p`:

```python
private_cmd = on_command("private", priority=10)

@private_cmd.handle()
async def handle_private(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await private_cmd.finish("权限不足。")
    action = args.extract_plain_text().strip()
    if action not in ("on", "off"):
        await private_cmd.finish("用法：/private on 或 /private off")
    enabled = action == "on"
    await set_private_chat_enabled(enabled)
    await private_cmd.finish(f"私聊功能已{'开启' if enabled else '关闭'}。")
```

- [ ] **Step 5: Add /admin command**

Insert after `/private`:

```python
admin_cmd = on_command("admin", priority=10)

@admin_cmd.handle()
async def handle_admin(event: MessageEvent):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await admin_cmd.finish("权限不足。")

    from lib.db import get_db

    lines = ["=== Bot 管理面板 ===", ""]

    # Static config
    lines.append("【静态白名单 (yaml)】")
    lines.append(f"  管理员: {', '.join(app_config.admins) if app_config.admins else '未配置'}")
    lines.append(f"  白名单用户: {', '.join(app_config.whitelist_users) if app_config.whitelist_users else '未限制'}")
    lines.append(f"  白名单群: {', '.join(app_config.whitelist_groups) if app_config.whitelist_groups else '未限制'}")
    lines.append("")

    # Dynamic permissions
    db = await get_db()
    try:
        cursor = await db.execute("SELECT target_type, target_id, level FROM permissions ORDER BY target_type, target_id")
        rows = await cursor.fetchall()
        lines.append("【动态权限 (DB)】")
        if rows:
            for row in rows:
                type_label = {"user": "用户", "group": "群", "private_chat": "私聊"}.get(row["target_type"], row["target_type"])
                level_label = "允许" if row["level"] == "allow" else "禁止"
                lines.append(f"  [{type_label}] {row['target_id']} → {level_label}")
        else:
            lines.append("  无")
    finally:
        await db.close()

    lines.append("")

    # Private chat toggle
    pc_enabled = await get_private_chat_enabled()
    lines.append(f"【私聊开关】: {'开启' if pc_enabled else '关闭'}")
    lines.append("")

    # Rate limits
    lines.append("【频率限制】")
    lines.append(f"  用户: {app_config.rate_limit_user_per_minute}/分钟")
    lines.append(f"  群: {app_config.rate_limit_group_per_minute}/分钟")

    await admin_cmd.finish("\n".join(lines))
```

- [ ] **Step 6: Update /help text**

Replace the help_text in `handle_help` (lines 51-61):

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
/admin - 查看管理面板（管理员）"""
```

- [ ] **Step 7: Commit**

```bash
git add src/plugins/chat/handlers.py
git commit -m "feat: add /hire /fire /allow-p /ban-p /private /admin commands"
```

---

### Task 6: Add private chat check in message router

**Files:**
- Modify: `src/plugins/chat/router.py:60-73`

- [ ] **Step 1: Add import for check_private_chat_permission**

Replace line 11 in `router.py`:
```python
from lib.permission import check_permission, check_rate_limit
```
with:
```python
from lib.permission import check_permission, check_rate_limit, check_private_chat_permission
```

- [ ] **Step 2: Add private chat check before existing permission check**

In `handle_chat`, after determining `group_id` and `user_id` (line 69), insert before the "Step 1: Permission check" comment (line 70):

```python
    # Step 0: Private chat access check
    if group_id == "private":
        allowed, reason = await check_private_chat_permission(user_id, app_config)
        if not allowed:
            await chat_handler.finish(reason)
```

- [ ] **Step 3: Commit**

```bash
git add src/plugins/chat/router.py
git commit -m "feat: gate private chat messages behind check_private_chat_permission"
```

---

### Task 7: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update command list in README**

Replace the table in README (lines 64-76):

```markdown
| 指令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/models` | 列出可用模型 |
| `/model <字母>` | 切换当前对话的 AI 模型 |
| `/A <消息>` `/B <消息>` | 临时使用指定模型回复本条消息 |
| `/set <人格名>` | 切换 Bot 人格 |
| `/status` | 查看当前配置和频率使用量 |
| `/summarize` | 总结当前对话历史 |
| `/clear` | 清除对话记忆 |
| `/allow @某人` | 允许某人使用 Bot（管理员） |
| `/ban @某人` | 禁止某人使用 Bot（管理员） |
| `/hire <群号>` | 授权群使用 Bot（管理员） |
| `/fire <群号>` | 撤销群使用权限（管理员） |
| `/allow-p @某人` | 授权某人私聊 Bot（管理员） |
| `/ban-p @某人` | 撤销某人私聊权限（管理员） |
| `/private on/off` | 全局私聊开关（管理员） |
| `/admin` | 查看管理面板（管理员） |
```

- [ ] **Step 2: Update permissions.yaml description in README**

Change line 53:
```
人格配置在 `config/personalities.yaml`，权限白名单在 `config/permissions.yaml`。
```
to:
```
人格配置在 `config/personalities.yaml`，权限白名单和私聊开关在 `config/permissions.yaml`。
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with new commands"
```

---

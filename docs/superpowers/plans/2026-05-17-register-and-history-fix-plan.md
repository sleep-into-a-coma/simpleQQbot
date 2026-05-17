# 群聊历史修复 + /register Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix group chat history to include all users (not just current speaker) with name-labeled messages, and add `/register` command to bind human-readable names to QQ IDs.

**Architecture:** Add `user_names` table for ID→name mapping. Modify `get_history` to query by group_id only for group chats. Extend history return values with `user_id`. Wrap group chat history messages in `<群聊消息>发言人：内容</群聊消息>` format with name resolution (DB lookup → fallback `用户{id}`).

**Tech Stack:** NoneBot2 + aiosqlite. No new dependencies.

---

### Task 1: Add user_names table to init_db

**Files:**
- Modify: `lib/db.py`

- [ ] **Step 1: Add user_names table to executescript**

Read `lib/db.py`. In `init_db`, inside the `executescript` block, add before the closing `"""`:

```sql

            CREATE TABLE IF NOT EXISTS user_names (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
```

- [ ] **Step 2: Commit**

```bash
git add lib/db.py
git commit -m "feat: add user_names table"
```

---

### Task 2: Add user name helpers to permission.py

**Files:**
- Modify: `lib/permission.py`

- [ ] **Step 1: Append helper functions**

Append at the end of `lib/permission.py`:

```python
async def set_user_name(user_id: str, name: str) -> None:
    """Bind a name to a user ID."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO user_names (user_id, name) VALUES (?, ?)",
            (user_id, name),
        )
        await db.commit()
    finally:
        await db.close()


async def get_user_name(user_id: str) -> str | None:
    """Get a user's bound name, or None if not registered."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT name FROM user_names WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["name"] if row else None
    finally:
        await db.close()


async def get_group_user_names(user_ids: list[str]) -> dict[str, str]:
    """Batch-fetch names for a list of user IDs. Returns {user_id: display_name}."""
    if not user_ids:
        return {}
    db = await get_db()
    try:
        placeholders = ",".join("?" * len(user_ids))
        cursor = await db.execute(
            f"SELECT user_id, name FROM user_names WHERE user_id IN ({placeholders})",
            user_ids,
        )
        rows = await cursor.fetchall()
        result = {row["user_id"]: row["name"] for row in rows}
        # Fill unregistered users with fallback name
        for uid in user_ids:
            if uid not in result:
                result[uid] = f"用户{uid}"
        return result
    finally:
        await db.close()
```

- [ ] **Step 2: Commit**

```bash
git add lib/permission.py
git commit -m "feat: add user name helpers"
```

---

### Task 3: Fix get_history for group chat

**Files:**
- Modify: `lib/context.py:7-21`

- [ ] **Step 1: Rewrite get_history to support group-wide query**

Replace the existing `get_history` function:

```python
async def get_history(group_id: str, user_id: str) -> list[dict]:
    """Get recent conversation history. Group chats return all users; private chats filter by user."""
    db = await get_db()
    try:
        if group_id == "private":
            cursor = await db.execute(
                """SELECT role, content FROM conversation_memory
                   WHERE group_id = ? AND user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (group_id, user_id, MAX_MESSAGES),
            )
        else:
            cursor = await db.execute(
                """SELECT role, content, user_id FROM conversation_memory
                   WHERE group_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (group_id, MAX_MESSAGES),
            )
        rows = await cursor.fetchall()
        rows.reverse()
        result = []
        for row in rows:
            entry = {"role": row["role"], "content": row["content"]}
            if group_id != "private" and "user_id" in row.keys():
                entry["user_id"] = row["user_id"]
            result.append(entry)
        return result
    finally:
        await db.close()
```

Note: The `_trim_history` function also queries by `(group_id, user_id)` and should remain as-is — trimming is fine per-user since each user's messages are trimmed independently. Or, to be safe, we should also update `_trim_history` to trim by group_id only for groups. Actually, the current behavior where each user's messages are trimmed independently could lead to uneven counts per user. But this is the existing behavior and not part of the change scope. Leave `_trim_history` unchanged.

Actually wait — `save_message` and `save_turn` still save with `(group_id, user_id)`, but `_trim_history` trims by `(group_id, user_id)`. Since `get_history` for groups now returns ALL messages in the group regardless of user, the total message count could far exceed `MAX_MESSAGES` if there are many users. We should fix `_trim_history` for groups too.

Let's update `_trim_history` as well:

```python
async def _trim_history(group_id: str, user_id: str):
    """Remove old messages beyond MAX_MESSAGES for a group or (group, user) pair."""
    db = await get_db()
    try:
        if group_id == "private":
            await db.execute(
                """DELETE FROM conversation_memory WHERE id IN (
                    SELECT id FROM conversation_memory
                    WHERE group_id = ? AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET ?
                )""",
                (group_id, user_id, MAX_MESSAGES),
            )
        else:
            await db.execute(
                """DELETE FROM conversation_memory WHERE id IN (
                    SELECT id FROM conversation_memory
                    WHERE group_id = ?
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET ?
                )""",
                (group_id, MAX_MESSAGES),
            )
        await db.commit()
    finally:
        await db.close()
```

- [ ] **Step 2: Update save_turn and clear_history unchanged**

`save_turn` still saves with `(group_id, user_id)` for both bot and user messages. `clear_history` should also clear by group_id only for groups. Update `clear_history`:

```python
async def clear_history(group_id: str, user_id: str):
    """Clear conversation history. Group: clear entire group. Private: clear per-user."""
    db = await get_db()
    try:
        if group_id == "private":
            await db.execute(
                "DELETE FROM conversation_memory WHERE group_id = ? AND user_id = ?",
                (group_id, user_id),
            )
        else:
            await db.execute(
                "DELETE FROM conversation_memory WHERE group_id = ?",
                (group_id,),
            )
        await db.commit()
    finally:
        await db.close()
```

- [ ] **Step 3: Commit**

```bash
git add lib/context.py
git commit -m "fix: group chat history now includes all users, not just current speaker"
```

---

### Task 4: Update message formatting in ai_core

**Files:**
- Modify: `lib/ai_core.py:127-150` (_build_initial_messages)

- [ ] **Step 1: Add import for get_group_user_names**

In `lib/ai_core.py`, add import near the top:

```python
from lib.permission import get_group_user_names
```

- [ ] **Step 2: Rewrite _build_initial_messages to format group chat messages**

Read the current function. Replace `_build_initial_messages` signature and implementation:

```python
async def _build_initial_messages(
    system_prompt: str,
    history: list[dict],
    user_text: str,
    image_data: bytes | None,
    group_id: str,
) -> list[ChatMessage]:
    messages = []

    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))

    # Collect all user_ids from history for batch name lookup (group only)
    if group_id != "private" and history:
        user_ids = list(set(h["user_id"] for h in history if "user_id" in h))
        names = await get_group_user_names(user_ids)
    else:
        names = {}

    for h in history:
        if h["role"] == "user":
            user_id = h.get("user_id", "")
            if group_id != "private" and user_id:
                display_name = names.get(user_id, f"用户{user_id}")
                content = f"<群聊消息>{display_name}说：{h['content']}</群聊消息>"
            else:
                content = f"<用户消息>\n{h['content']}\n</用户消息>"
        else:
            content = h["content"]
        messages.append(ChatMessage(role=h["role"], content=content))

    wrapped_text = f"<用户消息>\n{user_text}\n</用户消息>"
    user_msg = ChatMessage(role="user", content=wrapped_text)
    if image_data:
        user_msg.image_data = image_data
    messages.append(user_msg)
    return messages
```

- [ ] **Step 3: Update callers of _build_initial_messages**

In `process_message`, find the call to `_build_initial_messages` (around line 63). Add `group_id` parameter:

```python
    messages = await _build_initial_messages(
        system_prompt=personality_system_prompt,
        history=history,
        user_text=msg_text,
        image_data=img_for_model if client.supports_vision else None,
        group_id=group_id,
    )
```

- [ ] **Step 4: Commit**

```bash
git add lib/ai_core.py
git commit -m "feat: format group chat history with speaker names"
```

---

### Task 5: Add /register command + update /help

**Files:**
- Modify: `src/plugins/chat/handlers.py`

- [ ] **Step 1: Add import**

On line 6, add `set_user_name` to the permission import. Change:
```python
from lib.permission import check_permission, set_permission, get_rate_limit_status, get_private_chat_enabled, set_private_chat_enabled, get_think_enabled, set_think_enabled, get_think_history
```
to:
```python
from lib.permission import check_permission, set_permission, get_rate_limit_status, get_private_chat_enabled, set_private_chat_enabled, get_think_enabled, set_think_enabled, get_think_history, set_user_name
```

- [ ] **Step 2: Add /register command**

Insert BEFORE `think_cmd = on_command("think", priority=10)`:

```python
register_cmd = on_command("register", priority=10)

@register_cmd.handle()
async def handle_register(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)

    # Parse message segments: @mention gives target_id, text gives name
    target_id = None
    name_parts = []
    for seg in args:
        if seg.type == "at":
            target_id = seg.data.get("qq", "")
        elif seg.type == "text":
            name_parts.append(str(seg))

    name = "".join(name_parts).strip()

    if not name:
        await register_cmd.finish("用法：/register <名称> 或 /register @某人 <名称>")

    if target_id:
        if user_id not in app_config.admins:
            await register_cmd.finish("权限不足，只能给自己注册名称。")
        await set_user_name(target_id, name)
        await register_cmd.finish(f"已为用户 {target_id} 绑定名称：{name}")
    else:
        await set_user_name(user_id, name)
        await register_cmd.finish(f"已绑定名称：{name}")
```

- [ ] **Step 3: Update /help text**

Add this line before the `/think` line:
```
/register <名称> - 给自己绑定用户名称（admin 可 @某人 给别人起名）
```

- [ ] **Step 4: Commit**

```bash
git add src/plugins/chat/handlers.py
git commit -m "feat: add /register command"
```

---

### Task 6: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add /register to command table**

In README's command table, before the `/think` row, add:

```markdown
| `/register <名称>` | 绑定用户名称（admin 可 @某人 给别人起名） |
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add /register to README"
```

---

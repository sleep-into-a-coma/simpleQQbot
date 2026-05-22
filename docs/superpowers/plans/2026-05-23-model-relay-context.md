# Model Relay Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a user switches models mid-conversation, the new model is informed that previous replies came from a different model, and tool call history is preserved in provider-agnostic format.

**Architecture:** Three new DB columns on `conversation_memory` (`model_name`, `tool_calls`, `tool_call_id`). A new `lib/relay.py` module with a single pure function. Changes to `context.py` (save/load), `ai_core.py` (relay injection + tool reconstruction), and `router.py` (pass model name).

**Tech Stack:** Python 3.11, aiosqlite, the existing `ChatMessage`/`ToolCall` dataclasses as canonical format.

---

### Task 1: DB Migration

**Files:**
- Modify: `lib/db.py:16-109`

- [ ] **Step 1: Add migration logic to init_db()**

After the existing `CREATE TABLE` block and before the settings INSERT block, add column migration:

```python
        # ----- auto migration: add columns if missing -----
        cursor = await db.execute("PRAGMA table_info(conversation_memory)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "model_name" not in columns:
            await db.execute(
                "ALTER TABLE conversation_memory ADD COLUMN model_name TEXT DEFAULT NULL"
            )
        if "tool_calls" not in columns:
            await db.execute(
                "ALTER TABLE conversation_memory ADD COLUMN tool_calls TEXT DEFAULT NULL"
            )
        if "tool_call_id" not in columns:
            await db.execute(
                "ALTER TABLE conversation_memory ADD COLUMN tool_call_id TEXT DEFAULT NULL"
            )
        # -------------------------------------------------
```

Insert this after line 95 (after the `CREATE TABLE` blocks end) and before line 97 (`from lib.config import load_config`).

- [ ] **Step 2: Verify migration runs cleanly**

Delete `data/bot.db` (or rename temporarily), then run:

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot && python -c "
import asyncio
from lib.db import init_db
asyncio.run(init_db())
print('DB init OK')
"
```

Expected: `DB init OK`, no errors.

- [ ] **Step 3: Verify migration is idempotent**

Run the same command again — should not error on duplicate columns (the `IF NOT EXISTS` column check prevents it).

- [ ] **Step 4: Commit**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot
git add lib/db.py
git commit -m "feat: add model_name, tool_calls, tool_call_id columns to conversation_memory"
```

---

### Task 2: New Module `lib/relay.py`

**Files:**
- Create: `lib/relay.py`

- [ ] **Step 1: Write the module**

```python
"""Model relay: detect cross-model conversation handoffs and generate relay prompts."""


def detect_relay(history: list[dict], current_model_name: str) -> str | None:
    """
    Scan history for assistant messages from a different model.
    Returns relay prompt string if a switch is detected, else None.
    """
    previous_models: set[str] = set()
    for h in history:
        if h["role"] == "assistant":
            model = h.get("model_name")
            if model and model != current_model_name:
                previous_models.add(model)

    if not previous_models:
        return None

    prev_list = ", ".join(sorted(previous_models))
    return (
        f"[接力提示] 之前的回复由模型 {prev_list} 生成，"
        f"现在由你（{current_model_name}）继续。"
        f"请保持对话风格和上下文的连贯。"
    )
```

- [ ] **Step 2: Verify module imports cleanly**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot && python -c "from lib.relay import detect_relay; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verify function logic with quick smoke test**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot && python -c "
from lib.relay import detect_relay

# No switch → None
h1 = [{'role': 'user', 'content': 'hi'}, {'role': 'assistant', 'content': 'hey', 'model_name': 'A'}]
assert detect_relay(h1, 'A') is None, 'same model should return None'

# Switch detected
h2 = [{'role': 'assistant', 'content': 'hey', 'model_name': 'A'}]
r = detect_relay(h2, 'B')
assert r is not None, 'different model should return relay prompt'
assert 'A' in r and 'B' in r, 'relay prompt should mention both models'
print('All checks pass')
"
```

Expected: `All checks pass`

- [ ] **Step 4: Commit**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot
git add lib/relay.py
git commit -m "feat: add relay detection module for cross-model handoff"
```

---

### Task 3: Update `lib/context.py` — Save and Load

**Files:**
- Modify: `lib/context.py:7-103`

- [ ] **Step 1: Update save_message() signature and body**

Replace `save_message` (lines 38-48) with:

```python
async def save_message(group_id: str, user_id: str, role: str, content: str,
                       model_name: str | None = None,
                       tool_calls: list | None = None,
                       tool_call_id: str | None = None):
    """Save a single message to conversation history."""
    import json
    db = await get_db()
    try:
        tool_calls_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
        await db.execute(
            """INSERT INTO conversation_memory
               (group_id, user_id, role, content, model_name, tool_calls, tool_call_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (group_id, user_id, role, content, model_name, tool_calls_json, tool_call_id),
        )
        await db.commit()
    finally:
        await db.close()
```

- [ ] **Step 2: Update save_turn() signature and call**

Replace `save_turn` (lines 51-55) with:

```python
async def save_turn(group_id: str, user_id: str, user_msg: str, assistant_msg: str,
                    model_name: str | None = None,
                    tool_calls: list | None = None):
    """Save a complete conversation turn (user + assistant)."""
    await save_message(group_id, user_id, "user", user_msg)
    await save_message(group_id, user_id, "assistant", assistant_msg,
                       model_name=model_name, tool_calls=tool_calls)
    await _trim_history(group_id, user_id)
```

- [ ] **Step 3: Update get_history() to return new columns**

In `get_history()` (lines 7-34), update the SQL queries and result building.

Line 12-13 (private query): change `SELECT role, content` to `SELECT role, content, model_name, tool_calls, tool_call_id`.

Line 19-20 (group query): same change.

Lines 27-33 (result building): replace with:

```python
        result = []
        for row in rows:
            entry = {"role": row["role"], "content": row["content"]}
            if group_id != "private" and "user_id" in row.keys():
                entry["user_id"] = row["user_id"]
            if row["model_name"]:
                entry["model_name"] = row["model_name"]
            if row["tool_calls"]:
                import json
                try:
                    entry["tool_calls"] = json.loads(row["tool_calls"])
                except json.JSONDecodeError:
                    pass  # silently skip malformed JSON
            if row["tool_call_id"]:
                entry["tool_call_id"] = row["tool_call_id"]
            result.append(entry)
        return result
```

The `import json` at function level is intentional — `json` is not otherwise imported in this file.

- [ ] **Step 4: Verify all existing callers still work**

Existing callers pass positional args only, which still match. Quick check:

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot && python -c "
import asyncio
from lib.db import init_db
from lib.context import save_turn, get_history, save_message
async def test():
    await init_db()
    # old-style call (no model_name)
    await save_turn('test-g', 'test-u', 'hello', 'world')
    h = await get_history('test-g', 'test-u')
    assert len(h) == 2
    assert h[0]['role'] == 'user'
    assert h[0].get('model_name') is None
    assert h[1]['role'] == 'assistant'
    # new-style call
    await save_turn('test-g', 'test-u', 'hi', 'hey', model_name='A')
    h2 = await get_history('test-g', 'test-u')
    # should have 4 messages now (get_history returns reversed)
    print('OK -', len(h2), 'messages in history')
asyncio.run(test())
"
```

Expected: `OK - 4 messages in history`

- [ ] **Step 5: Commit**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot
git add lib/context.py
git commit -m "feat: store and load model_name, tool_calls, tool_call_id in conversation history"
```

---

### Task 4: Update `lib/ai_core.py` — Relay Injection and Tool Reconstruction

**Files:**
- Modify: `lib/ai_core.py:31-168`

- [ ] **Step 1: Update _build_initial_messages() signature and body**

Add `current_model_name: str` parameter. Add relay prompt injection and tool_call reconstruction. Also handle `tool_call_id` from history.

Full replacement (lines 132-168):

```python
async def _build_initial_messages(
    system_prompt: str,
    history: list[dict],
    user_text: str,
    image_data: bytes | None,
    group_id: str,
    current_model_name: str,
) -> list[ChatMessage]:
    from lib.relay import detect_relay

    messages = []

    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))

    # Inject relay handoff if model switch detected
    relay = detect_relay(history, current_model_name)
    if relay:
        messages.append(ChatMessage(role="user", content=relay))

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
            messages.append(ChatMessage(role=h["role"], content=content))
        else:
            # Rebuild tool_calls from JSON if present
            tc_list = []
            if h.get("tool_calls"):
                for tc_data in h["tool_calls"]:
                    tc_list.append(ToolCall(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=tc_data["arguments"],
                    ))
            messages.append(ChatMessage(
                role=h["role"],
                content=h["content"],
                tool_calls=tc_list,
                tool_call_id=h.get("tool_call_id"),
            ))

    wrapped_text = f"<用户消息>\n{user_text}\n</用户消息>"
    user_msg = ChatMessage(role="user", content=wrapped_text)
    if image_data:
        user_msg.image_data = image_data
    messages.append(user_msg)
    return messages
```

- [ ] **Step 2: Update process_message() to pass model_name**

In `process_message()` (line 31), the function already receives `model_name: str | None`. After resolving the model at line 52, the `model_config.name` is the effective model ID. Pass it to `_build_initial_messages()`.

At line 65-71, `_build_initial_messages()` call — add `current_model_name=model_config.name`:

```python
    # Build messages
    messages = await _build_initial_messages(
        system_prompt=personality_system_prompt,
        history=history,
        user_text=msg_text,
        image_data=img_for_model if client.supports_vision else None,
        group_id=group_id,
        current_model_name=model_config.name,
    )
```

- [ ] **Step 3: Save intermediate tool call messages to DB**

In `process_message()`, the tool calling loop (lines 79-117) builds intermediate `ChatMessage` objects but doesn't persist them. Add `save_message()` calls inside the loop.

After line 88 (`messages.append(ChatMessage(...))` for assistant with tool_calls), add:

```python
            # Persist intermediate assistant message with tool calls
            tc_list = [{"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                       for tc in response.tool_calls]
            await save_message(group_id, user_id, "assistant",
                             response.content or "",
                             model_name=model_config.name, tool_calls=tc_list)
```

After line 101 (`messages.append(ChatMessage(...))` for tool result), add:

```python
            # Persist intermediate tool result message
            await save_message(group_id, user_id, "tool", tool_result_text,
                             tool_call_id=tc.id)
```

Note: `save_message` from `lib.context` needs to be imported. Add at top of `ai_core.py`:
```python
from lib.context import save_message
```

- [ ] **Step 4: Verify import and no syntax errors**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot && python -c "
import ast
with open('lib/ai_core.py') as f:
    ast.parse(f.read())
print('Syntax OK')
"
```

Expected: `Syntax OK`

- [ ] **Step 5: Commit**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot
git add lib/ai_core.py
git commit -m "feat: inject relay prompt on model switch and reconstruct tool calls from history"
```

---

### Task 5: Verify `src/plugins/chat/router.py` — Model Name Pass-Through

**Files:**
- Verify: `src/plugins/chat/router.py:122-133`

- [ ] **Step 1: Confirm model name already flows through correctly**

`router.py` already passes `model_name=resolved_model` to `process_message()` (line 130). Inside `process_message()`, `resolve_model(app_config, model_name)` returns `model_config` where `model_config.name == resolved_model`. No code change needed — the value flows from router to `_build_initial_messages()` through the existing parameter.

- [ ] **Step 2: Mark verified**

No commit needed for this task (no code changes).

---

### Task 6: End-to-End Verification

**Files:** None (manual verification)

- [ ] **Step 1: Start the bot in test mode**

Verify the bot starts without errors after all changes.

- [ ] **Step 2: Single model conversation (no relay)**

Send a message with `/A hello` — verify normal response, no relay prompt visible.

Check DB:
```sql
SELECT role, model_name FROM conversation_memory ORDER BY id DESC LIMIT 5;
```
Expected: user messages have NULL model_name, assistant messages have `"A"`.

- [ ] **Step 3: Model switch triggers relay**

1. Send message with `/A hello` (model A responds)
2. Send `/model B` to switch
3. Send message with `/B what did we just talk about` (or just a normal message)

Verify the relay prompt is injected. Check DB that the last assistant message has `model_name = "B"`.

- [ ] **Step 4: Verify relay prompt only appears for the FIRST message after switch**

After step 3, send another message with model B — the relay prompt should NOT appear again (because there's now a B assistant message in history).

- [ ] **Step 5: Tool call history preservation (search)**

1. Send a message that triggers search (with model A): `/A search for Python`
2. Verify the response includes search results
3. Switch to model B: `/model B`
4. Send `/B thanks` — the history should include the full search tool chain

Check DB:
```sql
SELECT role, model_name, tool_calls, tool_call_id FROM conversation_memory
WHERE group_id = '<test-group>' ORDER BY id;
```
Expected: assistant messages with search tool calls have `tool_calls` JSON, and tool result messages have `tool_call_id`.

- [ ] **Step 6: Commit any fixes**

If any issues found during verification, fix and commit.

---

### Task 7: Clean Up Test Data

**Files:** None

- [ ] **Step 1: Remove test data from DB**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot && python -c "
import asyncio
from lib.db import get_db
async def clean():
    db = await get_db()
    try:
        await db.execute('DELETE FROM conversation_memory WHERE group_id LIKE ?', ('test-%',))
        await db.commit()
        print('Test data cleaned')
    finally:
        await db.close()
asyncio.run(clean())
"
```

- [ ] **Step 2: Final commit if needed**

# Model Relay: Cross-Model Conversation Continuity

## Problem

When a user switches models mid-conversation (`/model B`), the new model receives the full conversation history but has no awareness that previous assistant replies came from a different model. Context and personality continuity is lost.

The goal is **relay, not switch**: Model B should know it's taking over from Model A, receiving enough context to maintain conversational coherence.

## Design Principle

The internal `ChatMessage` / `ToolCall` dataclasses already serve as a provider-agnostic canonical format. Each client's `_build_messages()` translates from this internal format to its provider-specific API format. Therefore:

- **No format conversion code is needed.** Tool calls are stored in the canonical `ToolCall(id, name, arguments)` format and each client serializes them its own way.
- **New models added via .env** (or new providers with a new client class) **automatically participate in relay** — no changes to the relay layer.
- **The relay layer only does two things**: tag each assistant message with its source model, and inject a handoff note when a model switch is detected.

## Database Migration

```sql
ALTER TABLE conversation_memory ADD COLUMN model_name TEXT DEFAULT NULL;
ALTER TABLE conversation_memory ADD COLUMN tool_calls TEXT DEFAULT NULL;
```

Row semantics:

| message role | model_name | tool_calls |
|---|---|---|
| user | NULL | NULL |
| assistant (plain text) | `"A"` | NULL |
| assistant (with tool calls) | `"A"` | `[{"id":"...", "name":"web_search", "arguments":{...}}]` |
| tool (search result) | NULL | NULL (linked via `tool_call_id` on ChatMessage) |

Existing rows have `NULL` for both columns — backward compatible.

## New Module: `lib/relay.py`

Single function:

```python
def detect_relay(history: list[dict], current_model_name: str) -> str | None:
    """
    Scan history for assistant messages from a different model.
    Returns relay prompt string if a switch is detected, else None.
    """
```

Relay prompt format:
> `[接力提示] 之前的回复由模型 {previous_model_names} 生成，现在由你（{current_model}）继续。请保持对话风格和上下文的连贯。`

Where `previous_model_names` is the deduplicated list of model IDs found in history (e.g., "A, C" if user went A→B→C→D, and current is D — only A and C generated assistant messages in the loaded window).

## Changes to `lib/context.py`

### save_message()

Add optional parameters: `model_name: str | None = None`, `tool_calls: list | None = None`.

INSERT writes the new columns. `tool_calls` is serialized as JSON string.

### save_turn()

Add `model_name` and `tool_calls` params, passed through to `save_message()` for the assistant half.

### get_history()

Extend returned dicts to include `model_name` (str or None) and `tool_calls` (parsed JSON list or None).

## Changes to `lib/ai_core.py`

### _build_initial_messages()

New parameter: `current_model_name: str`.

Two new behaviors:

1. **Rebuild tool_calls from JSON:** For history entries with `tool_calls` not None, create `ToolCall` objects and attach to `ChatMessage`.

2. **Inject relay prompt:** Call `detect_relay(history, current_model_name)`. If non-None, insert a user message with the relay prompt before the history messages.

### process_message()

Pass `model_config.name` down to `_build_initial_messages()`.

### Tool call intermediate messages

The internal tool calling loop (search round-trips) in `process_message()` already builds `ChatMessage` objects with `tool_calls` and `tool_call_id` fields. Currently these intermediate messages live only in memory during the loop. With this change, each assistant+tool message pair is saved to DB within the loop via `save_message()` so the full tool chain can be reconstructed on history reload.

## Changes to `src/plugins/chat/router.py`

### handle_chat()

Pass `model_config.name` through the chain. The resolved model config is already available at Step 4-8 of the handler; it just needs to reach `_build_initial_messages()` via `process_message()`.

## Data Flow

```
User types /B hello
        │
        ▼
router.py → resolve model B
        │
        ▼
process_message(model="B")
  ├── get_history() → [{role, content, model_name, tool_calls}, ...]
  ├── _build_initial_messages(history, current_model="B")
  │     ├── detect_relay(history, "B") → "之前的回复由模型A生成..."
  │     ├── inject relay user message
  │     └── rebuild ToolCall objects from JSON
  ├── client_B.chat(messages)  ← client serializes in its own format
  └── save_turn(model_name="B", tool_calls=...)
```

## What This Does NOT Cover

- **Cross-session relay:** Relay only activates within the same conversation window (up to 20 turns in history). If history is cleared or ages out, the relay context is lost. This is intentional per the agreed scope.
- **Personality relay:** Switching personalities (`/set`) is a separate concern and not part of this design.
- **Provider-specific feature preservation:** Things unique to one provider (e.g., Anthropic extended thinking) are not relayed — only text and tool calls are.

## Migration Strategy

1. In `lib/db.py` init, check `PRAGMA table_info(conversation_memory)` for `model_name` column
2. If absent, run `ALTER TABLE conversation_memory ADD COLUMN model_name TEXT DEFAULT NULL`
3. Same for `tool_calls`
4. Old rows with NULL model_name/tool_calls are handled gracefully by all code paths
5. The migration runs automatically on first bot startup after upgrade

## Error Handling

- JSON parse failure on `tool_calls` column: log warning, treat as NULL
- Empty or malformed relay prompt: skip injection silently
- Model name not in config (deleted model): treat as unknown, skip in relay prompt

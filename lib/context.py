import json
import logging

from lib.db import get_db

logger = logging.getLogger(__name__)

MAX_HISTORY_ROUNDS = 20
MAX_MESSAGES = MAX_HISTORY_ROUNDS * 2  # user + assistant per round


async def get_history(group_id: str, user_id: str) -> list[dict]:
    """Get recent conversation history. Group chats return all users; private chats filter by user."""
    db = await get_db()
    try:
        if group_id == "private":
            cursor = await db.execute(
                """SELECT role, content, model_name, tool_calls, tool_call_id FROM conversation_memory
                   WHERE group_id = ? AND user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (group_id, user_id, MAX_MESSAGES),
            )
        else:
            cursor = await db.execute(
                """SELECT role, content, model_name, tool_calls, tool_call_id, user_id FROM conversation_memory
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
            if row["model_name"]:
                entry["model_name"] = row["model_name"]
            if row["tool_calls"]:
                try:
                    entry["tool_calls"] = json.loads(row["tool_calls"])
                except json.JSONDecodeError:
                    logger.warning("Malformed tool_calls JSON in conversation_memory row")
            if row["tool_call_id"]:
                entry["tool_call_id"] = row["tool_call_id"]
            result.append(entry)
        return result
    finally:
        await db.close()


async def save_message(group_id: str, user_id: str, role: str, content: str,
                       model_name: str | None = None,
                       tool_calls: list | None = None,
                       tool_call_id: str | None = None):
    """Save a single message to conversation history."""
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


async def save_turn(group_id: str, user_id: str, user_msg: str, assistant_msg: str,
                    model_name: str | None = None,
                    tool_calls: list | None = None):
    """Save a complete conversation turn (user + assistant)."""
    await save_message(group_id, user_id, "user", user_msg)
    await save_message(group_id, user_id, "assistant", assistant_msg,
                       model_name=model_name, tool_calls=tool_calls)
    await _trim_history(group_id, user_id)


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


async def log_reply(
    group_id: str,
    user_id: str,
    personality_name: str,
    model_name: str,
    has_image: bool,
    has_search: bool,
    response_time_ms: int,
    user_msg: str,
    reply: str,
):
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO reply_log
               (group_id, user_id, personality_name, model_name,
                has_image, has_search, response_time_ms, user_msg, reply)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (group_id, user_id, personality_name, model_name,
             1 if has_image else 0, 1 if has_search else 0,
             response_time_ms, user_msg[:500], reply[:500]),
        )
        await db.commit()
    finally:
        await db.close()

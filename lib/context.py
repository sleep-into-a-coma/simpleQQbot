from lib.db import get_db

MAX_HISTORY_ROUNDS = 20
MAX_MESSAGES = MAX_HISTORY_ROUNDS * 2  # user + assistant per round


async def get_history(group_id: str, user_id: str) -> list[dict]:
    """Get recent conversation history for a (group, user) pair."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT role, content FROM conversation_memory
               WHERE group_id = ? AND user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (group_id, user_id, MAX_MESSAGES),
        )
        rows = await cursor.fetchall()
        rows.reverse()  # oldest first for LLM context
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    finally:
        await db.close()


async def save_message(group_id: str, user_id: str, role: str, content: str):
    """Save a single message to conversation history."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO conversation_memory (group_id, user_id, role, content) VALUES (?, ?, ?, ?)",
            (group_id, user_id, role, content),
        )
        await db.commit()
    finally:
        await db.close()


async def save_turn(group_id: str, user_id: str, user_msg: str, assistant_msg: str):
    """Save a complete conversation turn (user + assistant)."""
    await save_message(group_id, user_id, "user", user_msg)
    await save_message(group_id, user_id, "assistant", assistant_msg)
    await _trim_history(group_id, user_id)


async def _trim_history(group_id: str, user_id: str):
    """Remove old messages beyond MAX_MESSAGES for a (group, user) pair."""
    db = await get_db()
    try:
        await db.execute(
            """DELETE FROM conversation_memory WHERE id IN (
                SELECT id FROM conversation_memory
                WHERE group_id = ? AND user_id = ?
                ORDER BY created_at DESC
                LIMIT -1 OFFSET ?
            )""",
            (group_id, user_id, MAX_MESSAGES),
        )
        await db.commit()
    finally:
        await db.close()


async def clear_history(group_id: str, user_id: str):
    """Clear all conversation history for a (group, user) pair."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM conversation_memory WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
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

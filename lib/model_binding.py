from lib.db import get_db


async def get_model_binding(group_id: str, user_id: str, default_model: str) -> str:
    """Resolve model binding: check per-user > per-group > default."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT model_name FROM model_bindings WHERE target_type = 'user' AND target_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return row["model_name"]

        cursor = await db.execute(
            "SELECT model_name FROM model_bindings WHERE target_type = 'group' AND target_id = ?",
            (group_id,),
        )
        row = await cursor.fetchone()
        if row:
            return row["model_name"]
    finally:
        await db.close()
    return default_model


async def set_model_binding(target_type: str, target_id: str, model_name: str):
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO model_bindings (target_type, target_id, model_name) VALUES (?, ?, ?)
               ON CONFLICT(target_type, target_id) DO UPDATE SET model_name = ?""",
            (target_type, target_id, model_name, model_name),
        )
        await db.commit()
    finally:
        await db.close()

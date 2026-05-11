from lib.config import AppConfig, PersonalityConfig
from lib.db import get_db


def get_default_personality(config: AppConfig) -> PersonalityConfig:
    for p in config.personalities:
        if p.name == config.default_personality:
            return p
    return config.personalities[0]


async def get_personality(group_id: str, user_id: str, config: AppConfig) -> PersonalityConfig:
    """Resolve personality: check per-user binding > per-group binding > default."""
    db = await get_db()
    try:
        # Check user-level binding first
        cursor = await db.execute(
            "SELECT personality_name FROM personality_bindings WHERE target_type = 'user' AND target_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            p = _find_by_name(row["personality_name"], config)
            if p:
                return p

        # Check group-level binding
        cursor = await db.execute(
            "SELECT personality_name FROM personality_bindings WHERE target_type = 'group' AND target_id = ?",
            (group_id,),
        )
        row = await cursor.fetchone()
        if row:
            p = _find_by_name(row["personality_name"], config)
            if p:
                return p
    finally:
        await db.close()

    return get_default_personality(config)


async def bind_personality(target_type: str, target_id: str, personality_name: str, config: AppConfig):
    """Bind a personality to a user or group. Validates personality exists."""
    p = _find_by_name(personality_name, config)
    if not p:
        raise ValueError(f"未找到人格: {personality_name}")

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO personality_bindings (target_type, target_id, personality_name) VALUES (?, ?, ?)
               ON CONFLICT(target_type, target_id) DO UPDATE SET personality_name = ?""",
            (target_type, target_id, personality_name, personality_name),
        )
        await db.commit()
    finally:
        await db.close()


def _find_by_name(name: str, config: AppConfig) -> PersonalityConfig | None:
    for p in config.personalities:
        if p.name == name:
            return p
    return None

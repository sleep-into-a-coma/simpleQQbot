import time
from collections import defaultdict
from lib.config import AppConfig
from lib.db import get_db


# In-memory rate limit counters (reset on restart)
_user_counters: dict[str, list[float]] = defaultdict(list)
_group_counters: dict[str, list[float]] = defaultdict(list)

# Periodic cleanup to prevent unbounded key growth
_cleanup_counter = 0
_CLEANUP_INTERVAL = 1000


def _cleanup_old(ts_list: list[float], window: float = 60.0) -> list[float]:
    """Remove timestamps older than window seconds."""
    now = time.time()
    return [t for t in ts_list if now - t < window]


def _sweep_empty_counters():
    """Remove entries whose timestamp lists are empty after cleanup."""
    for counters in (_user_counters, _group_counters):
        empty = [k for k, v in counters.items() if not v]
        for k in empty:
            del counters[k]


def check_rate_limit(group_id: str, user_id: str, config: AppConfig) -> tuple[bool, str]:
    """Check rate limits. Returns (allowed, reason_if_blocked)."""
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter >= _CLEANUP_INTERVAL:
        _sweep_empty_counters()
        _cleanup_counter = 0

    now = time.time()

    user_key = f"{group_id}:{user_id}"
    user_ts = _cleanup_old(_user_counters[user_key])
    if not user_ts:
        del _user_counters[user_key]
    if len(user_ts) >= config.rate_limit_user_per_minute:
        return False, "你的消息太频繁了，请稍后再试~"
    user_ts.append(now)
    _user_counters[user_key] = user_ts

    group_ts = _cleanup_old(_group_counters[group_id])
    if not group_ts:
        del _group_counters[group_id]
    if len(group_ts) >= config.rate_limit_group_per_minute:
        return False, "本群消息太频繁了，请稍后再试~"
    group_ts.append(now)
    _group_counters[group_id] = group_ts

    return True, ""


async def check_permission(group_id: str, user_id: str, config: AppConfig) -> tuple[bool, str]:
    """Check if user/group is allowed. Dynamic rules > static rules, block > allow."""
    has_dynamic_allow = False

    # Check dynamic rules (from DB)
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT target_type, level FROM permissions WHERE target_id IN (?, ?)",
            (user_id, group_id),
        )
        rows = await cursor.fetchall()
        for row in rows:
            if row["level"] == "block":
                return False, "你已被禁止使用 Bot。"
            if row["level"] == "allow":
                has_dynamic_allow = True
    finally:
        await db.close()

    if has_dynamic_allow:
        return True, ""

    # Static whitelist check (if whitelist is populated, only those in it pass)
    if config.whitelist_users and user_id not in config.whitelist_users:
        return False, "你没有使用 Bot 的权限。"
    if config.whitelist_groups and group_id not in config.whitelist_groups:
        return False, "本群没有使用 Bot 的权限。"

    return True, ""


async def set_permission(target_type: str, target_id: str, level: str):
    """Insert or update a dynamic permission rule."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO permissions (target_type, target_id, level) VALUES (?, ?, ?)
               ON CONFLICT(target_type, target_id) DO UPDATE SET level = ?""",
            (target_type, target_id, level, level),
        )
        await db.commit()
    finally:
        await db.close()


def get_rate_limit_status(group_id: str, user_id: str, config: AppConfig) -> dict:
    """Get current rate limit usage for /status command."""
    user_key = f"{group_id}:{user_id}"
    user_used = len(_cleanup_old(_user_counters.get(user_key, [])))
    group_used = len(_cleanup_old(_group_counters.get(group_id, [])))
    return {
        "user_used": user_used,
        "user_limit": config.rate_limit_user_per_minute,
        "group_used": group_used,
        "group_limit": config.rate_limit_group_per_minute,
    }


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

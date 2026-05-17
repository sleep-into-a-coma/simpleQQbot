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

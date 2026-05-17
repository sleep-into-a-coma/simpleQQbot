import aiosqlite
from pathlib import Path

DB_PATH = Path("data/bot.db")


async def get_db() -> aiosqlite.Connection:
    """Get a database connection. Caller must close it."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db():
    """Create tables if they don't exist."""
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reply_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                personality_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                has_image BOOLEAN DEFAULT 0,
                has_search BOOLEAN DEFAULT 0,
                response_time_ms INTEGER,
                user_msg TEXT,
                reply TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT 'allow',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(target_type, target_id)
            );

            CREATE TABLE IF NOT EXISTS personality_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                personality_name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(target_type, target_id)
            );

            CREATE TABLE IF NOT EXISTS model_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(target_type, target_id)
            );

            CREATE INDEX IF NOT EXISTS idx_memory_lookup
                ON conversation_memory(group_id, user_id, created_at);

            CREATE INDEX IF NOT EXISTS idx_reply_log_time
                ON reply_log(created_at);

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS think_history (
                group_id TEXT NOT NULL,
                slot INTEGER NOT NULL,
                user_msg TEXT,
                thinking TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_id, slot)
            );

            CREATE TABLE IF NOT EXISTS user_names (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
        """)
        await db.commit()
        from lib.config import load_config
        config = load_config()
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("private_chat_enabled", "1" if config.private_chat_enabled else "0"),
        )
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("think_enabled", "1" if config.think_enabled else "0"),
        )
        await db.commit()
    finally:
        await db.close()

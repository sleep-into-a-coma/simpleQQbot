import pytest_asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import init_db, DB_PATH


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Initialize test database before each test."""
    # Use a test-specific DB path to avoid clobbering dev data
    import lib.db as db_module
    original_path = db_module.DB_PATH
    test_path = Path("data/test_bot.db")
    db_module.DB_PATH = test_path

    test_path.unlink(missing_ok=True)
    await init_db()
    yield
    test_path.unlink(missing_ok=True)
    db_module.DB_PATH = original_path

import pytest
from lib.context import save_turn, get_history, clear_history, save_message


@pytest.mark.asyncio
async def test_save_and_get_history():
    await save_turn("group1", "user1", "hello", "hi there")
    history = await get_history("group1", "user1")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "hi there"


@pytest.mark.asyncio
async def test_history_isolation():
    await save_turn("group1", "user1", "msg1", "reply1")
    await save_turn("group1", "user2", "msg2", "reply2")
    h1 = await get_history("group1", "user1")
    assert len(h1) == 2
    assert h1[0]["content"] == "msg1"


@pytest.mark.asyncio
async def test_clear_history():
    await save_message("g1", "u1", "user", "msg")
    await clear_history("g1", "u1")
    history = await get_history("g1", "u1")
    assert len(history) == 0

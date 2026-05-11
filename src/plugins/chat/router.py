from nonebot import on_message
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent
import httpx
import time

from lib.context import get_history, save_turn, log_reply
from lib.permission import check_permission, check_rate_limit
from lib.personality import get_personality
from lib.ai_core import process_message, _vision_fallback
from lib.tools.search import format_search_sources
from lib.model_binding import get_model_binding
from lib.models.factory import resolve_model
from . import app_config


async def _extract_user_text(event: MessageEvent) -> str:
    """Extract text content from message, removing CQ codes and image segments."""
    text_parts = []
    for seg in event.message:
        if seg.type == "text":
            text_parts.append(str(seg))
    return "".join(text_parts).strip()


async def _extract_image_data(event: MessageEvent) -> bytes | None:
    """Extract first image from message. Returns raw bytes or None."""
    for seg in event.message:
        if seg.type == "image":
            url = seg.data.get("url", "")
            if url:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return resp.content
    return None


def _format_metadata(personality_name: str, model_name: str, has_search: bool, has_image: bool, response_time_ms: int) -> str:
    """Format the metadata footer line."""
    parts = []
    if has_search:
        parts.append("🔍搜索")
    if has_image:
        parts.append("🖼识图")
    parts.append(personality_name)
    parts.append(model_name)
    parts.append(f"{response_time_ms / 1000:.1f}s")
    return " | ".join(parts)


# Message handler: catch all non-command messages
chat_handler = on_message(priority=99, block=False)


@chat_handler.handle()
async def handle_chat(event: MessageEvent):
    user_text = await _extract_user_text(event)
    if not user_text and not any(seg.type == "image" for seg in event.message):
        return

    group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else "private"
    user_id = str(event.user_id)

    # Step 1: Permission check
    allowed, reason = await check_permission(group_id, user_id, app_config)
    if not allowed:
        await chat_handler.finish(reason)

    # Step 2: Rate limit check
    allowed, reason = check_rate_limit(group_id, user_id, app_config)
    if not allowed:
        await chat_handler.finish(reason)

    # Step 3: Check for trigger alias (/A /B /C)
    trigger_model = None
    msg_text = user_text
    for alias, model_name in app_config.aliases.items():
        if user_text.startswith(f"/{alias} "):
            trigger_model = model_name
            msg_text = user_text[len(alias) + 2:].strip()
            break

    # Step 4: Resolve persistent model binding
    resolved_model = trigger_model or await get_model_binding(group_id, user_id, app_config.default_model)

    # Step 5: Load personality
    personality = await get_personality(group_id, user_id, app_config)

    # Step 6: Load history
    history = await get_history(group_id, user_id)

    # Step 7: Extract image
    image_data = await _extract_image_data(event)

    # Step 8: Vision fallback is handled inside process_message

    # Step 9: Process with AI
    result = await process_message(
        user_text=msg_text,
        image_data=image_data,
        group_id=group_id,
        user_id=user_id,
        history=history,
        personality_system_prompt=personality.system_prompt,
        model_name=resolved_model,
        app_config=app_config,
    )

    # Step 10: Save conversation turn
    await save_turn(group_id, user_id, user_text, result["content"])

    # Step 11: Log reply metadata
    await log_reply(
        group_id=group_id,
        user_id=user_id,
        personality_name=personality.name,
        model_name=result["model_name"],
        has_image=result["has_image"],
        has_search=result["has_search"],
        response_time_ms=result["response_time_ms"],
        user_msg=user_text,
        reply=result["content"],
    )

    # Step 12: Build and send reply
    reply_text = result["content"]
    metadata = _format_metadata(
        personality.name,
        result["model_name"],
        result["has_search"],
        result["has_image"],
        result["response_time_ms"],
    )
    sources = format_search_sources(result["sources"]) if result["has_search"] else ""
    full_reply = f"{reply_text}\n\n{metadata}{sources}"

    await chat_handler.finish(full_reply)

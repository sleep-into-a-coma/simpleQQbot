import time
from lib.config import AppConfig
from lib.models.base import ChatMessage, ChatResponse, ToolCall, ToolDefinition
from lib.models.factory import resolve_model, create_client
from lib.errors import BotException
from lib.permission import get_group_user_names
from lib.tools.search import (
    SEARCH_TOOL_DEFINITION,
    create_search_backend,
    format_search_results,
    format_search_sources,
    SearchResult,
)
from lib.context import save_message

_cached_backend = None
_cached_config_key = None


def _get_search_backend(config):
    """Create or reuse the search backend. Config rarely changes after startup."""
    global _cached_backend, _cached_config_key
    key = (config.search_backend, config.bing_api_key, config.searxng_url, config.proxy_url)
    if _cached_backend is None or _cached_config_key != key:
        _cached_backend = create_search_backend(config)
        _cached_config_key = key
    return _cached_backend


async def _vision_fallback(image_data: bytes, config: AppConfig) -> str:
    """Use vision fallback model to describe an image."""
    client = create_client(config.vision_fallback, proxy_url=config.proxy_url)
    msg = ChatMessage(
        role="user",
        content="<user_message>\n请用中文一句话描述这张图片的内容。\n</user_message>",
        image_data=image_data,
    )
    try:
        response = await client.chat([msg], [])
        return response.content
    except BotException:
        return "[图片描述失败，请直接输入文字描述]"


async def process_message(
    user_text: str,
    image_data: bytes | None,
    group_id: str,
    user_id: str,
    history: list[dict],
    personality_system_prompt: str,
    model_name: str | None,
    app_config: AppConfig,
    think_triggered: bool = False,
) -> dict:
    """
    Main AI processing pipeline. Handles vision fallback, tool calling loop.
    Returns: {content, model_name, has_search, has_image, response_time_ms, sources}
    """
    start_time = time.time()
    has_image = image_data is not None
    has_search = False
    sources: list[SearchResult] = []

    # Resolve model
    model_config, client = resolve_model(app_config, model_name)

    # Create or reuse search backend
    search_backend = None
    if app_config.search_enabled:
        try:
            search_backend = _get_search_backend(app_config)
        except ValueError:
            search_backend = None

    # Vision fallback: if image present and model doesn't support vision
    msg_text = user_text
    img_for_model = image_data
    if image_data and not client.supports_vision:
        desc = await _vision_fallback(image_data, app_config)
        prefix = f"[图片描述：{desc}]"
        msg_text = f"{prefix}\n{user_text}" if user_text else prefix
        img_for_model = None
        has_image = True  # still count as image processing

    # Build messages
    messages = await _build_initial_messages(
        system_prompt=personality_system_prompt,
        history=history,
        user_text=msg_text,
        image_data=img_for_model if client.supports_vision else None,
        group_id=group_id,
        current_model_name=model_config.name,
    )

    # Build tools list
    tools = []
    if app_config.search_enabled:
        tools.append(SEARCH_TOOL_DEFINITION)

    # Tool calling loop
    max_rounds = 5
    for _ in range(max_rounds):
        response = await client.chat(messages, tools if tools else None, enable_thinking=think_triggered)

        if response.tool_calls:
            messages.append(ChatMessage(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))

            # Persist intermediate assistant message with tool calls
            tc_list = [{"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                       for tc in response.tool_calls]
            await save_message(group_id, user_id, "assistant",
                             response.content or "",
                             model_name=model_config.name, tool_calls=tc_list)

            for tc in response.tool_calls:
                if tc.name == "web_search":
                    has_search = True
                    query = tc.arguments.get("query", "")
                    if search_backend:
                        results = search_backend.search(query, app_config.search_max_results)
                    else:
                        results = []
                    if results:
                        sources = results
                    tool_result_text = format_search_results(results)
                    messages.append(ChatMessage(
                        role="tool",
                        content=tool_result_text,
                        tool_call_id=tc.id,
                    ))

                    # Persist intermediate tool result message
                    await save_message(group_id, user_id, "tool", tool_result_text,
                                     tool_call_id=tc.id)
        else:
            # No more tool calls — final response
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "content": response.content,
                "thinking": response.thinking,
                "model_name": model_config.name,
                "has_search": has_search,
                "has_image": has_image,
                "response_time_ms": elapsed_ms,
                "sources": sources,
            }

    # Fallback if loop exhausted
    elapsed_ms = int((time.time() - start_time) * 1000)
    return {
        "content": "处理超时，请重试。",
        "thinking": "",
        "model_name": model_config.name,
        "has_search": has_search,
        "has_image": has_image,
        "response_time_ms": elapsed_ms,
        "sources": sources,
    }


async def _build_initial_messages(
    system_prompt: str,
    history: list[dict],
    user_text: str,
    image_data: bytes | None,
    group_id: str,
    current_model_name: str,
) -> list[ChatMessage]:
    from lib.relay import detect_relay

    messages = []

    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))

    # Inject relay handoff if model switch detected
    relay = detect_relay(history, current_model_name)
    if relay:
        messages.append(ChatMessage(role="user", content=relay))

    # Collect all user_ids from history for batch name lookup (group only)
    if group_id != "private" and history:
        user_ids = list(set(h["user_id"] for h in history if "user_id" in h))
        names = await get_group_user_names(user_ids)
    else:
        names = {}

    for h in history:
        if h["role"] == "user":
            user_id = h.get("user_id", "")
            if group_id != "private" and user_id:
                display_name = names.get(user_id, f"用户{user_id}")
                content = f"<群聊消息>{display_name}说：{h['content']}</群聊消息>"
            else:
                content = f"<用户消息>\n{h['content']}\n</用户消息>"
            messages.append(ChatMessage(role=h["role"], content=content))
        else:
            # Rebuild tool_calls from JSON if present
            tc_list = []
            if h.get("tool_calls"):
                for tc_data in h["tool_calls"]:
                    tc_list.append(ToolCall(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=tc_data["arguments"],
                    ))
            messages.append(ChatMessage(
                role=h["role"],
                content=h["content"],
                tool_calls=tc_list,
                tool_call_id=h.get("tool_call_id"),
            ))

    wrapped_text = f"<用户消息>\n{user_text}\n</用户消息>"
    user_msg = ChatMessage(role="user", content=wrapped_text)
    if image_data:
        user_msg.image_data = image_data
    messages.append(user_msg)
    return messages

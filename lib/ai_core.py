import time
from lib.config import AppConfig
from lib.models.base import ChatMessage, ChatResponse, ToolDefinition
from lib.models.factory import resolve_model, create_client
from lib.errors import BotException
from lib.tools.search import (
    SEARCH_TOOL_DEFINITION,
    execute_search,
    format_search_results,
    format_search_sources,
    SearchResult,
)


async def _vision_fallback(image_data: bytes, config: AppConfig) -> str:
    """Use vision fallback model to describe an image."""
    client = create_client(config.vision_fallback)
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
    messages = _build_initial_messages(
        system_prompt=personality_system_prompt,
        history=history,
        user_text=msg_text,
        image_data=img_for_model if client.supports_vision else None,
    )

    # Build tools list
    tools = []
    if app_config.search_enabled:
        tools.append(SEARCH_TOOL_DEFINITION)

    # Tool calling loop
    max_rounds = 5
    for _ in range(max_rounds):
        response = await client.chat(messages, tools if tools else None)

        if response.tool_calls:
            messages.append(ChatMessage(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))

            for tc in response.tool_calls:
                if tc.name == "web_search":
                    has_search = True
                    query = tc.arguments.get("query", "")
                    try:
                        results = execute_search(query, app_config.search_max_results)
                    except Exception:
                        results = []
                    if results:
                        sources = results
                    tool_result_text = format_search_results(results)
                    messages.append(ChatMessage(
                        role="tool",
                        content=tool_result_text,
                        tool_call_id=tc.id,
                    ))
        else:
            # No more tool calls — final response
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "content": response.content,
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
        "model_name": model_config.name,
        "has_search": has_search,
        "has_image": has_image,
        "response_time_ms": elapsed_ms,
        "sources": sources,
    }


def _build_initial_messages(
    system_prompt: str,
    history: list[dict],
    user_text: str,
    image_data: bytes | None,
) -> list[ChatMessage]:
    messages = []

    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))

    for h in history:
        if h["role"] == "user":
            content = f"<user_message>\n{h['content']}\n</user_message>"
        else:
            content = h["content"]
        messages.append(ChatMessage(role=h["role"], content=content))

    wrapped_text = f"<user_message>\n{user_text}\n</user_message>"
    user_msg = ChatMessage(role="user", content=wrapped_text)
    if image_data:
        user_msg.image_data = image_data
    messages.append(user_msg)
    return messages

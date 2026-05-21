import json
import base64
from typing import Optional
import anthropic
import httpx
from lib.models.base import BaseModelClient, ChatMessage, ChatResponse, ToolCall, ToolDefinition
from lib.errors import BotException, E01, E02, E03, E04, E05, E08


class AnthropicClient(BaseModelClient):
    def __init__(self, api_key: str, model: str, supports_vision: bool = True, proxy_url: str | None = None):
        http_client = httpx.AsyncClient(proxy=proxy_url) if proxy_url else None
        self.client = anthropic.AsyncAnthropic(api_key=api_key, http_client=http_client)
        self.model = model
        self.supports_vision = supports_vision

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        enable_thinking: bool = False,
    ) -> ChatResponse:
        system_prompt = ""
        chat_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content or ""
            else:
                chat_messages.append(msg)

        anthropic_msgs = self._build_messages(chat_messages)
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]

        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": anthropic_msgs,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        if enable_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 1024}
            kwargs["max_tokens"] = kwargs.get("max_tokens", 4096) + 1024

        try:
            resp = await self.client.messages.create(**kwargs)
        except anthropic.APITimeoutError:
            raise BotException(E01)
        except anthropic.AuthenticationError:
            raise BotException(E02)
        except anthropic.RateLimitError:
            raise BotException(E03)
        except anthropic.InternalServerError:
            raise BotException(E04)
        except anthropic.APIConnectionError:
            raise BotException(E05)
        except anthropic.APIStatusError as e:
            if e.status_code == 429:
                raise BotException(E03)
            if e.status_code >= 500:
                raise BotException(E04)
            raise BotException(E08, f"HTTP {e.status_code}")
        except Exception:
            raise BotException(E08)

        content = ""
        thinking_text = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "thinking":
                thinking_text += block.thinking
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        return ChatResponse(content=content, thinking=thinking_text, tool_calls=tool_calls)

    def _build_messages(self, messages: list[ChatMessage]) -> list[dict]:
        result = []
        for msg in messages:
            if msg.role == "tool":
                result.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.content}],
                })
            else:
                parts = []
                if msg.content:
                    parts.append({"type": "text", "text": msg.content})
                if msg.image_data:
                    b64 = base64.b64encode(msg.image_data).decode()
                    parts.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64},
                    })
                if msg.tool_calls:
                    # Anthropic assistant tool_use blocks
                    for tc in msg.tool_calls:
                        parts.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
                result.append({"role": msg.role, "content": parts if parts else msg.content or ""})
        return result

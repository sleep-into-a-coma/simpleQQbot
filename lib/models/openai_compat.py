import json
import httpx
from typing import Optional
from lib.models.base import BaseModelClient, ChatMessage, ChatResponse, ToolCall, ToolDefinition
from lib.errors import BotException, E01, E02, E03, E04, E05, E08


class OpenAICompatClient(BaseModelClient):
    def __init__(self, api_base: str, api_key: str, model: str, supports_vision: bool = False, proxy_url: str | None = None):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.supports_vision = supports_vision
        self._http = httpx.AsyncClient(timeout=60, proxy=proxy_url)

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[ToolDefinition]] = None,
        enable_thinking: bool = False,
    ) -> ChatResponse:
        body = {
            "model": self.model,
            "messages": self._build_messages(messages),
        }
        if tools:
            body["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ]
            body["tool_choice"] = "auto"

        try:
            resp = await self._http.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        except httpx.TimeoutException:
            raise BotException(E01)
        except httpx.ConnectError:
            raise BotException(E05)
        except httpx.NetworkError:
            raise BotException(E05)

        if resp.status_code == 401 or resp.status_code == 403:
            raise BotException(E02)
        if resp.status_code == 429:
            raise BotException(E03)
        if resp.status_code >= 500:
            raise BotException(E04)
        if resp.status_code != 200:
            raise BotException(E08, f"HTTP {resp.status_code}")

        data = resp.json()

        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        thinking = choice.get("reasoning_content") or ""
        tool_calls = []
        if "tool_calls" in choice:
            for tc in choice["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                ))

        return ChatResponse(content=content, thinking=thinking, tool_calls=tool_calls)

    def _build_messages(self, messages: list[ChatMessage]) -> list[dict]:
        result = []
        for msg in messages:
            parts = []
            if msg.content:
                parts.append({"type": "text", "text": msg.content})
            if msg.image_data:
                import base64
                b64 = base64.b64encode(msg.image_data).decode()
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })

            entry = {"role": msg.role}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
                entry["role"] = "tool"

            if parts:
                # If there are images, build multi-part content
                if len(parts) == 1 and parts[0]["type"] == "text":
                    entry["content"] = msg.content
                else:
                    entry["content"] = parts
            elif msg.content is not None:
                entry["content"] = msg.content

            result.append(entry)
        return result

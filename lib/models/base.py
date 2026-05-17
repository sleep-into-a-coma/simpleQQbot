from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema for the tool's parameters


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ChatMessage:
    role: str  # 'system' | 'user' | 'assistant' | 'tool'
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    image_data: Optional[bytes] = None  # raw image bytes for vision


@dataclass
class ChatResponse:
    content: str
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class BaseModelClient(ABC):
    """Abstract base for AI model providers."""

    supports_vision: bool = False

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ChatResponse:
        """Send messages and return response. May include tool calls."""
        ...

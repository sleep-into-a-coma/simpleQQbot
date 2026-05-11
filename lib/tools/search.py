from dataclasses import dataclass
from duckduckgo_search import DDGS
from lib.models.base import ToolDefinition


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


SEARCH_TOOL_DEFINITION = ToolDefinition(
    name="web_search",
    description="搜索互联网获取最新信息。当需要查找实时信息、事实核实或你不确定的内容时使用。",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
        },
        "required": ["query"],
    },
)


def execute_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Execute a DuckDuckGo search and return results."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(SearchResult(
                title=r["title"],
                url=r["href"],
                snippet=r["body"],
            ))
    return results


def format_search_results(results: list[SearchResult]) -> str:
    """Format search results as text for LLM context."""
    if not results:
        return "未找到相关搜索结果。"

    lines = ["搜索结果："]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.title}\n   {r.snippet}\n   {r.url}")
    return "\n".join(lines)


def format_search_sources(results: list[SearchResult]) -> str:
    """Format search sources as citation links for reply footer."""
    if not results:
        return ""
    lines = ["\n📎 来源："]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r.title}]({r.url})")
    return "\n".join(lines)

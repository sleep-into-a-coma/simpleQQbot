from abc import ABC, abstractmethod
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


class SearchBackend(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int) -> list[SearchResult]:
        """Execute search. Returns empty list on any error."""
        ...


class DuckDuckGoBackend(SearchBackend):
    def __init__(self, proxy_url: str | None = None):
        self._proxy_url = proxy_url

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            results = []
            with DDGS(proxy=self._proxy_url) as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(SearchResult(
                        title=r["title"],
                        url=r["href"],
                        snippet=r["body"],
                    ))
            return results
        except Exception:
            return []


class BingSearchBackend(SearchBackend):
    def __init__(self, api_key: str, proxy_url: str | None = None):
        import httpx
        self._client = httpx.Client(
            base_url="https://api.bing.microsoft.com",
            proxy=proxy_url,
            headers={"Ocp-Apim-Subscription-Key": api_key},
        )

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            resp = self._client.get("/v7.0/search", params={
                "q": query,
                "count": max_results,
                "mkt": "zh-CN",
            })
            if resp.status_code != 200:
                return []
            data = resp.json()
            web_pages = data.get("webPages", {}).get("value", [])
            return [
                SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                )
                for item in web_pages
            ]
        except Exception:
            return []


class SearXNGBackend(SearchBackend):
    def __init__(self, instance_url: str, proxy_url: str | None = None):
        import httpx
        self._client = httpx.Client(
            base_url=instance_url.rstrip("/"),
            proxy=proxy_url,
        )

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            resp = self._client.get("/search", params={
                "q": query,
                "format": "json",
                "categories": "general",
            })
            if resp.status_code != 200:
                return []
            data = resp.json()
            items = data.get("results", [])
            return [
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", "") or item.get("snippet", ""),
                )
                for item in items[:max_results]
            ]
        except Exception:
            return []


def create_search_backend(config) -> SearchBackend:
    """Validate config and return the configured SearchBackend. Raises ValueError on misconfiguration."""
    backend_name = config.search_backend
    if backend_name == "duckduckgo":
        return DuckDuckGoBackend(proxy_url=config.proxy_url)
    elif backend_name == "bing":
        if not config.bing_api_key:
            raise ValueError("BING_API_KEY is required when SEARCH_BACKEND=bing")
        return BingSearchBackend(
            api_key=config.bing_api_key,
            proxy_url=config.proxy_url,
        )
    elif backend_name == "searxng":
        if not config.searxng_url:
            raise ValueError("SEARXNG_URL is required when SEARCH_BACKEND=searxng")
        return SearXNGBackend(
            instance_url=config.searxng_url,
            proxy_url=config.proxy_url,
        )
    else:
        raise ValueError(f"Unknown search backend: {backend_name}")


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

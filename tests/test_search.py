import pytest
import httpx
from lib.tools.search import (
    SearchBackend,
    SearchResult,
    DuckDuckGoBackend,
    BingSearchBackend,
    SearXNGBackend,
    create_search_backend,
    SEARCH_TOOL_DEFINITION,
    format_search_results,
    format_search_sources,
)


# --- Factory tests ---

class FakeConfig:
    search_backend = "duckduckgo"
    search_max_results = 5
    proxy_url = None
    bing_api_key = None
    searxng_url = None


def test_factory_creates_duckduckgo():
    cfg = FakeConfig()
    cfg.search_backend = "duckduckgo"
    backend = create_search_backend(cfg)
    assert isinstance(backend, DuckDuckGoBackend)


def test_factory_creates_bing():
    cfg = FakeConfig()
    cfg.search_backend = "bing"
    cfg.bing_api_key = "test-key"
    backend = create_search_backend(cfg)
    assert isinstance(backend, BingSearchBackend)


def test_factory_creates_searxng():
    cfg = FakeConfig()
    cfg.search_backend = "searxng"
    cfg.searxng_url = "https://searx.example.com"
    backend = create_search_backend(cfg)
    assert isinstance(backend, SearXNGBackend)


def test_factory_raises_on_unknown_backend():
    cfg = FakeConfig()
    cfg.search_backend = "google"
    with pytest.raises(ValueError, match="Unknown search backend"):
        create_search_backend(cfg)


def test_factory_raises_when_bing_missing_api_key():
    cfg = FakeConfig()
    cfg.search_backend = "bing"
    cfg.bing_api_key = None
    with pytest.raises(ValueError, match="BING_API_KEY"):
        create_search_backend(cfg)


def test_factory_raises_when_searxng_missing_url():
    cfg = FakeConfig()
    cfg.search_backend = "searxng"
    cfg.searxng_url = None
    with pytest.raises(ValueError, match="SEARXNG_URL"):
        create_search_backend(cfg)


# --- Bing backend tests ---

def make_bing_response(snippets):
    """Build a realistic Bing API JSON response."""
    return {
        "webPages": {
            "value": [
                {"name": s["title"], "url": s["url"], "snippet": s["snippet"]}
                for s in snippets
            ]
        }
    }


def test_bing_search_parses_results():
    transport = httpx.MockTransport(lambda req: httpx.Response(
        200, json=make_bing_response([
            {"title": "Title1", "url": "https://a.com", "snippet": "Snippet 1"},
            {"title": "Title2", "url": "https://b.com", "snippet": "Snippet 2"},
        ])
    ))
    backend = BingSearchBackend(api_key="k", proxy_url=None)
    backend._client = httpx.Client(transport=transport, base_url="https://api.bing.microsoft.com")
    results = backend.search("test", 5)
    assert len(results) == 2
    assert results[0] == SearchResult(title="Title1", url="https://a.com", snippet="Snippet 1")


def test_bing_search_returns_empty_on_http_error():
    transport = httpx.MockTransport(lambda req: httpx.Response(500, content=b"error"))
    backend = BingSearchBackend(api_key="k", proxy_url=None)
    backend._client = httpx.Client(transport=transport, base_url="https://api.bing.microsoft.com")
    results = backend.search("test", 5)
    assert results == []


def test_bing_search_returns_empty_on_network_error():
    transport = httpx.MockTransport(lambda req: (_ for _ in ()).throw(httpx.ConnectError("fail")))
    backend = BingSearchBackend(api_key="k", proxy_url=None)
    backend._client = httpx.Client(transport=transport, base_url="https://api.bing.microsoft.com")
    results = backend.search("test", 5)
    assert results == []


def test_bing_search_returns_empty_on_malformed_json():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"wrong": "shape"}))
    backend = BingSearchBackend(api_key="k", proxy_url=None)
    backend._client = httpx.Client(transport=transport, base_url="https://api.bing.microsoft.com")
    results = backend.search("test", 5)
    assert results == []


# --- SearXNG backend tests ---

def make_searxng_response(results_list):
    """Build a realistic SearXNG JSON response."""
    return {
        "results": [
            {"title": r["title"], "url": r["url"], "content": r["content"]}
            for r in results_list
        ]
    }


def test_searxng_search_parses_results():
    transport = httpx.MockTransport(lambda req: httpx.Response(
        200, json=make_searxng_response([
            {"title": "T1", "url": "https://x.com", "content": "Body 1"},
        ])
    ))
    backend = SearXNGBackend(instance_url="https://s.example.com", proxy_url=None)
    backend._client = httpx.Client(transport=transport, base_url="https://s.example.com")
    results = backend.search("q", 5)
    assert len(results) == 1
    assert results[0] == SearchResult(title="T1", url="https://x.com", snippet="Body 1")


def test_searxng_search_returns_empty_on_http_error():
    transport = httpx.MockTransport(lambda req: httpx.Response(500, content=b"err"))
    backend = SearXNGBackend(instance_url="https://s.example.com", proxy_url=None)
    backend._client = httpx.Client(transport=transport, base_url="https://s.example.com")
    results = backend.search("q", 5)
    assert results == []


def test_searxng_search_returns_empty_on_network_error():
    transport = httpx.MockTransport(lambda req: (_ for _ in ()).throw(httpx.ConnectError("fail")))
    backend = SearXNGBackend(instance_url="https://s.example.com", proxy_url=None)
    backend._client = httpx.Client(transport=transport, base_url="https://s.example.com")
    results = backend.search("q", 5)
    assert results == []


# --- Format helpers (existing, smoke tests) ---

def test_format_search_results_empty():
    assert format_search_results([]) == "未找到相关搜索结果。"


def test_format_search_results_nonempty():
    r = [SearchResult(title="T", url="https://u.com", snippet="S")]
    out = format_search_results(r)
    assert "T" in out
    assert "S" in out
    assert "https://u.com" in out


def test_format_search_sources_empty():
    assert format_search_sources([]) == ""


def test_format_search_sources_nonempty():
    r = [SearchResult(title="T", url="https://u.com", snippet="S")]
    out = format_search_sources(r)
    assert "[T](https://u.com)" in out

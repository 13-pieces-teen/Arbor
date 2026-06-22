"""Tests for the pluggable search backends + the web-tools factory.

Network is never touched: ``requests`` is monkeypatched and the alphaXiv SDK is
faked via ``ax._load_axv``.
"""

from __future__ import annotations

import asyncio
import json

import arbor.core.tools.web.backends as B
from arbor.core.tools.web.backends import (
    ExaBackend,
    ExaMcpBackend,
    JinaSearchBackend,
    SerperBackend,
    build_search_backends,
    resolve_backend_names,
)
from arbor.core.tools.web.factory import build_web_search_tool, build_web_visit_tool
from arbor.core.tools.web.search import WebSearchTool
from arbor.coordinator.config import SearchConfig


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.headers = {"Content-Type": "application/json"}
        self.text = "ok"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


# ── resolve_backend_names ────────────────────────────────────────────────────

def test_resolve_legacy_alphaxiv():
    assert resolve_backend_names(SearchConfig(builtin_backend="alphaxiv")) == ["alphaxiv"]


def test_resolve_legacy_endpoint():
    sc = SearchConfig(web_search_endpoint="http://x/search")
    assert resolve_backend_names(sc) == ["endpoint"]


def test_resolve_explicit_list_keyless():
    sc = SearchConfig(backends=["alphaxiv", "jina"])
    assert resolve_backend_names(sc) == ["alphaxiv", "jina"]


def test_resolve_drops_keyless_missing_creds(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    sc = SearchConfig(backends=["serper", "exa", "jina"])
    # serper/exa dropped (no key), jina kept (keyless)
    assert resolve_backend_names(sc) == ["jina"]


def test_resolve_keeps_keyed_when_key_present():
    sc = SearchConfig(backends=["serper", "exa"], serper_api_key="s", exa_api_key="e")
    assert resolve_backend_names(sc) == ["serper", "exa"]


def test_resolve_dedup_and_unknown_dropped():
    sc = SearchConfig(backends=["alphaxiv", "alphaxiv", "bogus"])
    assert resolve_backend_names(sc) == ["alphaxiv"]


# ── adapter parsing ──────────────────────────────────────────────────────────

def test_serper_backend_parses_organic(monkeypatch):
    payload = {"organic": [
        {"link": "https://a.com", "title": "A", "snippet": "sa"},
        {"link": "https://b.com", "title": "B", "snippet": "sb"},
    ]}
    monkeypatch.setattr(B.requests, "post", lambda *a, **k: _Resp(payload))
    items = asyncio.run(SerperBackend(api_key="k").search("q", 5))
    assert items == [
        {"url": "https://a.com", "title": "A", "snippets": "sa"},
        {"url": "https://b.com", "title": "B", "snippets": "sb"},
    ]


def test_exa_backend_parses_results(monkeypatch):
    payload = {"results": [
        {"url": "https://p.com", "title": "P", "text": "body text", "author": "Ann", "publishedDate": "2025"},
    ]}
    monkeypatch.setattr(B.requests, "post", lambda *a, **k: _Resp(payload))
    items = asyncio.run(ExaBackend(api_key="k").search("q", 5))
    assert items[0]["url"] == "https://p.com"
    assert items[0]["title"] == "P"
    assert "body text" in items[0]["snippets"]
    assert "Ann" in items[0]["snippets"]


def test_jina_search_backend_parses(monkeypatch):
    payload = {"data": [
        {"url": "https://j.com", "title": "J", "description": "desc"},
    ]}
    monkeypatch.setattr(B.requests, "get", lambda *a, **k: _Resp(payload))
    items = asyncio.run(JinaSearchBackend().search("q", 5))
    assert items == [{"url": "https://j.com", "title": "J", "snippets": "desc"}]


# ── build_search_backends ────────────────────────────────────────────────────

def test_build_search_backends_types():
    sc = SearchConfig(backends=["alphaxiv", "jina", "serper", "exa"],
                      serper_api_key="s", exa_api_key="e")
    backends = build_search_backends(sc)
    names = [b.name for b in backends]
    assert names == ["alphaxiv", "jina", "serper", "exa"]


# ── WebSearchTool multi-backend fan-out + merge ──────────────────────────────

class _FakeBackend:
    def __init__(self, name, items):
        self.name = name
        self._items = items

    async def search(self, query, max_results):
        return self._items


def test_websearch_tool_merges_across_backends():
    # Same URL from two backends → should merge (support=2 after dedup).
    b1 = _FakeBackend("x", [{"url": "https://shared.com", "title": "S", "snippets": "one"}])
    b2 = _FakeBackend("y", [{"url": "https://shared.com", "title": "S", "snippets": "one"},
                            {"url": "https://only.com", "title": "O", "snippets": "two"}])
    tool = WebSearchTool(cwd=".", backends=[b1, b2])
    out = asyncio.run(tool.execute(query=["q"]))
    assert "shared.com" in out
    assert "only.com" in out


def test_websearch_tool_backend_failure_is_reported():
    class _Boom:
        name = "boom"
        async def search(self, q, n):
            raise RuntimeError("down")
    ok = _FakeBackend("ok", [{"url": "https://ok.com", "title": "K", "snippets": "s"}])
    tool = WebSearchTool(cwd=".", backends=[_Boom(), ok])
    out = asyncio.run(tool.execute(query=["q"]))
    assert "ok.com" in out  # surviving backend still produces results


def test_websearch_tool_requires_source():
    import pytest
    with pytest.raises(ValueError):
        WebSearchTool(cwd=".")  # neither endpoint_url nor backends


# ── factory tool selection ───────────────────────────────────────────────────

def test_factory_alphaxiv_only():
    from arbor.core.tools.web.alphaxiv import AlphaXivSearchTool, AlphaXivVisitTool
    sc = SearchConfig(builtin_backend="alphaxiv")
    st = build_web_search_tool(sc, cwd=".")
    vt = build_web_visit_tool(sc, cwd=".")
    assert isinstance(st, AlphaXivSearchTool)
    assert isinstance(vt, AlphaXivVisitTool)  # alphaXiv-only default preserved


def test_factory_multi_backend_uses_routing_visit():
    from arbor.core.tools.web.keyless_visit import RoutingVisitTool
    sc = SearchConfig(backends=["alphaxiv", "jina"])
    st = build_web_search_tool(sc, cwd=".")
    vt = build_web_visit_tool(sc, cwd=".")
    assert isinstance(st, WebSearchTool)
    assert isinstance(vt, RoutingVisitTool)  # alphaXiv papers + jina general


def test_factory_jina_only_visit():
    from arbor.core.tools.web.keyless_visit import JinaVisitTool
    sc = SearchConfig(backends=["jina"])
    vt = build_web_visit_tool(sc, cwd=".")
    assert isinstance(vt, JinaVisitTool)


def test_factory_browse_endpoint_visit():
    from arbor.core.tools.web.visit import WebVisitTool
    sc = SearchConfig(web_search_endpoint="http://x/s", web_browse_endpoint="http://x/b")
    vt = build_web_visit_tool(sc, cwd=".")
    assert isinstance(vt, WebVisitTool)


def test_factory_no_backend_returns_none():
    sc = SearchConfig()
    assert build_web_search_tool(sc, cwd=".") is None
    assert build_web_visit_tool(sc, cwd=".") is None


# ── Exa MCP backend ──────────────────────────────────────────────────────────

def test_exa_mcp_resolve_and_build():
    sc = SearchConfig(backends=["exa-mcp"], exa_api_key="k")
    assert resolve_backend_names(sc) == ["exa-mcp"]
    backends = build_search_backends(sc)
    assert len(backends) == 1 and backends[0].name == "exa-mcp"


def test_exa_mcp_dropped_without_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    sc = SearchConfig(backends=["exa-mcp"])
    assert resolve_backend_names(sc) == []


def test_exa_mcp_uses_configured_url():
    sc = SearchConfig(backends=["exa-mcp"], exa_api_key="k", exa_mcp_url="https://my/mcp")
    backend = build_search_backends(sc)[0]
    assert backend._url == "https://my/mcp"


def test_exa_mcp_parse_results():
    payload = json.dumps({"results": [
        {"url": "https://e.com", "title": "E", "text": "body", "author": "Ann", "publishedDate": "2025"},
        {"url": "https://f.com", "title": "F", "highlights": ["h1", "h2"]},
    ]})
    items = ExaMcpBackend._parse(payload)
    assert items[0]["url"] == "https://e.com"
    assert "body" in items[0]["snippets"] and "Ann" in items[0]["snippets"]
    assert items[1]["url"] == "https://f.com"
    assert "h1" in items[1]["snippets"]


def test_exa_mcp_parse_handles_garbage():
    assert ExaMcpBackend._parse("not json") == []
    assert ExaMcpBackend._parse("") == []


def test_exa_mcp_search_parses_tool_output(monkeypatch):
    """search() maps the MCP tool's text output without touching the network."""
    canned = json.dumps({"results": [{"url": "https://e.com", "title": "E", "text": "b"}]})

    async def fake_call(self, query, max_results):
        return canned

    monkeypatch.setattr(ExaMcpBackend, "_call_tool", fake_call)
    items = asyncio.run(ExaMcpBackend(api_key="k").search("q", 5))
    assert items == [{"url": "https://e.com", "title": "E", "snippets": "b"}]


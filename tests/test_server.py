"""Exercise the MCP layer: tool registration, schemas and calls (offline)."""

import asyncio
import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from medium_mcp import feeds, server
from medium_mcp.medium_api import MediumClient

FIXTURE = (Path(__file__).parent / "fixtures" / "user_feed.xml").read_bytes()


def run(coro):
    return asyncio.run(coro)


def _payload(result):
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


def test_default_tools_without_token():
    names = {t.name for t in run(server.mcp.list_tools())}
    assert {"get_user_stories", "get_publication_stories", "get_tag_stories", "prepare_article"} <= names
    assert "create_post" not in names


def test_get_user_stories_via_mcp(monkeypatch):
    monkeypatch.setattr(feeds, "fetch", lambda url: FIXTURE)
    result = run(server.mcp.call_tool("get_user_stories", {"username": "samplewriter", "limit": 1}))
    assert not result.is_error
    data = _payload(result)
    assert data["source"] == "https://medium.com/feed/@samplewriter"
    assert data["count"] == 1


def test_prepare_article_via_mcp():
    result = run(server.mcp.call_tool("prepare_article", {"markdown": "# Hi there\n\nbody", "tags": ["dev"]}))
    data = _payload(result)
    assert data["title"] == "Hi there" and data["tags"] == ["dev"]


def test_bad_username_is_visible_tool_error():
    with pytest.raises(ToolError, match="Not a valid Medium username"):
        run(server.mcp.call_tool("get_user_stories", {"username": "../../x"}))


def test_network_error_is_visible_tool_error(monkeypatch):
    def boom(url):
        raise feeds.FeedError("Couldn't reach Medium: timed out")

    monkeypatch.setattr(feeds, "fetch", boom)
    with pytest.raises(ToolError, match="Couldn't reach Medium"):
        run(server.mcp.call_tool("get_tag_stories", {"tag": "python"}))


def test_publishing_tools_register_and_default_to_draft(monkeypatch):
    client = MediumClient("fake-token")
    sent = {}

    def fake_request(method, path, body=None, content_type="application/json"):
        if path == "/me":
            return {"id": "u1", "username": "sample"}
        sent.update(method=method, path=path, body=json.loads(body))
        return {"id": "p1", "url": "https://medium.com/p/p1", "publishStatus": "draft", "tags": ["dev"]}

    monkeypatch.setattr(client, "_request", fake_request)
    server.register_publishing_tools(client)
    names = {t.name for t in run(server.mcp.list_tools())}
    assert {"create_post", "upload_image", "list_my_publications", "get_medium_profile"} <= names

    result = run(server.mcp.call_tool("create_post", {"title": "T", "content_markdown": "# T", "tags": ["dev"]}))
    assert not result.is_error
    assert sent["path"] == "/users/u1/posts"
    assert sent["body"]["publishStatus"] == "draft"
    assert sent["body"]["notifyFollowers"] is False
    assert _payload(result)["publish_status"] == "draft"

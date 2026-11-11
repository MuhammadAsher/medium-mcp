"""open_in_medium: clipboard + browser hand-off. Never touches the real clipboard or browser."""

import asyncio
import json
import subprocess
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from medium_mcp import handoff, server


def run(coro):
    return asyncio.run(coro)


def _payload(result):
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


@pytest.fixture
def fake_macos(monkeypatch):
    """Record osascript/open calls instead of running them."""
    calls = []

    def fake_run(cmd, **kwargs):
        rec = {"cmd": cmd}
        if cmd[0] == "osascript":  # capture the files' contents before the temp dir is deleted
            rec["html"] = Path(cmd[-2]).read_text()
            rec["text"] = Path(cmd[-1]).read_text()
            calls.append(rec)
            return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")
        calls.append(rec)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(handoff.sys, "platform", "darwin")
    monkeypatch.setattr(handoff.subprocess, "run", fake_run)
    monkeypatch.delenv(handoff.BROWSER_ENV, raising=False)
    return calls


def test_copies_rich_text_and_opens_safari_by_default(fake_macos, tmp_path):
    md = tmp_path / "post.md"
    md.write_text("# A post\n\nHello **world**.\n")
    data = _payload(run(server.mcp.call_tool("open_in_medium", {"file_path": str(md), "tags": ["python"]})))

    clip, opened = fake_macos
    assert clip["cmd"][:3] == ["osascript", "-l", "JavaScript"]
    assert "<h1>A post</h1>" in clip["html"] and "<strong>world</strong>" in clip["html"]
    assert '<meta charset="utf-8">' in clip["html"]
    assert clip["text"].startswith("# A post")
    assert opened["cmd"] == ["open", "-a", "Safari", "https://medium.com/new-story"]
    assert data["browser"] == "Safari" and data["tags"] == ["python"]


def test_browser_from_env_and_argument(fake_macos, monkeypatch):
    monkeypatch.setenv(handoff.BROWSER_ENV, "Google Chrome")
    run(server.mcp.call_tool("open_in_medium", {"markdown": "# T\n\nx"}))
    assert fake_macos[-1]["cmd"][:3] == ["open", "-a", "Google Chrome"]

    run(server.mcp.call_tool("open_in_medium", {"markdown": "# T\n\nx", "browser": "default"}))
    assert fake_macos[-1]["cmd"] == ["open", "https://medium.com/new-story"]


def test_missing_browser_is_a_visible_error(monkeypatch):
    monkeypatch.setattr(handoff.sys, "platform", "darwin")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "osascript":
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Unable to find application named 'Arc'")

    monkeypatch.setattr(handoff.subprocess, "run", fake_run)
    with pytest.raises(ToolError, match="Unable to find application named 'Arc'"):
        run(server.mcp.call_tool("open_in_medium", {"markdown": "# T\n\nx", "browser": "Arc"}))


def test_clipboard_failure_is_a_visible_error(monkeypatch):
    monkeypatch.setattr(handoff.sys, "platform", "darwin")
    monkeypatch.setattr(
        handoff.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="execution error"),
    )
    with pytest.raises(ToolError, match="clipboard"):
        run(server.mcp.call_tool("open_in_medium", {"markdown": "# T\n\nx"}))


def test_not_macos_points_to_export(monkeypatch):
    monkeypatch.setattr(handoff.sys, "platform", "linux")
    with pytest.raises(ToolError, match="export_article"):
        run(server.mcp.call_tool("open_in_medium", {"markdown": "# T\n\nx"}))

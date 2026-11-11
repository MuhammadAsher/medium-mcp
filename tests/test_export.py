import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from medium_mcp import server
from medium_mcp.export import inline, markdown_to_html, render_page


def run(coro):
    return asyncio.run(coro)


def _payload(result):
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


def test_headings_paragraphs_and_lists():
    html = markdown_to_html("# Title\n\n## Section\n\nLine one\nline two\n\n- a\n- b\n\n1. x\n2. y\n")
    assert "<h1>Title</h1>" in html
    assert "<h2>Section</h2>" in html
    assert "<p>Line one line two</p>" in html
    assert "<ul>\n<li>a</li>\n<li>b</li>\n</ul>" in html
    assert "<ol>\n<li>x</li>\n<li>y</li>\n</ol>" in html


def test_code_block_is_escaped_and_untouched():
    html = markdown_to_html("```python\nif a < b and **x**:\n    pass\n```")
    assert "<pre><code>if a &lt; b and **x**:\n    pass</code></pre>" in html


def test_inline_formatting():
    out = inline("**bold** and *it* and `a<b>` and [link](https://x.dev/?a=1&b=2)")
    assert "<strong>bold</strong>" in out
    assert "<em>it</em>" in out
    assert "<code>a&lt;b&gt;</code>" in out
    assert '<a href="https://x.dev/?a=1&amp;b=2">link</a>' in out


def test_snake_case_is_not_italicised():
    assert "<em>" not in inline("call my_func_name now")


def test_quote_image_and_rule():
    html = markdown_to_html('> wise words\n\n![A cat](https://x/cat.png "Caption")\n\n---\n')
    assert "<blockquote><p>wise words</p></blockquote>" in html
    assert '<img src="https://x/cat.png" alt="A cat">' in html and "<figcaption>Caption</figcaption>" in html
    assert "<hr>" in html


def test_page_escapes_title():
    assert "<title>A &lt;b&gt; title</title>" in render_page("A <b> title", "<p>x</p>")


def test_export_tool_writes_file_next_to_input(tmp_path):
    md = tmp_path / "post.md"
    md.write_text("# My post\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nHello **world**.\n")
    data = _payload(run(server.mcp.call_tool("export_article", {"file_path": str(md), "tags": ["python"]})))
    out = tmp_path / "post.medium.html"
    assert data["html_path"] == str(out)
    page = out.read_text()
    assert "<h1>My post</h1>" in page and "<strong>world</strong>" in page
    assert "<pre><code>" in page  # table became a code block via prepare_article
    assert data["tags"] == ["python"] and data["changes"]


def test_export_tool_needs_exactly_one_source():
    with pytest.raises(ToolError, match="exactly one"):
        run(server.mcp.call_tool("export_article", {}))


def test_export_tool_rejects_non_html_output(tmp_path):
    with pytest.raises(ToolError, match=r"\.html"):
        run(server.mcp.call_tool(
            "export_article", {"markdown": "# x\n\ny", "output_path": str(tmp_path / "out.md")}
        ))

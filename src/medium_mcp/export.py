"""Turn Medium-ready Markdown into an HTML page you can copy-paste into Medium.

Medium's editor keeps formatting when you paste rich text from a browser, but
not when you paste raw Markdown. So the no-token workflow is:

    prepare_article -> export_article -> open the .html -> Cmd+A, Cmd+C -> paste into Medium

This is a deliberately small Markdown converter covering exactly what Medium
supports: two heading sizes, paragraphs, bold/italic/inline code, links,
images, bulleted and numbered lists, block quotes, code blocks and dividers.
Standard library only.
"""

from __future__ import annotations

import html
import re

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_UL_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_HR_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_IMAGE_LINE_RE = re.compile(r'^\s*!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)\s*$')

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ max-width: 680px; margin: 2rem auto; padding: 0 16px; font: 20px/1.6 Georgia, serif; color: #242424; background: #fff; }}
  .howto {{ font: 14px/1.5 -apple-system, system-ui, sans-serif; background: #f2f7f2; border: 1px solid #cfe3cf;
            border-radius: 6px; padding: 10px 14px; margin-bottom: 2rem; }}
  h1, h2, h3 {{ font-family: -apple-system, system-ui, sans-serif; line-height: 1.25; }}
  pre {{ background: #f2f2f2; padding: 14px; overflow-x: auto; font-size: 15px; }}
  code {{ background: #f2f2f2; padding: 1px 4px; font-size: 0.85em; }}
  pre code {{ background: none; padding: 0; }}
  blockquote {{ border-left: 3px solid #242424; margin-left: 0; padding-left: 20px; font-style: italic; }}
  img {{ max-width: 100%; }}
  figcaption {{ text-align: center; font-size: 15px; color: #6b6b6b; }}
</style>
</head>
<body>
<div class="howto" contenteditable="false">
  <strong>To paste into Medium:</strong> click inside the article below, press Cmd+A then Cmd+C,
  open <a href="https://medium.com/new-story">medium.com/new-story</a> and press Cmd+V.
  Tags, subtitle and canonical URL go in Medium's publish dialog.
</div>
<article contenteditable="true">
{body}
</article>
</body>
</html>
"""


def markdown_to_html(markdown: str) -> str:
    """Convert Medium-flavoured Markdown to an HTML fragment."""
    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    list_kind: str | None = None  # "ul" | "ol"
    quote: list[str] = []
    i = 0

    def flush_para() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(s.strip() for s in para))}</p>")
            para.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = None

    def flush_quote() -> None:
        if quote:
            out.append(f"<blockquote><p>{inline(' '.join(s.strip() for s in quote))}</p></blockquote>")
            quote.clear()

    def flush_all() -> None:
        flush_para()
        close_list()
        flush_quote()

    while i < len(lines):
        line = lines[i]

        fence = _FENCE_RE.match(line)
        if fence:
            flush_all()
            marker = fence.group(1)
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(marker):
                code.append(lines[i])
                i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
            i += 1  # skip closing fence (or run off the end if unclosed)
            continue

        if not line.strip():
            flush_all()
            i += 1
            continue

        m = _HEADING_RE.match(line)
        if m:
            flush_all()
            level = min(len(m.group(1)), 3)
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if _HR_RE.match(line):
            flush_all()
            out.append("<hr>")
            i += 1
            continue

        m = _IMAGE_LINE_RE.match(line)
        if m:
            flush_all()
            alt, src, caption = m.group(1), m.group(2), m.group(3)
            fig = f'<figure><img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}">'
            if caption:
                fig += f"<figcaption>{inline(caption)}</figcaption>"
            out.append(fig + "</figure>")
            i += 1
            continue

        m = _QUOTE_RE.match(line)
        if m:
            flush_para()
            close_list()
            quote.append(m.group(1))
            i += 1
            continue
        flush_quote()

        ul, ol = _UL_RE.match(line), _OL_RE.match(line)
        if ul or ol:
            flush_para()
            kind = "ul" if ul else "ol"
            if list_kind != kind:
                close_list()
                out.append(f"<{kind}>")
                list_kind = kind
            out.append(f"<li>{inline((ul or ol).group(1))}</li>")
            i += 1
            continue

        if list_kind and line.startswith((" ", "\t")):
            # Continuation of the previous list item: append to it.
            out[-1] = out[-1][: -len("</li>")] + " " + inline(line.strip()) + "</li>"
            i += 1
            continue

        close_list()
        para.append(line)
        i += 1

    flush_all()
    return "\n".join(out)


def inline(text: str) -> str:
    """Inline Markdown -> HTML. Code spans are protected from other rules."""
    spans: list[str] = []

    def stash_code(m: re.Match) -> str:
        spans.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash_code, text)
    text = html.escape(text, quote=False)
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)",
        lambda m: f'<img src="{_attr(m.group(2))}" alt="{_attr(m.group(1))}">',
        text,
    )
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)",
        lambda m: f'<a href="{_attr(m.group(2))}">{m.group(1)}</a>',
        text,
    )
    text = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"<strong>\2</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])", r"<em>\1</em>", text)
    text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<s>\1</s>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def _attr(value: str) -> str:
    # Input is already HTML-escaped (minus quotes); only quotes need escaping here.
    return value.replace('"', "&quot;")


def render_page(title: str, body_html: str) -> str:
    return _PAGE.format(title=html.escape(title or "Medium draft"), body=body_html)

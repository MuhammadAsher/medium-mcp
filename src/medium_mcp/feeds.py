"""Read Medium content through its public RSS feeds (no account or token needed).

Medium exposes feeds for users, publications and tags. Each feed returns only
the ~10 most recent stories, so this is for "what's new", not a full archive.
"""

from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field

FEED_BASE = "https://medium.com/feed"
USER_AGENT = "medium-mcp/0.1 (+https://github.com/modelcontextprotocol)"
TIMEOUT_SECONDS = 15

# Namespaces used in Medium's RSS
NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom",
}

# Medium usernames, publication slugs and tags are simple slugs. Rejecting
# anything else keeps callers from steering requests to other paths.
_USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_.\-]{1,64}$")
_SLUG_RE = re.compile(r"^[A-Za-z0-9_\-]{1,100}$")

WORDS_PER_MINUTE = 265  # Medium's own reading-time assumption


class FeedError(Exception):
    """Raised when a feed can't be fetched or parsed."""


@dataclass
class Story:
    title: str
    url: str
    author: str
    published: str
    tags: list[str] = field(default_factory=list)
    reading_minutes: int = 0
    summary: str = ""
    content_markdown: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if data["content_markdown"] is None:
            data.pop("content_markdown")
        return data


# --------------------------------------------------------------------------- #
# URL builders
# --------------------------------------------------------------------------- #

def user_feed_url(username: str) -> str:
    username = username.strip()
    if not _USERNAME_RE.match(username):
        raise FeedError(f"Not a valid Medium username: {username!r}")
    return f"{FEED_BASE}/@{username.lstrip('@')}"


def publication_feed_url(slug: str) -> str:
    slug = slug.strip().strip("/")
    if not _SLUG_RE.match(slug):
        raise FeedError(f"Not a valid publication slug: {slug!r}")
    return f"{FEED_BASE}/{slug}"


def tag_feed_url(tag: str) -> str:
    tag = tag.strip().lower().replace(" ", "-")
    if not _SLUG_RE.match(tag):
        raise FeedError(f"Not a valid tag: {tag!r}")
    return f"{FEED_BASE}/tag/{tag}"


# --------------------------------------------------------------------------- #
# Fetch + parse
# --------------------------------------------------------------------------- #

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FeedError(f"No feed found at {url} (404). Check the name.") from e
        raise FeedError(f"Medium returned HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise FeedError(f"Couldn't reach Medium: {e.reason}") from e


def parse_feed(xml_bytes: bytes, limit: int = 10, include_content: bool = False) -> list[Story]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise FeedError(
            "Medium didn't return a valid feed (it may be rate limiting or "
            "showing a bot check). Try again shortly."
        ) from e

    stories: list[Story] = []
    for item in root.iterfind("./channel/item"):
        content_html = item.findtext("content:encoded", default="", namespaces=NS)
        if not content_html:
            content_html = item.findtext("description", default="")
        text = html_to_text(content_html)

        stories.append(
            Story(
                title=(item.findtext("title") or "").strip(),
                url=_clean_url(item.findtext("link") or ""),
                author=(item.findtext("dc:creator", default="", namespaces=NS) or "").strip(),
                published=(item.findtext("pubDate") or "").strip(),
                tags=[(c.text or "").strip() for c in item.findall("category") if c.text],
                reading_minutes=max(1, round(len(text.split()) / WORDS_PER_MINUTE)) if text else 0,
                summary=_summary(text),
                content_markdown=html_to_markdown(content_html) if include_content else None,
            )
        )
        if len(stories) >= limit:
            break
    return stories


def get_stories(url: str, limit: int = 10, include_content: bool = False) -> list[Story]:
    return parse_feed(fetch(url), limit=limit, include_content=include_content)


# --------------------------------------------------------------------------- #
# HTML helpers (stdlib only, good enough for Medium's limited markup)
# --------------------------------------------------------------------------- #

def _clean_url(url: str) -> str:
    # Medium appends tracking params like ?source=rss-...
    return url.split("?", 1)[0].strip()


def _summary(text: str, max_chars: int = 280) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + "…"


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>|</pre>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(raw).strip()


def html_to_markdown(raw: str) -> str:
    """Convert the small subset of HTML Medium emits into readable Markdown."""
    s = raw
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s)
    # Drop Medium's tracking pixel
    s = re.sub(r'(?is)<img[^>]+stat\?event=[^>]*>', "", s)

    def pre(m: re.Match) -> str:
        code = re.sub(r"(?i)<br\s*/?>", "\n", m.group(1))
        code = html.unescape(re.sub(r"<[^>]+>", "", code))
        return f"\n```\n{code.strip()}\n```\n"

    s = re.sub(r"(?is)<pre[^>]*>(.*?)</pre>", pre, s)
    s = re.sub(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", lambda m: f"\n## {m.group(1)}\n", s)
    s = re.sub(r"(?is)<h[4-6][^>]*>(.*?)</h[4-6]>", lambda m: f"\n### {m.group(1)}\n", s)
    s = re.sub(r"(?is)<blockquote[^>]*>(.*?)</blockquote>", lambda m: f"\n> {m.group(1)}\n", s)
    s = re.sub(r"(?is)<li[^>]*>(.*?)</li>", lambda m: f"\n- {m.group(1)}", s)
    s = re.sub(r'(?is)<img[^>]*src="([^"]+)"[^>]*>', r"\n![](\1)\n", s)
    s = re.sub(r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", s)
    s = re.sub(r"(?is)<(strong|b)>(.*?)</\1>", r"**\2**", s)
    s = re.sub(r"(?is)<(em|i)>(.*?)</\1>", r"*\2*", s)
    s = re.sub(r"(?is)<code>(.*?)</code>", r"`\1`", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p>|</figure>|</ul>|</ol>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

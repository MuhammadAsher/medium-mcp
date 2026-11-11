from pathlib import Path

import pytest

from medium_mcp import feeds

FIXTURE = (Path(__file__).parent / "fixtures" / "user_feed.xml").read_bytes()


def test_parse_basic_fields():
    stories = feeds.parse_feed(FIXTURE)
    assert len(stories) == 2
    s = stories[0]
    assert s.title.startswith("Caching API Responses")
    assert s.url == "https://medium.com/@samplewriter/caching-api-responses-1a2b3c4d5e6f"  # tracking stripped
    assert s.author == "Sample Writer"
    assert s.tags == ["python", "fastapi", "caching"]
    assert s.reading_minutes >= 1
    assert "800ms" in s.summary and "&amp;" not in s.summary
    assert "content_markdown" not in s.to_dict()


def test_limit():
    assert len(feeds.parse_feed(FIXTURE, limit=1)) == 1


def test_include_content_markdown():
    md = feeds.parse_feed(FIXTURE, include_content=True)[0].content_markdown
    assert "## The problem" in md
    assert "**800ms**" in md
    assert "```\nfrom functools import lru_cache\n\n@lru_cache" in md
    assert "- Cache reads" in md
    assert "[the docs](https://example.com/docs)" in md
    assert "stat?event" not in md  # tracking pixel removed


@pytest.mark.parametrize(
    "fn,arg,expected",
    [
        (feeds.user_feed_url, "@asherazeem", "https://medium.com/feed/@asherazeem"),
        (feeds.user_feed_url, "asher.azeem", "https://medium.com/feed/@asher.azeem"),
        (feeds.publication_feed_url, "better-programming", "https://medium.com/feed/better-programming"),
        (feeds.tag_feed_url, "Machine Learning", "https://medium.com/feed/tag/machine-learning"),
    ],
)
def test_urls(fn, arg, expected):
    assert fn(arg) == expected


@pytest.mark.parametrize("bad", ["../../etc", "a/b", "x?y=1", "", "evil.com/@x"])
def test_rejects_bad_names(bad):
    with pytest.raises(feeds.FeedError):
        feeds.publication_feed_url(bad)


def test_bad_xml_gives_friendly_error():
    with pytest.raises(feeds.FeedError, match="valid feed"):
        feeds.parse_feed(b"<html>Just a moment...</html")

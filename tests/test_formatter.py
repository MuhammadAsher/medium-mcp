from medium_mcp.formatter import prepare_article

SAMPLE = """# How We Cut API Latency by 70% With Three Small Changes

Intro paragraph.

| Change | Before | After |
|---|---|---|
| Cache | 800ms | 240ms |
| Index | 240ms | 90ms |

#### Deep heading

# Accidental second title

- [x] done
- [ ] todo
  - nested item

![](chart.png)

```python
| not | a | table |
#### not a heading
```

Note[^1].
"""


def test_title_from_first_h1_and_kept_once():
    r = prepare_article(SAMPLE, subtitle="What we measured", tags=["python"])
    assert r.title == "How We Cut API Latency by 70% With Three Small Changes"
    assert r.content_markdown.startswith(f"# {r.title}\n### What we measured\n")
    assert r.content_markdown.count(f"# {r.title}") == 1


def test_table_converted_to_code_block():
    r = prepare_article(SAMPLE)
    assert "| Change |" not in r.content_markdown
    assert "Change  Before  After" in r.content_markdown
    assert any("table" in c for c in r.changes)


def test_headings_normalised():
    md = prepare_article(SAMPLE).content_markdown
    assert "### Deep heading" in md
    assert "## Accidental second title" in md


def test_code_blocks_left_untouched():
    md = prepare_article(SAMPLE).content_markdown
    assert "| not | a | table |" in md
    assert "#### not a heading" in md


def test_checklist_and_warnings():
    r = prepare_article(SAMPLE)
    assert "✅ done" in r.content_markdown and "⬜ todo" in r.content_markdown
    joined = " ".join(r.warnings)
    for needle in ("nested", "alt text", "Footnotes", "subtitle", "No tags"):
        assert needle in joined, needle


def test_tags_cleaned_and_capped():
    r = prepare_article("# T\n\nbody", tags=["#Python", "python", "AI", "a", "b", "c", "d", "x" * 30])
    assert r.tags == ["Python", "AI", "a", "b", "c"]
    assert any("25 characters" in w for w in r.warnings)
    assert any("allows 5 tags" in w for w in r.warnings)


def test_missing_title_and_unclosed_fence():
    r = prepare_article("no title here\n\n```\ncode")
    assert r.title == ""
    assert any("No title" in w for w in r.warnings)
    assert any("never closed" in w for w in r.warnings)


def test_reading_time():
    r = prepare_article("# T\n\n" + "word " * 530)
    assert r.word_count >= 530 and r.reading_minutes == 2


def test_footnote_and_html_checks_ignore_code_blocks():
    md = "# A title that is long enough to pass\n\n```python\nre.sub(r\"[^`]+\", x)\nhtml = \"<div>\"\n```\n"
    warnings = prepare_article(md).warnings
    assert not any("Footnotes" in w for w in warnings)
    assert not any("Raw HTML" in w for w in warnings)


def test_footnote_in_prose_still_warns():
    assert any("Footnotes" in w for w in prepare_article("# T\n\nClaim[^1].\n").warnings)


def test_only_long_code_blocks_warn():
    short = prepare_article("# A title that is long enough to pass\n\n```\nx = 1\n```\n")
    assert not any("Gist" in w for w in short.warnings)
    body = "\n".join(f"line{i}" for i in range(40))
    long = prepare_article(f"# A title that is long enough to pass\n\n```\n{body}\n```\n")
    assert any("Gist" in w for w in long.warnings)

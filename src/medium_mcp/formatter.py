"""Check and tidy Markdown so it publishes cleanly on Medium.

Medium's editor supports a smaller set of formatting than GitHub Markdown.
This module rewrites what it safely can and reports the rest as warnings,
so you see the problems before you paste or publish.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

WORDS_PER_MINUTE = 265
MAX_TAGS = 5
MAX_TAG_LENGTH = 25
MAX_TITLE_LENGTH = 100
GOOD_TITLE_RANGE = (40, 70)  # what tends to display without truncation in feeds
LONG_CODE_BLOCK_LINES = 30  # beyond this, suggest a Gist

_FENCE_RE = re.compile(r"^(```|~~~)")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_NESTED_LIST_RE = re.compile(r"^( {2,}|\t+)([-*+]|\d+\.)\s+")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
_FOOTNOTE_RE = re.compile(r"\[\^[^\]]+\]")
_HTML_TAG_RE = re.compile(r"</?(div|span|table|details|summary|sup|sub)\b", re.I)
_TASK_RE = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+")


@dataclass
class PreparedArticle:
    title: str
    subtitle: str | None
    tags: list[str]
    canonical_url: str | None
    word_count: int
    reading_minutes: int
    warnings: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    content_markdown: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_tag(tag: str) -> str:
    tag = re.sub(r"\s+", " ", tag.strip().lstrip("#"))
    return tag


def prepare_article(
    markdown: str,
    title: str | None = None,
    subtitle: str | None = None,
    tags: list[str] | None = None,
    canonical_url: str | None = None,
) -> PreparedArticle:
    warnings: list[str] = []
    changes: list[str] = []
    lines = markdown.replace("\r\n", "\n").split("\n")

    # ---- Title: use the argument, else the first H1 -------------------------
    first_h1_idx = next(
        (i for i, ln in enumerate(lines) if re.match(r"^#\s+\S", ln)), None
    )
    if not title and first_h1_idx is not None:
        title = lines[first_h1_idx][2:].strip()
    if not title:
        title = ""
        warnings.append("No title. Pass `title` or start the article with `# Your title`.")

    # Medium shows the content's first heading as the story title, so make sure
    # the body opens with it exactly once.
    if first_h1_idx is not None:
        del lines[first_h1_idx]
    if title:
        body_start = [f"# {title}"]
        if subtitle:
            # "###" pastes as Medium's small heading, which it styles as the
            # subtitle when it sits right under the title. "##" looks like a section.
            body_start.append(f"### {subtitle}")
        lines = body_start + [""] + _strip_leading_blank(lines)

    # ---- Walk the body -------------------------------------------------------
    out: list[str] = []
    in_fence = False
    table_buf: list[str] = []
    tables_converted = 0
    deep_headings = 0
    nested_lists = 0
    task_items = 0
    images_without_alt = 0
    extra_h1 = 0
    long_code_blocks = 0
    fence_lines = 0
    prose: list[str] = []  # lines outside code blocks, for footnote/HTML checks

    def flush_table() -> None:
        nonlocal tables_converted
        if not table_buf:
            return
        if len(table_buf) >= 2 and _TABLE_SEP_RE.match(table_buf[1]):
            out.append("```")
            out.extend(_render_table_as_text(table_buf))
            out.append("```")
            tables_converted += 1
        else:
            out.extend(table_buf)
        table_buf.clear()

    for idx, line in enumerate(lines):
        if _FENCE_RE.match(line.strip()):
            flush_table()
            if in_fence and fence_lines > LONG_CODE_BLOCK_LINES:
                long_code_blocks += 1
            fence_lines = 0
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            fence_lines += 1
            out.append(line)
            continue

        if _TABLE_ROW_RE.match(line) or (table_buf and _TABLE_SEP_RE.match(line)):
            table_buf.append(line)
            continue
        flush_table()
        prose.append(line)

        m = _HEADING_RE.match(line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and idx != 0:
                extra_h1 += 1
                line = f"## {text}"
            elif level >= 4:
                deep_headings += 1
                line = f"### {text}"

        if _NESTED_LIST_RE.match(line):
            nested_lists += 1
        if _TASK_RE.match(line):
            task_items += 1
            line = re.sub(r"\[[xX]\]", "✅", line, count=1)
            line = line.replace("[ ]", "⬜", 1)

        for alt, _src in _IMAGE_RE.findall(line):
            if not alt.strip():
                images_without_alt += 1

        out.append(line)
    flush_table()

    if in_fence:
        warnings.append("A code block is never closed (missing ```). Everything after it will show as code.")

    # ---- Report --------------------------------------------------------------
    if tables_converted:
        changes.append(
            f"Converted {tables_converted} table(s) to aligned text in a code block "
            "(Medium has no tables). For a nicer look, swap in a screenshot or a GitHub Gist."
        )
    if extra_h1:
        changes.append(f"Demoted {extra_h1} extra `#` heading(s) to `##` (only the title should be `#`).")
    if deep_headings:
        changes.append(
            f"Mapped {deep_headings} heading(s) of level 4+ to `###`. "
            "Medium only shows two heading sizes, so keep structure shallow."
        )
    if task_items:
        changes.append(f"Turned {task_items} checklist item(s) into ✅/⬜ (Medium has no checkboxes).")
    if nested_lists:
        warnings.append(
            f"{nested_lists} nested list item(s): Medium flattens nested lists. "
            "Consider rewriting as separate lists or short paragraphs."
        )
    if images_without_alt:
        warnings.append(f"{images_without_alt} image(s) have no alt text; add a short description for accessibility.")
    prose_text = "\n".join(prose)
    if _FOOTNOTE_RE.search(prose_text):
        warnings.append("Footnotes (`[^1]`) aren't supported on Medium; inline them or use a short 'Notes' section.")
    if _HTML_TAG_RE.search(prose_text):
        warnings.append("Raw HTML tags found; Medium ignores most HTML. Rewrite them as plain Markdown.")
    if long_code_blocks:
        warnings.append(
            f"{long_code_blocks} code block(s) over {LONG_CODE_BLOCK_LINES} lines. Medium highlights "
            "code itself, but long blocks are hard to read in an article; consider a GitHub Gist "
            "or trimming to the lines that matter."
        )

    if title and len(title) > MAX_TITLE_LENGTH:
        warnings.append(f"Title is {len(title)} characters; keep it under {MAX_TITLE_LENGTH}.")
    elif title and not (GOOD_TITLE_RANGE[0] <= len(title) <= GOOD_TITLE_RANGE[1]):
        warnings.append(
            f"Title is {len(title)} characters; {GOOD_TITLE_RANGE[0]}–{GOOD_TITLE_RANGE[1]} "
            "usually shows in full in feeds and search results."
        )
    if not subtitle:
        warnings.append("No subtitle. A one-line subtitle shows under the title and in previews.")

    clean_tags = _clean_tags(tags or [], warnings)
    if not clean_tags:
        warnings.append(f"No tags. Add up to {MAX_TAGS} so readers can find the story.")

    if canonical_url and not re.match(r"^https?://", canonical_url):
        warnings.append("canonical_url should be a full URL starting with https://")

    content = "\n".join(out).strip() + "\n"
    words = len(re.sub(r"```.*?```", " ", content, flags=re.S).split())

    return PreparedArticle(
        title=title,
        subtitle=subtitle,
        tags=clean_tags,
        canonical_url=canonical_url,
        word_count=words,
        reading_minutes=max(1, round(words / WORDS_PER_MINUTE)),
        warnings=warnings,
        changes=changes,
        content_markdown=content,
    )


def _clean_tags(tags: list[str], warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in tags:
        tag = normalize_tag(raw)
        if not tag or tag.lower() in seen:
            continue
        if len(tag) > MAX_TAG_LENGTH:
            warnings.append(f"Tag '{tag}' is over {MAX_TAG_LENGTH} characters and was dropped.")
            continue
        seen.add(tag.lower())
        result.append(tag)
    if len(result) > MAX_TAGS:
        warnings.append(f"Medium allows {MAX_TAGS} tags; kept the first {MAX_TAGS}: {', '.join(result[:MAX_TAGS])}.")
        result = result[:MAX_TAGS]
    return result


def _strip_leading_blank(lines: list[str]) -> list[str]:
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    return lines[i:]


def _render_table_as_text(rows: list[str]) -> list[str]:
    cells = [
        [c.strip() for c in r.strip().strip("|").split("|")]
        for i, r in enumerate(rows)
        if i != 1  # skip the |---|---| separator
    ]
    ncols = max(len(r) for r in cells)
    for r in cells:
        r.extend([""] * (ncols - len(r)))
    widths = [max(len(r[c]) for r in cells) for c in range(ncols)]
    rendered = [
        "  ".join(cell.ljust(widths[c]) for c, cell in enumerate(r)).rstrip() for r in cells
    ]
    rendered.insert(1, "  ".join("-" * w for w in widths))
    return rendered

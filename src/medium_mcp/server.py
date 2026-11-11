"""Medium MCP server.

Always available (no account needed):
  - get_user_stories, get_publication_stories, get_tag_stories  (public RSS)
  - prepare_article                                              (local checks)

Available only when MEDIUM_INTEGRATION_TOKEN is set (pre-2025 legacy token):
  - get_medium_profile, list_my_publications, upload_image, create_post
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import feeds
from .formatter import prepare_article as _prepare_article
from .medium_api import LICENSES, MediumAPIError, MediumClient

log = logging.getLogger("medium_mcp")

INSTRUCTIONS = """\
Tools for reading Medium and preparing articles for it.

Reading uses Medium's public RSS feeds, which return only the ~10 newest stories
for a user, publication or tag. Use include_content=true only when you need the
full text (it is much longer).

Before publishing or pasting anything into Medium, run prepare_article on the
Markdown and show the user its warnings. Medium has no tables, no nested lists,
no footnotes and only two heading sizes.

Publishing tools exist only if the user configured a legacy integration token.
create_post defaults to publish_status="draft". Never use "public" or "unlisted"
unless the user explicitly asked for that in this conversation. Medium's API
cannot edit or delete a post after it is created.
"""

mcp = MCPServer("medium", instructions=INSTRUCTIONS, version="0.1.0")

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True, idempotentHint=True)
LOCAL_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False, idempotentHint=True)

Limit = Annotated[int, Field(ge=1, le=10, description="How many stories to return (max 10).")]
IncludeContent = Annotated[
    bool, Field(description="Include each story's full text as Markdown. Much longer output.")
]


async def _call(fn, *args, **kwargs):
    """Run blocking I/O off the event loop; surface expected errors to the model.

    MCP 2.x hides the text of unexpected exceptions from the client, so errors
    the user can act on (bad username, revoked token...) are re-raised as ToolError.
    """
    try:
        return await asyncio.to_thread(functools.partial(fn, *args, **kwargs))
    except (feeds.FeedError, MediumAPIError) as e:
        raise ToolError(str(e)) from e


async def _stories(url_fn, name: str, limit: int, include_content: bool) -> dict:
    try:
        url = url_fn(name)
    except feeds.FeedError as e:
        raise ToolError(str(e)) from e
    stories = await _call(feeds.get_stories, url, limit, include_content)
    return {"source": url, "count": len(stories), "stories": [s.to_dict() for s in stories]}


# --------------------------------------------------------------------------- #
# Reading (public RSS)
# --------------------------------------------------------------------------- #

@mcp.tool(annotations=READ_ONLY)
async def get_user_stories(
    username: Annotated[str, Field(description="Medium username, with or without '@', e.g. 'asherazeem'.")],
    limit: Limit = 10,
    include_content: IncludeContent = False,
) -> dict:
    """Get the most recent stories by a Medium author (newest first)."""
    return await _stories(feeds.user_feed_url, username, limit, include_content)


@mcp.tool(annotations=READ_ONLY)
async def get_publication_stories(
    publication: Annotated[str, Field(description="Publication slug from its URL, e.g. 'better-programming'.")],
    limit: Limit = 10,
    include_content: IncludeContent = False,
) -> dict:
    """Get the most recent stories from a Medium publication."""
    return await _stories(feeds.publication_feed_url, publication, limit, include_content)


@mcp.tool(annotations=READ_ONLY)
async def get_tag_stories(
    tag: Annotated[str, Field(description="Medium tag, e.g. 'python' or 'machine learning'.")],
    limit: Limit = 10,
    include_content: IncludeContent = False,
) -> dict:
    """Get the latest stories Medium lists under a tag. Useful for spotting what's being written about a topic."""
    return await _stories(feeds.tag_feed_url, tag, limit, include_content)


# --------------------------------------------------------------------------- #
# Writing (local, no network)
# --------------------------------------------------------------------------- #

@mcp.tool(annotations=LOCAL_ONLY)
def prepare_article(
    markdown: Annotated[str, Field(description="The article body in Markdown.")],
    title: Annotated[str | None, Field(description="Story title. Defaults to the first '# ' heading.")] = None,
    subtitle: Annotated[str | None, Field(description="One-line subtitle shown under the title.")] = None,
    tags: Annotated[list[str] | None, Field(description="Up to 5 tags.")] = None,
    canonical_url: Annotated[
        str | None, Field(description="Original URL if this was first published elsewhere (protects SEO).")
    ] = None,
) -> dict:
    """Check Markdown against what Medium supports and return a cleaned version.

    Converts tables to aligned text, demotes extra/deep headings, turns checklists
    into emoji, and reports anything it can't fix (nested lists, footnotes, raw
    HTML, missing alt text, title length, tags). Also returns word count and
    reading time.
    """
    return _prepare_article(markdown, title, subtitle, tags, canonical_url).to_dict()


# --------------------------------------------------------------------------- #
# Publishing (legacy token only)
# --------------------------------------------------------------------------- #

def register_publishing_tools(client: MediumClient) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def get_medium_profile() -> dict:
        """Get the Medium profile linked to the configured integration token."""
        return await _call(client.me)

    @mcp.tool(annotations=READ_ONLY)
    async def list_my_publications() -> dict:
        """List publications the token's user belongs to, with their IDs (needed to post into one)."""
        pubs = await _call(client.publications)
        return {"count": len(pubs), "publications": pubs}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
    async def upload_image(
        file_path: Annotated[str, Field(description="Path to a local JPEG, PNG, GIF or TIFF (max 25 MB).")],
    ) -> dict:
        """Upload a local image to Medium and get back a URL to use in the article's Markdown."""
        return await _call(client.upload_image, file_path)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
    async def create_post(
        title: Annotated[str, Field(description="Story title.")],
        content_markdown: Annotated[
            str, Field(description="Body in Markdown. Run prepare_article first and pass its content_markdown.")
        ],
        tags: Annotated[list[str] | None, Field(description="Up to 5 tags.")] = None,
        publish_status: Annotated[
            Literal["draft", "unlisted", "public"],
            Field(description="Keep 'draft' unless the user explicitly asked to publish."),
        ] = "draft",
        canonical_url: Annotated[str | None, Field(description="Original URL if cross-posting.")] = None,
        publication_id: Annotated[
            str | None, Field(description="Post into this publication (ID from list_my_publications).")
        ] = None,
        license: Annotated[str | None, Field(description=f"One of: {', '.join(LICENSES)}.")] = None,
        notify_followers: Annotated[bool, Field(description="Notify followers. Only matters for public posts.")] = False,
    ) -> dict:
        """Create a Medium story. Defaults to a draft the user can review on medium.com.

        Medium's API can't edit or delete posts afterwards, so confirm title,
        tags and status with the user before calling with anything but 'draft'.
        """
        post = await _call(
            client.create_post,
            title=title,
            content=content_markdown,
            tags=tags,
            canonical_url=canonical_url,
            publish_status=publish_status,
            license=license,
            notify_followers=notify_followers,
            publication_id=publication_id,
        )
        return {
            "id": post.get("id"),
            "url": post.get("url"),
            "publish_status": post.get("publishStatus"),
            "tags": post.get("tags"),
            "note": "Drafts appear under medium.com/me/stories/drafts." if publish_status == "draft" else "",
        }


# --------------------------------------------------------------------------- #
# Prompt (shows up as a slash command in Claude Code)
# --------------------------------------------------------------------------- #

@mcp.prompt()
def draft_from_code(topic: str = "the changes on the current branch") -> str:
    """Turn code in the current project into a Medium article draft."""
    return f"""Write a Medium article about {topic}.

1. Read the relevant code, README, commits or diff in this project first.
2. Write for developers who haven't seen this codebase: open with the problem,
   then the approach, then short code snippets (only the interesting parts),
   then results and trade-offs. Aim for 5-8 minutes of reading.
3. Use only '#' for the title and '##' for sections. No tables, nested lists or footnotes.
4. Suggest a subtitle and up to 5 tags.
5. Run prepare_article on the draft, fix anything it warns about, and save the
   result as a .md file in the project. Don't publish anything."""


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = MediumClient.from_env()
    if client:
        register_publishing_tools(client)
        log.info("Publishing tools enabled (MEDIUM_INTEGRATION_TOKEN found).")
    else:
        log.info("No MEDIUM_INTEGRATION_TOKEN; running read and prepare tools only.")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

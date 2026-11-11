# medium-mcp

An MCP server that lets Claude read Medium and get your articles Medium-ready.
Works in Claude Code (terminal or the VS Code extension), the Claude desktop app,
and any other MCP client.

## How it works (no token needed)

1. **Research**: ask Claude what's being written under a tag or by an author.
2. **Draft**: `/mcp__medium__draft_from_code <topic>` writes an article from code in your project.
3. **Prepare**: `prepare_article` fixes what Medium can't display (tables, deep headings, checklists)
   and warns about the rest.
4. **Export**: `export_article` writes `<post>.medium.html`. Open it, click in the article,
   press Cmd+A, Cmd+C, and paste into [medium.com/new-story](https://medium.com/new-story).
   Medium keeps headings, bold, links, lists, quotes, images and code blocks.
   Add tags and subtitle in Medium's publish dialog.

## Tools

| Tool | What it does |
|---|---|
| `get_user_stories` | Latest stories by an author, with full text (public RSS) |
| `get_publication_stories` | Latest stories in a publication |
| `get_tag_stories` | Latest stories under a tag (Medium only includes an excerpt here) |
| `prepare_article` | Checks Markdown against what Medium supports, fixes what it can, returns warnings, word count and reading time |
| `export_article` | Runs `prepare_article`, then writes a paste-ready HTML page |

Plus one prompt, `draft_from_code`, which shows up as a slash command in Claude Code.

**Limits to know**
- RSS feeds only return the ~10 newest stories. There's no full archive or stats.
- Medium has no public way to post without an API token, and stopped issuing
  tokens in January 2025, hence the copy-paste step.

## Install (macOS)

Requires Python 3.10+.

```bash
cd medium-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest            # 36 tests, all offline
```

## Connect it to Claude Code (VS Code extension or terminal)

Both read the same config. Easiest: add a `.mcp.json` to the root of the project
you'll write articles from (use the full path to your venv):

```json
{
  "mcpServers": {
    "medium": {
      "command": "/Users/YOU/path/to/medium-mcp/.venv/bin/medium-mcp"
    }
  }
}
```

Or, if you have the `claude` CLI installed, register it for all projects:

```bash
claude mcp add --scope user medium -- /Users/YOU/path/to/medium-mcp/.venv/bin/medium-mcp
```

Start a new Claude Code session, approve the server when asked, and type `/mcp`
to confirm `medium` is connected.

## Try it

- "What has @username published on Medium lately?"
- "What's being written under the fastapi tag this week? Summarize the angles."
- "/mcp__medium__draft_from_code the caching layer in src/cache"
- "Run prepare_article on docs/post.md and fix the warnings."
- "Export docs/post.md for Medium."

## Project layout

```
src/medium_mcp/
  server.py      MCP tools, prompt, entry point
  feeds.py       RSS fetch/parse, HTML -> Markdown (stdlib only)
  formatter.py   Medium compatibility checks and rewrites
  export.py      Markdown -> paste-ready HTML
  _http.py       HTTPS using the OS trust store
  medium_api.py  Legacy REST client (token only)
tests/           Offline tests with a fixture feed
```

Dependencies: the `mcp` SDK (v2) and `truststore` (so HTTPS works with python.org
builds on macOS). HTTP, XML and Markdown use the standard library.

## Next steps

- Wrap this in a Claude Code plugin: bundle the server with `/medium-draft` and
  `/medium-publish` commands and a writing-style skill.
- Add a `cross_post` tool that sets `canonical_url` from your own blog's URL.

## Legacy: direct publishing with an old token

Only if you have an integration token created before January 2025. Setting one adds
`get_medium_profile`, `list_my_publications`, `upload_image` and `create_post`
(defaults to draft; Medium's API can't edit or delete posts afterwards).

```json
"medium": {
  "command": "/Users/YOU/path/to/medium-mcp/.venv/bin/medium-mcp",
  "env": { "MEDIUM_INTEGRATION_TOKEN": "your-token" }
}
```

Don't commit a `.mcp.json` that contains your token. Put it in
`~/.claude.json` via `claude mcp add --scope user ... -e MEDIUM_INTEGRATION_TOKEN=...`
instead.

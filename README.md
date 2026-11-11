# medium-mcp

An MCP server that lets Claude read Medium and get your articles Medium-ready.
Works in Claude Code (terminal or the VS Code extension), the Claude desktop app,
and any other MCP client.

## Tools

| Tool | Needs a token? | What it does |
|---|---|---|
| `get_user_stories` | No | Latest stories by an author (public RSS) |
| `get_publication_stories` | No | Latest stories in a publication |
| `get_tag_stories` | No | Latest stories under a tag |
| `prepare_article` | No | Checks Markdown against what Medium supports, fixes what it can, returns warnings, word count and reading time |
| `get_medium_profile` | Yes | Profile linked to your token |
| `list_my_publications` | Yes | Publications you can post to, with IDs |
| `upload_image` | Yes | Uploads a local image, returns a Medium URL |
| `create_post` | Yes | Creates a story. **Defaults to draft** |

Plus one prompt, `draft_from_code`, which shows up as a slash command in Claude Code
and turns code in your project into an article draft.

**Limits to know**
- RSS feeds only return the ~10 newest stories. There's no full archive or stats.
- Medium stopped issuing integration tokens in January 2025. Publishing tools
  appear only if you set a token created before then.
- Medium's API can't edit or delete a post after it's created, which is why
  `create_post` defaults to `draft`.

## Install (macOS)

Requires Python 3.10+.

```bash
cd medium-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest            # 27 tests, all offline
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

### Optional: enable publishing

Only if you have a pre-2025 integration token (Medium → Settings → Security
and apps → Integration tokens):

```json
"medium": {
  "command": "/Users/YOU/path/to/medium-mcp/.venv/bin/medium-mcp",
  "env": { "MEDIUM_INTEGRATION_TOKEN": "your-token" }
}
```

Don't commit a `.mcp.json` that contains your token. Put it in
`~/.claude.json` via `claude mcp add --scope user ... -e MEDIUM_INTEGRATION_TOKEN=...`
instead.

## Try it

- "What has @username published on Medium lately?"
- "What's being written under the fastapi tag this week? Summarize the angles."
- "/mcp__medium__draft_from_code the caching layer in src/cache"
- "Run prepare_article on docs/post.md and fix the warnings."

## Project layout

```
src/medium_mcp/
  server.py      MCP tools, prompt, entry point
  feeds.py       RSS fetch/parse, HTML -> Markdown (stdlib only)
  formatter.py   Medium compatibility checks and rewrites
  medium_api.py  Legacy REST client (token only)
tests/           Offline tests with a fixture feed
```

The only dependency is the `mcp` SDK (v2). HTTP and XML use the standard library.

## Next steps

- Wrap this in a Claude Code plugin: bundle the server with `/medium-draft` and
  `/medium-publish` commands and a writing-style skill.
- Add a `cross_post` tool that sets `canonical_url` from your own blog's URL.

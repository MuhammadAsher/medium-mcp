# Changelog

## 0.2.0 (2026-11-11)

First public release, published to PyPI as `medium-writer-mcp`.

- `open_in_medium` (macOS): copies the prepared article to the clipboard as rich
  text and opens a new Medium story in your browser. No login, no automation.
- `export_article`: writes a paste-ready HTML page, for any OS.
- `prepare_article`: checks and rewrites Markdown for what Medium supports.
- `get_user_stories`, `get_publication_stories`, `get_tag_stories`: read Medium's
  public RSS feeds.
- `draft_from_code` prompt: drafts an article from code in your project.
- HTTPS uses the OS trust store (`truststore`), so it works with python.org
  Python on macOS.
- Legacy publishing tools when a pre-2025 `MEDIUM_INTEGRATION_TOKEN` is set.

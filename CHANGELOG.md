# Changelog

## 0.2.1 (2026-11-11)

First version on PyPI (the 0.2.0 release job never ran).

- Subtitle is pasted as a small heading, so Medium styles it as the subtitle
  instead of a section heading.
- Apostrophes outside code are curled (’) before pasting, so a paragraph no
  longer mixes ' and ’.
- The "Medium doesn't highlight code" warning is gone (Medium highlights code
  blocks itself). The formatter now only flags code blocks over 30 lines.

## 0.2.0 (2026-11-11)

Tagged but not published.

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

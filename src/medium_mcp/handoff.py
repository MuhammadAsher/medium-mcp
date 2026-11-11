"""Hand an article to Medium without logging in or automating a browser.

Puts the article on the macOS clipboard as rich text (HTML plus a plain-text
fallback) and opens medium.com/new-story in the user's normal browser, where
they're already signed in. The user presses Cmd+V and publishes.

macOS only; uses the built-in `osascript` (JavaScript for Automation) and `open`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

NEW_STORY_URL = "https://medium.com/new-story"
BROWSER_ENV = "MEDIUM_BROWSER"
DEFAULT_BROWSER = "Safari"

# Reads the HTML and text from files (no size limits or quoting issues) and
# writes both flavours to the general pasteboard.
_JXA = """
ObjC.import('AppKit');
function run(argv) {
  var read = function (p) {
    return $.NSString.stringWithContentsOfFileEncodingError($(p), $.NSUTF8StringEncoding, null);
  };
  var pb = $.NSPasteboard.generalPasteboard;
  pb.clearContents;
  var ok = pb.setStringForType(read(argv[0]), $.NSPasteboardTypeHTML)
        && pb.setStringForType(read(argv[1]), $.NSPasteboardTypeString);
  return ok ? 'ok' : 'failed';
}
"""


class HandoffError(Exception):
    """A problem the user can act on (wrong OS, browser not installed...)."""


def _require_macos() -> None:
    if sys.platform != "darwin":
        raise HandoffError(
            "open_in_medium only works on macOS. Use export_article and paste the HTML page instead."
        )


def copy_rich_text(html_fragment: str, plain_text: str) -> None:
    """Put HTML (with a plain-text fallback) on the macOS clipboard."""
    _require_macos()
    html_doc = f'<html><head><meta charset="utf-8"></head><body>{html_fragment}</body></html>'
    with tempfile.TemporaryDirectory(prefix="medium-mcp-") as tmp:
        html_path, text_path = Path(tmp, "a.html"), Path(tmp, "a.txt")
        html_path.write_text(html_doc, encoding="utf-8")
        text_path.write_text(plain_text, encoding="utf-8")
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", _JXA, str(html_path), str(text_path)],
                capture_output=True, text=True, timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise HandoffError(f"Couldn't run osascript to set the clipboard: {e}") from e
    if result.returncode != 0 or result.stdout.strip() != "ok":
        raise HandoffError(f"Couldn't copy to the clipboard: {(result.stderr or result.stdout).strip()}")


def resolve_browser(browser: str | None) -> str | None:
    """Pick the browser app: argument, then $MEDIUM_BROWSER, then Safari. 'default' = system default."""
    choice = (browser or os.environ.get(BROWSER_ENV) or DEFAULT_BROWSER).strip()
    return None if choice.lower() in {"default", "system", ""} else choice


def open_url(url: str, browser: str | None) -> None:
    """Open a URL in the named macOS app (e.g. 'Safari', 'Google Chrome'), or the default browser."""
    _require_macos()
    cmd = ["open", "-a", browser, url] if browser else ["open", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise HandoffError(f"Couldn't open the browser: {e}") from e
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise HandoffError(
            f"Couldn't open {browser or 'the default browser'}: {detail}. "
            "Use the app's name as shown in /Applications, e.g. 'Safari' or 'Google Chrome', or 'default'."
        )

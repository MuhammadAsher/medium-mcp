"""Minimal client for Medium's legacy REST API (api.medium.com/v1).

Medium stopped issuing new integration tokens in January 2025. Tokens created
before that still work, so this client is only switched on when
MEDIUM_INTEGRATION_TOKEN is set. The API can create posts and upload images;
it cannot edit, delete or list posts, or read stats.
"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from . import _http

API_BASE = "https://api.medium.com/v1"
TIMEOUT_SECONDS = 30
PUBLISH_STATUSES = ("draft", "unlisted", "public")
LICENSES = (
    "all-rights-reserved", "cc-40-by", "cc-40-by-sa", "cc-40-by-nd",
    "cc-40-by-nc", "cc-40-by-nc-nd", "cc-40-by-nc-sa", "cc-40-zero", "public-domain",
)
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/tiff"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024


class MediumAPIError(Exception):
    pass


class MediumClient:
    def __init__(self, token: str):
        if not token:
            raise MediumAPIError("No Medium integration token provided.")
        self._token = token
        self._me: dict | None = None

    @classmethod
    def from_env(cls) -> "MediumClient | None":
        token = os.environ.get("MEDIUM_INTEGRATION_TOKEN", "").strip()
        return cls(token) if token else None

    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, body: bytes | None = None,
                 content_type: str = "application/json") -> dict:
        req = urllib.request.Request(
            f"{API_BASE}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "Accept-Charset": "utf-8",
                **({"Content-Type": content_type} if body is not None else {}),
            },
        )
        try:
            with _http.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                errs = json.loads(e.read()).get("errors", [])
                detail = "; ".join(f"{x.get('message')} (code {x.get('code')})" for x in errs)
            except Exception:
                pass
            if e.code == 401:
                raise MediumAPIError("Medium rejected the token (401). It may have been revoked.") from e
            raise MediumAPIError(f"Medium API error {e.code}: {detail or e.reason}") from e
        except urllib.error.URLError as e:
            raise MediumAPIError(f"Couldn't reach Medium: {e.reason}") from e
        return payload.get("data", payload)

    # ------------------------------------------------------------------ #
    def me(self) -> dict:
        if self._me is None:
            self._me = self._request("GET", "/me")
        return self._me

    def publications(self) -> list[dict]:
        return self._request("GET", f"/users/{self.me()['id']}/publications")

    def create_post(
        self,
        title: str,
        content: str,
        content_format: str = "markdown",
        tags: list[str] | None = None,
        canonical_url: str | None = None,
        publish_status: str = "draft",
        license: str | None = None,
        notify_followers: bool = False,
        publication_id: str | None = None,
    ) -> dict:
        if publish_status not in PUBLISH_STATUSES:
            raise MediumAPIError(f"publish_status must be one of {PUBLISH_STATUSES}")
        if content_format not in ("markdown", "html"):
            raise MediumAPIError("content_format must be 'markdown' or 'html'")
        if license and license not in LICENSES:
            raise MediumAPIError(f"license must be one of {LICENSES}")

        body: dict = {
            "title": title,
            "contentFormat": content_format,
            "content": content,
            "publishStatus": publish_status,
            "notifyFollowers": notify_followers,
        }
        if tags:
            body["tags"] = tags[:5]
        if canonical_url:
            body["canonicalUrl"] = canonical_url
        if license:
            body["license"] = license

        path = (
            f"/publications/{publication_id}/posts"
            if publication_id
            else f"/users/{self.me()['id']}/posts"
        )
        return self._request("POST", path, json.dumps(body).encode("utf-8"))

    def upload_image(self, file_path: str) -> dict:
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise MediumAPIError(f"File not found: {path}")
        mime = mimetypes.guess_type(path.name)[0] or ""
        if mime not in IMAGE_TYPES:
            raise MediumAPIError("Medium accepts JPEG, PNG, GIF or TIFF images only.")
        data = path.read_bytes()
        if len(data) > MAX_IMAGE_BYTES:
            raise MediumAPIError("Image is larger than 25 MB.")

        boundary = uuid.uuid4().hex
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            data,
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        return self._request("POST", "/images", body, f"multipart/form-data; boundary={boundary}")

"""Shared HTTPS context.

Python from python.org on macOS ships without a CA bundle, so plain urllib fails
with CERTIFICATE_VERIFY_FAILED until "Install Certificates.command" is run.
truststore verifies against the operating system's trust store instead, which
works out of the box on macOS, Windows and Linux.
"""

from __future__ import annotations

import ssl
import urllib.request

try:
    import truststore

    SSL_CONTEXT: ssl.SSLContext = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except ImportError:  # pragma: no cover - truststore is a declared dependency
    SSL_CONTEXT = ssl.create_default_context()


def urlopen(req: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT)

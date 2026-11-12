"""URL, SSRF, file-upload, and tool-argument validation."""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".pdf", ".csv", ".json"}
BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata.google.internal"}


class UnsafeURLError(ValueError):
    """Raised when a URL violates SSRF or protocol boundaries."""


def _is_forbidden_ip(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_external_url(url: str, resolve_dns: bool = False) -> str:
    """Ensure a URL uses HTTP/HTTPS and does not target internal/private networks."""
    cleaned = (url or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Unsupported URL scheme: {parsed.scheme!r}")
    if not parsed.netloc or not parsed.hostname:
        raise UnsafeURLError("URL missing valid hostname")

    host = parsed.hostname.lower()
    if host in BLOCKED_HOSTNAMES or host.endswith(".local") or host.endswith(".internal"):
        raise UnsafeURLError(f"Blocked internal hostname: {host!r}")
    if _is_forbidden_ip(host):
        raise UnsafeURLError(f"Blocked non-public IP address: {host!r}")

    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                addr = info[4][0]
                if _is_forbidden_ip(addr):
                    raise UnsafeURLError(f"Hostname {host!r} resolved to forbidden IP {addr!r}")
        except socket.gaierror:
            pass

    return cleaned


def validate_upload_filename(filename: str, size_bytes: int, max_bytes: int) -> str:
    """Validate uploaded filename extension and size."""
    if size_bytes <= 0:
        raise ValueError("Uploaded file is empty")
    if size_bytes > max_bytes:
        raise ValueError(f"Uploaded file exceeds maximum allowed size of {max_bytes} bytes")
    safe_name = Path(filename or "document.txt").name
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type {ext!r}. Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}"
        )
    return safe_name

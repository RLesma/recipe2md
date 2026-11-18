"""HTTP fetching, URL fallback generation, and image downloading."""

import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_url(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def candidate_urls(url: str) -> List[str]:
    """Generate fallback URLs for AMP cache links, mobile params, or http->https."""
    candidates: List[str] = [url]
    parsed = urllib.parse.urlsplit(url)

    # 1. Google AMP cache: *.cdn.ampproject.org/v/s/<host>/<path>... and/or ampshare=
    if "cdn.ampproject.org" in parsed.netloc.lower():
        for part in (parsed.fragment, parsed.query):
            m = re.search(r"ampshare=([^&]+)", part)
            if m:
                candidates.append(urllib.parse.unquote(m.group(1)))
        amp_m = re.match(r"^/v/(s/)?([^/]+)(/.*)$", parsed.path)
        if amp_m:
            scheme = "https" if amp_m.group(1) else "http"
            host = amp_m.group(2)
            path = amp_m.group(3)
            candidates.append(f"{scheme}://{host}{path}")
            stripped_amp = re.sub(r"/amp/?$", "/", path)
            if stripped_amp != path:
                candidates.append(f"{scheme}://{host}{stripped_amp}")

    # 2. Strip Blogger mobile ?m=1 or tracking fragments
    if parsed.query:
        qs = [
            (k, v)
            for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() != "m"
        ]
        new_q = urllib.parse.urlencode(qs)
        if new_q != parsed.query:
            candidates.append(
                urllib.parse.urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, new_q, "")
                )
            )
    if parsed.fragment:
        candidates.append(
            urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")
            )
        )

    # 3. http -> https fallback
    if parsed.scheme.lower() == "http":
        candidates.append(
            urllib.parse.urlunsplit(
                ("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment)
            )
        )

    seen = set()
    unique: List[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def guess_image_ext(url: str, content_type: str = "") -> str:
    ct = content_type.lower()
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    path = urllib.parse.urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _encode_url_path(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    encoded_path = urllib.parse.quote(parts.path, safe="/%")
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment)
    )


def download_image(url: str, dest_dir: Path, base_name: str) -> Optional[str]:
    try:
        safe_url = _encode_url_path(url)
        req = urllib.request.Request(safe_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type", "")
        ext = guess_image_ext(url, ct)
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{base_name}{ext}"
        (dest_dir / filename).write_bytes(data)
        return filename
    except Exception as exc:
        print(f"  [warn] Could not download image {url}: {exc}", file=sys.stderr)
        return None

"""Text and HTML utility functions."""

import html
import re
import unicodedata
from typing import Optional


def slugify(text: str, max_len: int = 80) -> str:
    norm = unicodedata.normalize("NFKD", text)
    ascii_text = norm.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "receta"


def clean_whitespace(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return clean_whitespace(text)


def format_iso_duration(duration: Optional[str]) -> Optional[str]:
    if not duration or not isinstance(duration, str):
        return None
    m = re.match(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", duration.strip())
    if not m:
        return duration.strip()
    days, hours, mins, secs = (int(x) if x else 0 for x in m.groups())
    parts = []
    if days:
        parts.append(f"{days} d")
    if hours:
        parts.append(f"{hours} h")
    if mins:
        parts.append(f"{mins} min")
    if secs and not parts:
        parts.append(f"{secs} s")
    return " ".join(parts) if parts else None


def yaml_escape(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def extract_meta_tag(raw_html: str, prop: str) -> Optional[str]:
    patterns = [
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(prop)}["\']',
    ]
    for pat in patterns:
        m = re.search(pat, raw_html, re.I)
        if m:
            return html.unescape(m.group(1).strip())
    return None

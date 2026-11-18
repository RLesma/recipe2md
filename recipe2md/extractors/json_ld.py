"""JSON-LD extraction and schema.org Recipe helpers."""

import html
import json
import re
from typing import Any, Dict, List, Optional

from ..utils import clean_whitespace


def _parse_json_lenient(raw: str) -> Any:
    text = raw.strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        cleaned = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        return json.loads(cleaned, strict=False)


def extract_json_ld(raw_html: str) -> List[Dict[str, Any]]:
    blocks = re.findall(
        r'<script[^>]*type=["\']?application/ld\+json[^"\'>]*["\']?[^>]*>(.*?)</script>',
        raw_html,
        re.S | re.I,
    )
    items: List[Dict[str, Any]] = []
    for block in blocks:
        try:
            data = _parse_json_lenient(block)
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            curr = stack.pop(0)
            if isinstance(curr, list):
                stack.extend(curr)
            elif isinstance(curr, dict):
                if "@graph" in curr and isinstance(curr["@graph"], list):
                    stack.extend(curr["@graph"])
                items.append(curr)
    return items


def has_type(item: Dict[str, Any], target: str) -> bool:
    t = item.get("@type")
    if isinstance(t, list):
        return target in t
    return t == target


def pick_image_url(val: Any) -> Optional[str]:
    if not val:
        return None
    if isinstance(val, str):
        return html.unescape(val.strip())
    if isinstance(val, list):
        for entry in val:
            url = pick_image_url(entry)
            if url:
                return url
    if isinstance(val, dict):
        return pick_image_url(val.get("url") or val.get("contentUrl"))
    return None


def parse_instructions_from_jsonld(raw_inst: Any) -> List[str]:
    steps: List[str] = []
    if not raw_inst:
        return steps
    if isinstance(raw_inst, str):
        for line in raw_inst.splitlines():
            line = clean_whitespace(line)
            if line:
                steps.append(line)
        return steps
    if isinstance(raw_inst, list):
        for entry in raw_inst:
            if isinstance(entry, str):
                s = clean_whitespace(entry)
                if s:
                    steps.append(s)
            elif isinstance(entry, dict):
                if has_type(entry, "HowToSection") and entry.get("itemListElement"):
                    sec_name = clean_whitespace(str(entry.get("name", "")))
                    if sec_name:
                        steps.append(f"**{sec_name}**")
                    steps.extend(parse_instructions_from_jsonld(entry["itemListElement"]))
                else:
                    text = entry.get("text") or entry.get("name") or ""
                    s = clean_whitespace(str(text))
                    if s:
                        steps.append(s)
    return steps

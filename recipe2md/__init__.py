"""recipe2md package for converting recipe URLs into Obsidian-ready Markdown."""

from .cli import load_urls, main
from .extractors import (
    ElComidistaBodyParser,
    extract_json_ld,
    extract_legacy_html_recipe,
    extract_recipe,
    has_type,
    parse_instructions_from_jsonld,
    parse_plain_text_recipe,
    pick_image_url,
)
from .models import Recipe
from .network import (
    USER_AGENT,
    _encode_url_path,
    candidate_urls,
    download_image,
    fetch_url,
    guess_image_ext,
)
from .renderer import render_markdown
from .storage import index_existing_sources, process_url, save_recipe
from .utils import (
    clean_whitespace,
    extract_meta_tag,
    format_iso_duration,
    slugify,
    strip_tags,
    yaml_escape,
)

__all__ = [
    "ElComidistaBodyParser",
    "Recipe",
    "USER_AGENT",
    "_encode_url_path",
    "candidate_urls",
    "clean_whitespace",
    "download_image",
    "extract_json_ld",
    "extract_legacy_html_recipe",
    "extract_meta_tag",
    "extract_recipe",
    "fetch_url",
    "format_iso_duration",
    "guess_image_ext",
    "has_type",
    "index_existing_sources",
    "load_urls",
    "main",
    "parse_instructions_from_jsonld",
    "parse_plain_text_recipe",
    "pick_image_url",
    "process_url",
    "render_markdown",
    "save_recipe",
    "slugify",
    "strip_tags",
    "yaml_escape",
]

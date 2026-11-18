#!/usr/bin/env python3
"""CLI entrypoint for recipe2md (re-exports public API for backward compatibility)."""

import sys

from recipe2md import (
    ElComidistaBodyParser,
    Recipe,
    USER_AGENT,
    _encode_url_path,
    candidate_urls,
    clean_whitespace,
    download_image,
    extract_json_ld,
    extract_legacy_html_recipe,
    extract_meta_tag,
    extract_recipe,
    fetch_url,
    format_iso_duration,
    guess_image_ext,
    has_type,
    index_existing_sources,
    load_urls,
    main,
    parse_instructions_from_jsonld,
    parse_plain_text_recipe,
    pick_image_url,
    process_url,
    render_markdown,
    save_recipe,
    slugify,
    strip_tags,
    yaml_escape,
)

if __name__ == "__main__":
    sys.exit(main())

"""Filesystem storage, frontmatter indexing, and URL processing pipeline."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .extractors import extract_recipe
from .models import Recipe
from .network import candidate_urls, download_image, fetch_url
from .renderer import render_markdown
from .utils import slugify


def index_existing_sources(out_dir: Path) -> Dict[str, Path]:
    """Map normalized source URLs from existing Markdown frontmatter in out_dir."""
    sources: Dict[str, Path] = {}
    if not out_dir.exists():
        return sources
    for md_file in out_dir.glob("*.md"):
        try:
            with md_file.open("r", encoding="utf-8", errors="replace") as fh:
                first_line = fh.readline().strip()
                if first_line != "---":
                    continue
                for line in fh:
                    stripped = line.strip()
                    if stripped == "---":
                        break
                    m = re.match(r'^source:\s*["\']?(.*?)["\']?\s*$', stripped)
                    if m and m.group(1):
                        sources[m.group(1)] = md_file
                        break
        except OSError:
            continue
    return sources


def save_recipe(
    recipe: Union[Recipe, dict],
    out_dir: Path,
    images_subdir: str,
    download_images: bool,
    use_checkboxes: bool,
    overwrite: bool,
) -> Path:
    slug = slugify(recipe["title"])
    md_path = out_dir / f"{slug}.md"
    if md_path.exists() and not overwrite:
        suffix = abs(hash(recipe["url"])) % 10000
        md_path = out_dir / f"{slug}-{suffix}.md"
        slug = f"{slug}-{suffix}"

    subdir = images_subdir.strip("/").strip()
    if subdir in ("", "."):
        subdir = ""
        images_dir = out_dir
    else:
        images_dir = out_dir / subdir

    def format_img_ref(filename: str) -> str:
        return f"{subdir}/{filename}" if subdir else filename

    hero_ref: Optional[str] = None
    if recipe.get("hero_image"):
        if download_images:
            fname = download_image(recipe["hero_image"], images_dir, slug)
            hero_ref = format_img_ref(fname) if fname else recipe["hero_image"]
        else:
            hero_ref = recipe["hero_image"]

    inline_refs: List[Tuple[str, str]] = []
    seen_urls = {recipe.get("hero_image")}
    for idx, (img_url, alt) in enumerate(recipe.get("inline_images", []), start=1):
        if img_url in seen_urls:
            continue
        seen_urls.add(img_url)
        if download_images:
            fname = download_image(img_url, images_dir, f"{slug}-{idx}")
            ref = format_img_ref(fname) if fname else img_url
        else:
            ref = img_url
        inline_refs.append((ref, alt))

    md_content = render_markdown(
        recipe, hero_ref, inline_refs, use_checkboxes=use_checkboxes
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"  Saved -> {md_path}")
    return md_path


def process_url(
    url: str,
    out_dir: Path,
    images_subdir: str,
    download_images: bool,
    use_checkboxes: bool,
    overwrite: bool,
) -> Path:
    print(f"Fetching: {url}")
    last_exc: Optional[Exception] = None
    recipe: Optional[Recipe] = None
    for idx, cand in enumerate(candidate_urls(url)):
        if idx > 0:
            print(f"  [alt-url] Trying {cand}")
        try:
            raw_bytes = fetch_url(cand)
            raw_html = raw_bytes.decode("utf-8", errors="replace")
            extracted = extract_recipe(cand, raw_html)
            if not extracted.has_content:
                raise ValueError("No ingredients or instructions could be extracted")
            extracted.url = url  # Keep original URL for duplicate-skipping
            recipe = extracted
            break
        except Exception as exc:
            last_exc = exc

    if recipe is None:
        assert last_exc is not None
        raise last_exc

    return save_recipe(
        recipe=recipe,
        out_dir=out_dir,
        images_subdir=images_subdir,
        download_images=download_images,
        use_checkboxes=use_checkboxes,
        overwrite=overwrite,
    )

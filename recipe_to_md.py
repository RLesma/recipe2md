#!/usr/bin/env python3
"""Convert recipe URLs (especially El Comidista / El País) into Obsidian-ready Markdown files."""

import argparse
import html
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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


def extract_json_ld(raw_html: str) -> List[Dict[str, Any]]:
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw_html,
        re.S | re.I,
    )
    items: List[Dict[str, Any]] = []
    for block in blocks:
        try:
            data = json.loads(block.strip())
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


class ElComidistaBodyParser(HTMLParser):
    """Parses El Comidista / El País article body for context paragraphs, images, and structured recipe."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.body_depth = 0

        self.in_aside = False
        self.aside_depth = 0

        self.in_si = False
        self.si_depth = 0

        self.in_si_i = False
        self.si_i_depth = 0

        self.in_si_d = False
        self.si_d_depth = 0

        self.in_figure = False
        self.figure_depth = 0

        self.in_p = False
        self.p_buf: List[str] = []
        self.link_href: Optional[str] = None
        self.link_buf: List[str] = []
        self.in_em = False
        self.in_strong = False

        self.context_paragraphs: List[str] = []
        self.inline_images: List[Tuple[str, str]] = []  # (url, alt)

        # Structured ingredients: list of (heading_or_None, [items])
        self.ingredient_sections: List[Tuple[Optional[str], List[str]]] = []
        self._curr_ing_heading: Optional[str] = None
        self._curr_ing_items: List[str] = []
        self._in_ing_heading = False
        self._ing_heading_buf: List[str] = []
        self._in_ing_li = False
        self._ing_li_buf: List[str] = []

        # Structured instructions
        self.instructions: List[str] = []
        self._in_step_div = False
        self._step_depth = 0
        self._step_buf: List[str] = []

    def _attrs_dict(self, attrs: List[Tuple[str, Optional[str]]]) -> Dict[str, str]:
        return {k.lower(): (v or "") for k, v in attrs}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        ad = self._attrs_dict(attrs)
        cls = ad.get("class", "")
        classes = set(cls.split())

        if not self.in_body:
            if tag == "div" and (
                ad.get("data-dtm-region") == "articulo_cuerpo"
                or "a_c" in classes
            ):
                self.in_body = True
                self.body_depth = 1
            return

        self.body_depth += 1

        if tag == "aside" or "w-sea" in classes:
            if not self.in_aside:
                self.in_aside = True
                self.aside_depth = 1
            else:
                self.aside_depth += 1
            return
        if self.in_aside:
            self.aside_depth += 1
            return

        # Recipe box (.si)
        if tag == "div" and "si" in classes and not self.in_si:
            self.in_si = True
            self.si_depth = 1
            return
        if self.in_si:
            self.si_depth += 1
            if tag == "div" and "si_i" in classes and not self.in_si_i:
                self.in_si_i = True
                self.si_i_depth = 1
                return
            if self.in_si_i:
                self.si_i_depth += 1
                if tag in ("h3", "h4") and "si_m_l_h" in classes:
                    self._in_ing_heading = True
                    self._ing_heading_buf = []
                elif tag == "li":
                    self._in_ing_li = True
                    self._ing_li_buf = []
                return

            if tag == "div" and "si_d" in classes and not self.in_si_d:
                self.in_si_d = True
                self.si_d_depth = 1
                return
            if self.in_si_d:
                self.si_d_depth += 1
                if tag == "div" and "si_m_p_div" in classes and not self._in_step_div:
                    self._in_step_div = True
                    self._step_depth = 1
                    self._step_buf = []
                elif self._in_step_div:
                    self._step_depth += 1
                return
            return

        # Figures / images inside body (before .si)
        if tag == "figure":
            self.in_figure = True
            self.figure_depth = 1
        elif self.in_figure:
            self.figure_depth += 1

        if tag == "img" and self.in_figure:
            src = ad.get("src") or ad.get("data-src") or ""
            if not src and ad.get("srcset"):
                src = ad["srcset"].split(",")[0].strip().split(" ")[0]
            alt = ad.get("alt", "").strip()
            if src and not src.endswith(".svg") and "the-trust-project" not in src:
                self.inline_images.append((html.unescape(src), alt))

        # Paragraphs for context (only before .si)
        if tag == "p" and not self.in_p:
            self.in_p = True
            self.p_buf = []
        elif self.in_p:
            if tag == "a" and ad.get("href"):
                self.link_href = ad["href"]
                self.link_buf = []
            elif tag in ("em", "i") and not self.in_em:
                self.in_em = True
                self.p_buf.append("*")
            elif tag in ("strong", "b") and not self.in_strong:
                self.in_strong = True
                self.p_buf.append("**")

    def handle_endtag(self, tag: str) -> None:
        if not self.in_body:
            return

        if self.in_aside:
            self.aside_depth -= 1
            if self.aside_depth <= 0:
                self.in_aside = False
            self.body_depth -= 1
            return

        if self.in_si:
            if self.in_si_i:
                if self._in_ing_heading and tag in ("h3", "h4"):
                    self._in_ing_heading = False
                    heading = clean_whitespace("".join(self._ing_heading_buf))
                    if self._curr_ing_items or self._curr_ing_heading is not None:
                        self.ingredient_sections.append(
                            (self._curr_ing_heading, self._curr_ing_items)
                        )
                    self._curr_ing_heading = heading or None
                    self._curr_ing_items = []
                elif self._in_ing_li and tag == "li":
                    self._in_ing_li = False
                    item = clean_whitespace("".join(self._ing_li_buf))
                    if item:
                        self._curr_ing_items.append(item)
                self.si_i_depth -= 1
                if self.si_i_depth <= 0:
                    self.in_si_i = False
                    if self._curr_ing_items or self._curr_ing_heading is not None:
                        self.ingredient_sections.append(
                            (self._curr_ing_heading, self._curr_ing_items)
                        )
                        self._curr_ing_heading = None
                        self._curr_ing_items = []
            elif self.in_si_d:
                if self._in_step_div:
                    self._step_depth -= 1
                    if self._step_depth <= 0:
                        self._in_step_div = False
                        step = clean_whitespace("".join(self._step_buf))
                        if step:
                            self.instructions.append(step)
                self.si_d_depth -= 1
                if self.si_d_depth <= 0:
                    self.in_si_d = False

            self.si_depth -= 1
            if self.si_depth <= 0:
                self.in_si = False
            self.body_depth -= 1
            return

        if self.in_figure:
            self.figure_depth -= 1
            if self.figure_depth <= 0:
                self.in_figure = False

        if self.in_p:
            if tag == "a" and self.link_href is not None:
                link_text = "".join(self.link_buf).strip()
                if link_text:
                    self.p_buf.append(f"[{link_text}]({self.link_href})")
                self.link_href = None
                self.link_buf = []
            elif tag in ("em", "i") and self.in_em:
                self.in_em = False
                self.p_buf.append("*")
            elif tag in ("strong", "b") and self.in_strong:
                self.in_strong = False
                self.p_buf.append("**")
            elif tag == "p":
                self.in_p = False
                para = clean_whitespace("".join(self.p_buf))
                # Clean up spacing around markdown emphasis markers
                para = re.sub(r"\*\*\s+\*\*", " ", para)
                if para:
                    self.context_paragraphs.append(para)

        self.body_depth -= 1
        if self.body_depth <= 0:
            self.in_body = False

    def handle_data(self, data: str) -> None:
        if not self.in_body or self.in_aside:
            return
        if self._in_ing_heading:
            self._ing_heading_buf.append(data)
        elif self._in_ing_li:
            self._ing_li_buf.append(data)
        elif self._in_step_div:
            self._step_buf.append(data)
        elif self.in_p:
            if self.link_href is not None:
                self.link_buf.append(data)
            else:
                self.p_buf.append(data)


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


def extract_recipe(url: str, raw_html: str) -> Dict[str, Any]:
    ld_items = extract_json_ld(raw_html)
    recipe_ld = next((x for x in ld_items if has_type(x, "Recipe")), None)
    video_ld = next((x for x in ld_items if has_type(x, "VideoObject")), None)
    article_ld = next(
        (x for x in ld_items if has_type(x, "NewsArticle") or has_type(x, "Article")),
        None,
    )

    body_parser = ElComidistaBodyParser()
    body_parser.feed(raw_html)

    # Title
    title = None
    if recipe_ld and recipe_ld.get("name"):
        title = clean_whitespace(str(recipe_ld["name"]))
    elif article_ld and article_ld.get("headline"):
        title = clean_whitespace(str(article_ld["headline"]))
    else:
        title = extract_meta_tag(raw_html, "og:title")
        if not title:
            m = re.search(r"<title>(.*?)</title>", raw_html, re.S | re.I)
            title = clean_whitespace(m.group(1)) if m else "Receta"

    # Description
    description = None
    if recipe_ld and recipe_ld.get("description"):
        description = clean_whitespace(str(recipe_ld["description"]))
    else:
        description = extract_meta_tag(raw_html, "og:description") or extract_meta_tag(
            raw_html, "description"
        )

    # Author
    author = None
    raw_author = (recipe_ld or {}).get("author") or (article_ld or {}).get("author")
    if isinstance(raw_author, list) and raw_author:
        raw_author = raw_author[0]
    if isinstance(raw_author, dict):
        author = clean_whitespace(str(raw_author.get("name", "")))
    elif isinstance(raw_author, str):
        author = clean_whitespace(raw_author)

    # Date
    date_str = None
    raw_date = (recipe_ld or {}).get("datePublished") or (article_ld or {}).get(
        "datePublished"
    )
    if raw_date and isinstance(raw_date, str):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", raw_date.strip())
        date_str = m.group(1) if m else raw_date.strip()

    # Servings / Yield
    servings = None
    if recipe_ld and recipe_ld.get("recipeYield"):
        ry = recipe_ld["recipeYield"]
        if isinstance(ry, list) and ry:
            ry = ry[0]
        servings = clean_whitespace(str(ry))

    # Times
    prep_time = format_iso_duration((recipe_ld or {}).get("prepTime"))
    cook_time = format_iso_duration((recipe_ld or {}).get("cookTime"))
    total_time = format_iso_duration((recipe_ld or {}).get("totalTime"))

    # Hero / preview image (handles video preview automatically)
    hero_image = None
    if recipe_ld:
        hero_image = pick_image_url(recipe_ld.get("image"))
    if not hero_image and video_ld:
        hero_image = pick_image_url(video_ld.get("thumbnailUrl"))
    if not hero_image:
        hero_image = extract_meta_tag(raw_html, "og:image")

    # Context paragraphs
    context_paragraphs = body_parser.context_paragraphs
    if not context_paragraphs and recipe_ld and recipe_ld.get("text"):
        context_paragraphs = [clean_whitespace(str(recipe_ld["text"]))]

    # Ingredients
    ingredient_sections = body_parser.ingredient_sections
    if not ingredient_sections and recipe_ld and recipe_ld.get("recipeIngredient"):
        items = [
            clean_whitespace(str(i))
            for i in recipe_ld["recipeIngredient"]
            if clean_whitespace(str(i))
        ]
        if items:
            ingredient_sections = [(None, items)]

    # Instructions
    instructions = body_parser.instructions
    if not instructions and recipe_ld and recipe_ld.get("recipeInstructions"):
        instructions = parse_instructions_from_jsonld(recipe_ld["recipeInstructions"])

    # Tags
    tags = ["receta"]
    if "elpais.com" in url or "elcomidista" in url:
        tags.append("el-comidista")

    return {
        "title": title,
        "description": description,
        "url": url,
        "author": author,
        "date": date_str,
        "servings": servings,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "total_time": total_time,
        "hero_image": hero_image,
        "inline_images": body_parser.inline_images,
        "context_paragraphs": context_paragraphs,
        "ingredient_sections": ingredient_sections,
        "instructions": instructions,
        "tags": tags,
    }


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


def download_image(url: str, dest_dir: Path, base_name: str) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
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


def render_markdown(
    recipe: Dict[str, Any],
    hero_img_ref: Optional[str],
    inline_img_refs: List[Tuple[str, str]],
    use_checkboxes: bool = False,
) -> str:
    lines: List[str] = []

    # YAML Frontmatter for Obsidian
    lines.append("---")
    lines.append(f"title: {yaml_escape(recipe['title'])}")
    lines.append(f"source: {yaml_escape(recipe['url'])}")
    if recipe.get("author"):
        lines.append(f"author: {yaml_escape(recipe['author'])}")
    if recipe.get("date"):
        lines.append(f"date: {recipe['date']}")
    if recipe.get("servings"):
        lines.append(f"servings: {yaml_escape(recipe['servings'])}")
    if recipe.get("prep_time"):
        lines.append(f"prep_time: {yaml_escape(recipe['prep_time'])}")
    if recipe.get("cook_time"):
        lines.append(f"cook_time: {yaml_escape(recipe['cook_time'])}")
    if recipe.get("total_time"):
        lines.append(f"total_time: {yaml_escape(recipe['total_time'])}")
    lines.append("tags:")
    for tag in recipe.get("tags", ["receta"]):
        lines.append(f"  - {tag}")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {recipe['title']}")
    lines.append("")

    # Metadata summary line (clean for PDF export)
    meta_parts: List[str] = []
    if recipe.get("author"):
        meta_parts.append(f"**Autor:** {recipe['author']}")
    if recipe.get("date"):
        meta_parts.append(f"**Fecha:** {recipe['date']}")
    if recipe.get("servings"):
        meta_parts.append(f"**Raciones:** {recipe['servings']}")
    if recipe.get("total_time"):
        meta_parts.append(f"**Tiempo total:** {recipe['total_time']}")
    elif recipe.get("prep_time") or recipe.get("cook_time"):
        if recipe.get("prep_time"):
            meta_parts.append(f"**Prep:** {recipe['prep_time']}")
        if recipe.get("cook_time"):
            meta_parts.append(f"**Cocción:** {recipe['cook_time']}")
    meta_parts.append(f"[Receta original]({recipe['url']})")
    lines.append(" · ".join(meta_parts))
    lines.append("")

    # Description / Lead
    if recipe.get("description"):
        lines.append(f"> {recipe['description']}")
        lines.append("")

    # Hero / Preview Image
    if hero_img_ref:
        lines.append(f"![{recipe['title']}]({hero_img_ref})")
        lines.append("")

    # Context
    if recipe.get("context_paragraphs"):
        lines.append("## Contexto")
        lines.append("")
        for para in recipe["context_paragraphs"]:
            lines.append(para)
            lines.append("")

    # Any extra inline images from the article body
    if inline_img_refs:
        for ref, alt in inline_img_refs:
            lines.append(f"![{alt or recipe['title']}]({ref})")
            lines.append("")

    # Ingredients
    if recipe.get("ingredient_sections"):
        lines.append("## Ingredientes")
        lines.append("")
        bullet = "- [ ]" if use_checkboxes else "-"
        for heading, items in recipe["ingredient_sections"]:
            if heading:
                lines.append(f"### {heading}")
                lines.append("")
            for item in items:
                lines.append(f"{bullet} {item}")
            lines.append("")

    # Instructions
    if recipe.get("instructions"):
        lines.append("## Preparación")
        lines.append("")
        for idx, step in enumerate(recipe["instructions"], start=1):
            lines.append(f"{idx}. {step}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def process_url(
    url: str,
    out_dir: Path,
    images_subdir: str,
    download_images: bool,
    use_checkboxes: bool,
    overwrite: bool,
) -> Path:
    print(f"Fetching: {url}")
    raw_bytes = fetch_url(url)
    raw_html = raw_bytes.decode("utf-8", errors="replace")
    recipe = extract_recipe(url, raw_html)

    slug = slugify(recipe["title"])
    md_path = out_dir / f"{slug}.md"
    if md_path.exists() and not overwrite:
        # Avoid silent overwrite if two distinct URLs share a title
        suffix = abs(hash(url)) % 10000
        md_path = out_dir / f"{slug}-{suffix}.md"
        slug = f"{slug}-{suffix}"

    images_dir = out_dir / images_subdir
    hero_ref: Optional[str] = None
    if recipe.get("hero_image"):
        if download_images:
            fname = download_image(recipe["hero_image"], images_dir, slug)
            hero_ref = f"{images_subdir}/{fname}" if fname else recipe["hero_image"]
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
            ref = f"{images_subdir}/{fname}" if fname else img_url
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


def load_urls(args: argparse.Namespace) -> List[str]:
    urls: List[str] = []
    if args.file:
        if args.file == "-":
            lines = sys.stdin.read().splitlines()
        else:
            lines = Path(args.file).read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    urls.extend(args.urls)
    # Deduplicate while preserving order
    seen = set()
    unique: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert recipe URLs into Obsidian-ready Markdown files."
    )
    parser.add_argument("urls", nargs="*", help="One or more recipe URLs.")
    parser.add_argument(
        "-f",
        "--file",
        help="Path to a text file with one URL per line (use '-' for stdin).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="./recipes",
        help="Destination folder for Markdown files (default: ./recipes).",
    )
    parser.add_argument(
        "--images-dir",
        default="images",
        help="Subfolder inside output-dir for downloaded images (default: images).",
    )
    parser.add_argument(
        "--no-download-images",
        action="store_true",
        help="Keep remote image URLs instead of downloading images locally.",
    )
    parser.add_argument(
        "--checkboxes",
        action="store_true",
        help="Render ingredients as Obsidian checkboxes (- [ ]) instead of bullets (-).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Markdown files with the same slug.",
    )
    args = parser.parse_args()

    urls = load_urls(args)
    if not urls:
        parser.print_help()
        return 1

    out_dir = Path(args.output_dir).expanduser().resolve()
    failures = 0
    for url in urls:
        try:
            process_url(
                url=url,
                out_dir=out_dir,
                images_subdir=args.images_dir,
                download_images=not args.no_download_images,
                use_checkboxes=args.checkboxes,
                overwrite=args.overwrite,
            )
        except Exception as exc:
            failures += 1
            print(f"  [error] Failed {url}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

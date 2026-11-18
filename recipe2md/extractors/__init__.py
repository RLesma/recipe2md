"""Recipe extraction orchestrator combining JSON-LD, El Comidista DOM, and HTML fallbacks."""

import re

from ..models import Recipe
from ..utils import clean_whitespace, extract_meta_tag, format_iso_duration
from .elcomidista import ElComidistaBodyParser
from .html_fallback import extract_legacy_html_recipe
from .json_ld import (
    extract_json_ld,
    has_type,
    parse_instructions_from_jsonld,
    pick_image_url,
)
from .plaintext import parse_plain_text_recipe

__all__ = [
    "ElComidistaBodyParser",
    "extract_json_ld",
    "extract_legacy_html_recipe",
    "extract_recipe",
    "has_type",
    "parse_instructions_from_jsonld",
    "parse_plain_text_recipe",
    "pick_image_url",
]


def extract_recipe(url: str, raw_html: str) -> Recipe:
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

    # Legacy El Comidista / generic HTML heading+list & microdata fallback
    if not ingredient_sections and not instructions:
        leg_ctx, leg_ings, leg_inst = extract_legacy_html_recipe(raw_html)
        if leg_ings:
            ingredient_sections = leg_ings
        if leg_inst:
            instructions = leg_inst
        if leg_ctx and (
            not context_paragraphs or len(leg_ctx) < len(context_paragraphs)
        ):
            context_paragraphs = leg_ctx

    tags = ["receta"]
    if "elpais.com" in url or "elcomidista" in url:
        tags.append("el-comidista")

    return Recipe(
        title=title or "Receta",
        description=description,
        url=url,
        author=author,
        date=date_str,
        servings=servings,
        prep_time=prep_time,
        cook_time=cook_time,
        total_time=total_time,
        hero_image=hero_image,
        inline_images=body_parser.inline_images,
        context_paragraphs=context_paragraphs,
        ingredient_sections=ingredient_sections,
        instructions=instructions,
        tags=tags,
    )

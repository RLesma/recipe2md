"""Obsidian-ready Markdown rendering for extracted recipes."""

from typing import List, Optional, Tuple, Union

from .models import Recipe
from .utils import yaml_escape


def render_markdown(
    recipe: Union[Recipe, dict],
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

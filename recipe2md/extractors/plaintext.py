"""Plain-text recipe parser for manual --from-text and --paste modes."""

import re
from typing import List, Optional

from ..models import Recipe
from ..utils import clean_whitespace


def parse_plain_text_recipe(
    raw_text: str, source_url: str = "", title_override: Optional[str] = None
) -> Recipe:
    """Parse pasted plain text (e.g. from a paywalled page) into a Recipe."""
    lines = [clean_whitespace(l) for l in raw_text.splitlines()]
    lines = [l for l in lines if l]
    if not lines:
        raise ValueError("Input text is empty")

    title = title_override or lines[0]
    body_lines = lines if title_override else lines[1:]

    ing_re = re.compile(r"^(?:ingredientes?|ingredients?)\b[:\s]*$", re.I)
    inst_re = re.compile(
        r"^(?:preparaci[oó]n|elaboraci[oó]n|instrucciones|instructions|method|directions)\b[:\s]*$",
        re.I,
    )

    context_paragraphs: List[str] = []
    ingredients: List[str] = []
    instructions: List[str] = []

    mode = "context"
    for line in body_lines:
        if ing_re.match(line):
            mode = "ingredients"
            continue
        if inst_re.match(line):
            mode = "instructions"
            continue
        if mode == "context":
            context_paragraphs.append(line)
        elif mode == "ingredients":
            item = re.sub(r"^[-*•\[\]\s]+", "", line).strip()
            if item:
                ingredients.append(item)
        elif mode == "instructions":
            step = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            if step:
                instructions.append(step)

    if not ingredients and not instructions:
        instructions = body_lines

    return Recipe(
        title=title,
        url=source_url or "manual-input",
        context_paragraphs=context_paragraphs,
        ingredient_sections=[(None, ingredients)] if ingredients else [],
        instructions=instructions,
        tags=["receta"],
    )

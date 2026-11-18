"""Fallback HTML extractor for older El Comidista posts, generic blogs, and microdata."""

import re
from typing import List, Optional, Tuple

from ..utils import strip_tags


def extract_legacy_html_recipe(
    raw_html: str,
) -> Tuple[List[str], List[Tuple[Optional[str], List[str]]], List[str]]:
    """Fallback for older El Comidista posts, generic recipe blogs, and microdata."""
    # 1. Try microdata itemprop="recipeIngredient" / "recipeInstructions"
    micro_ings = [
        strip_tags(m)
        for m in re.findall(
            r'<[^>]+itemprop=["\']?recipeIngredient["\']?[^>]*>(.*?)</(?:li|span|p|div)>',
            raw_html,
            re.S | re.I,
        )
        if strip_tags(m)
    ]
    micro_inst = [
        strip_tags(m)
        for m in re.findall(
            r'<[^>]+itemprop=["\']?recipeInstructions["\']?[^>]*>(.*?)</(?:li|span|p|div|ol)>',
            raw_html,
            re.S | re.I,
        )
        if strip_tags(m)
    ]

    # 2. Scan article body for "Ingredientes" and "Preparación"/"Elaboración"/"Instrucciones"
    body_match = re.search(
        r'<div[^>]+(?:data-dtm-region=["\']?articulo_cuerpo["\']?|class=["\'][^"\']*\ba_c\b[^"\']*["\'])[^>]*>(.*?)(?:<aside\b|</article>)',
        raw_html,
        re.S | re.I,
    )
    scope = body_match.group(1) if body_match else raw_html

    tokens = re.findall(
        r"<(h[2-4]|p|ul|ol)\b[^>]*>(.*?)</\1>",
        scope,
        re.S | re.I,
    )

    context_paras: List[str] = []
    ing_sections: List[Tuple[Optional[str], List[str]]] = []
    instructions: List[str] = []

    mode = "context"
    curr_heading: Optional[str] = None
    curr_items: List[str] = []

    ing_re = re.compile(r"^ingredientes?\b", re.I)
    inst_re = re.compile(
        r"^(?:preparaci[oó]n|elaboraci[oó]n|instrucciones|c[oó]mo\s+hacer)\b", re.I
    )
    stop_re = re.compile(
        r"^(?:comentarios|sobre\s+la\s+firma|contenido\s+relacionado|noticias\s+relacionadas)\b",
        re.I,
    )

    for tag, inner in tokens:
        tag_l = tag.lower()
        txt = strip_tags(inner)
        if not txt:
            continue

        is_bold_p = tag_l == "p" and bool(
            re.match(
                r"^\s*<(?:strong|b)\b[^>]*>.*</(?:strong|b)>\s*$", inner, re.S | re.I
            )
        )
        is_heading_like = tag_l in ("h2", "h3", "h4") or is_bold_p

        if is_heading_like:
            if stop_re.match(txt):
                break
            if ing_re.match(txt):
                mode = "ingredients"
                continue
            if inst_re.match(txt):
                if curr_items:
                    ing_sections.append((curr_heading, curr_items))
                    curr_heading = None
                    curr_items = []
                mode = "instructions"
                continue

        if mode == "context":
            if tag_l == "p":
                context_paras.append(txt)
        elif mode == "ingredients":
            if tag_l == "ul":
                lis = [
                    strip_tags(li)
                    for li in re.findall(r"<li\b[^>]*>(.*?)</li>", inner, re.S | re.I)
                ]
                lis = [x for x in lis if x]
                if lis:
                    ing_sections.append((curr_heading, lis))
                    curr_heading = None
            elif tag_l in ("p", "h3", "h4") and len(txt) < 80:
                curr_heading = txt
        elif mode == "instructions":
            if tag_l == "ol":
                lis = [
                    strip_tags(li)
                    for li in re.findall(r"<li\b[^>]*>(.*?)</li>", inner, re.S | re.I)
                ]
                instructions.extend([x for x in lis if x])
            elif tag_l == "p" and not txt.startswith("*"):
                step = re.sub(r"^\d+[\.\)]\s*", "", txt)
                if step:
                    instructions.append(step)

    if curr_items:
        ing_sections.append((curr_heading, curr_items))

    if not ing_sections and micro_ings:
        ing_sections = [(None, micro_ings)]
    if not instructions and micro_inst:
        instructions = micro_inst

    return (context_paras if body_match else [], ing_sections, instructions)

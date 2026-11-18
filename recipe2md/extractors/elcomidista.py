"""HTML parser for modern El Comidista / El País recipe articles (.si box)."""

import html
import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

from ..utils import clean_whitespace


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

"""Models for recipe representation."""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class Recipe:
    title: str
    url: str
    description: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    servings: Optional[str] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    total_time: Optional[str] = None
    hero_image: Optional[str] = None
    inline_images: List[Tuple[str, str]] = field(default_factory=list)
    context_paragraphs: List[str] = field(default_factory=list)
    ingredient_sections: List[Tuple[Optional[str], List[str]]] = field(default_factory=list)
    instructions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=lambda: ["receta"])

    @property
    def has_content(self) -> bool:
        return bool(self.ingredient_sections or self.instructions)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

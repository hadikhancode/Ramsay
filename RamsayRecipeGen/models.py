from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class RecipeResult:
    title: str
    rating: Optional[float]
    ratings_count: Optional[int]
    image_url: Optional[str]
    image_alt: Optional[str]
    url: str
    cook_time: Optional[str] = None
    ingredients: Optional[str] = None
    dietary_info: Optional[List[str]] = None
from __future__ import annotations

import html
import re
from typing import Iterator, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

import requests

try:
    import cloudscraper
except ImportError:  # pragma: no cover - optional fallback
    cloudscraper = None

from config import BASE_URL, DETAIL_TIMEOUT_SECONDS, HEADERS, RESULTS_PER_PAGE, SEARCH_TIMEOUT_SECONDS
from gemini_validation import validate_recipes_with_gemini_parallel_stream
from models import RecipeResult


def build_search_url(query: str, page: int = 1) -> str:
    params = [f"q={quote_plus(query.strip())}"]
    offset = (page - 1) * RESULTS_PER_PAGE
    if offset > 0:
        params.append(f"offset={offset}")
    return f"{BASE_URL}?{'&'.join(params)}"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_attr(tag_html: str, attribute: str) -> Optional[str]:
    match = re.search(rf'{attribute}=["\']([^"\']+)["\']', tag_html, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1))
    return None


def extract_card_title(card_html: str) -> Optional[str]:
    match = re.search(
        r'<span[^>]*class="[^"]*card__title-text[^"]*"[^>]*>(.*?)</span>',
        card_html,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    return normalize_whitespace(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1))))


def extract_card_rating(card_html: str) -> Optional[float]:
    star_block = re.search(
        r'<div[^>]*class="[^"]*mntl-recipe-star-rating[^"]*"[^>]*>(.*?)</div>',
        card_html,
        re.IGNORECASE | re.DOTALL,
    )
    if not star_block:
        return None

    body = star_block.group(1)
    full_stars = len(re.findall(r'<svg[^>]*class="[^"]*icon-star(?!-half)[^"]*"', body, re.IGNORECASE))
    half_stars = len(re.findall(r'<svg[^>]*class="[^"]*icon-star-half[^"]*"', body, re.IGNORECASE))
    if full_stars == 0 and half_stars == 0:
        return None
    return full_stars + (0.5 * half_stars)


def extract_card_image(card_html: str) -> tuple[Optional[str], Optional[str]]:
    img_match = re.search(r"<img\b([^>]+)>", card_html, re.IGNORECASE | re.DOTALL)
    if not img_match:
        return None, None

    img_tag = img_match.group(0)
    image_url = extract_attr(img_tag, "data-src") or extract_attr(img_tag, "src")
    image_alt = extract_attr(img_tag, "alt")
    return image_url, image_alt


def fetch_recipe_details(
    recipe_url: str,
    session: requests.Session,
    timeout: int = DETAIL_TIMEOUT_SECONDS,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        response = session.get(recipe_url, timeout=timeout)
        response.raise_for_status()
        html_content = response.text

        ingredients = ""
        ingredients_match = re.search(
            r'<ul[^>]*class="[^"]*ingredients[^"]*"[^>]*>(.*?)</ul>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )

        if not ingredients_match:
            ingredients_match = re.search(
                r'<div[^>]*class="[^"]*ingredient[^"]*"[^>]*>(.*?)</div>',
                html_content,
                re.IGNORECASE | re.DOTALL,
            )

        if not ingredients_match:
            ingredients_match = re.search(
                r"[Ii]ngredients.*?<(?:ul|div)[^>]*>(.*?)</(?:ul|div)>",
                html_content,
                re.IGNORECASE | re.DOTALL,
            )

        if ingredients_match:
            items = re.findall(r"<li[^>]*>(.*?)</li>", ingredients_match.group(1), re.IGNORECASE | re.DOTALL)
            if items:
                cleaned_items = [normalize_whitespace(html.unescape(re.sub(r"<[^>]+>", " ", item))) for item in items]
                ingredients = "\n".join(cleaned_items)

        if not ingredients:
            json_ld_match = re.search(r'"recipeIngredient"\s*:\s*\[(.*?)\]', html_content, re.IGNORECASE | re.DOTALL)
            if json_ld_match:
                ingredient_items = re.findall(r'"([^"]*)"', json_ld_match.group(1))
                ingredients = "\n".join(ingredient_items)

        cook_time_match = re.search(
            r"(\d+)\s*(?:hour|hr|h)?\s*(\d+)?\s*(?:minute|min|m)?(?:\s|$)",
            html_content,
            re.IGNORECASE,
        )
        cook_time = None
        if cook_time_match:
            hours = cook_time_match.group(1)
            minutes = cook_time_match.group(2)
            if hours and minutes:
                cook_time = f"{hours}h {minutes}m"
            elif minutes:
                cook_time = f"{minutes}m"
            else:
                cook_time = f"{hours}h"

        directions = ""
        directions_match = re.search(
            r'<section[^>]*class="[^"]*instructions[^"]*"[^>]*>(.*?)</section>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if directions_match:
            steps = re.findall(r"<li[^>]*>(.*?)</li>", directions_match.group(1), re.IGNORECASE | re.DOTALL)
            cleaned_steps = [normalize_whitespace(html.unescape(re.sub(r"<[^>]+>", " ", step))) for step in steps]
            directions = "\n".join([step for step in cleaned_steps if step])

        if not directions:
            instruction_texts = re.findall(r'"text"\s*:\s*"([^"]+)"', html_content, re.IGNORECASE)
            if instruction_texts:
                cleaned_steps = [normalize_whitespace(html.unescape(step)) for step in instruction_texts]
                directions = "\n".join([step for step in cleaned_steps if step])

        return ingredients or None, cook_time, (directions or None)
    except Exception:
        return None, None, None


def get_recipe_context(recipe_url: str, timeout: int = DETAIL_TIMEOUT_SECONDS) -> dict[str, Optional[str]]:
    if cloudscraper is not None:
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    else:
        session = requests.Session()

    session.headers.update(HEADERS)
    ingredients, cook_time, directions = fetch_recipe_details(recipe_url, session, timeout)
    return {
        "ingredients": ingredients,
        "cook_time": cook_time,
        "directions": directions,
    }


def extract_recipe_candidates(page_html: str, base_url: str) -> List[RecipeResult]:
    results: list[RecipeResult] = []
    seen_urls: set[str] = set()

    for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, re.IGNORECASE | re.DOTALL):
        href = html.unescape(match.group(1))
        card_html = match.group(0)

        if "/recipe/" not in href and "-recipe-" not in href:
            continue

        url = urljoin(base_url, href)
        parsed = urlparse(url)
        if not parsed.netloc.endswith("allrecipes.com"):
            continue

        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = extract_card_title(card_html)
        if not title:
            continue

        rating = extract_card_rating(card_html)
        count_match = re.search(
            r'<div[^>]*class="[^"]*rating-count-number[^"]*"[^>]*>\s*(\d[\d,]*)',
            card_html,
            re.IGNORECASE | re.DOTALL,
        )
        count = int(count_match.group(1).replace(",", "")) if count_match else None
        image_url, image_alt = extract_card_image(card_html)

        if title.lower() in {"next", "previous", "home", "search", "save recipe"}:
            continue

        results.append(
            RecipeResult(
                title=title,
                rating=rating,
                ratings_count=count,
                image_url=image_url,
                image_alt=image_alt,
                url=url,
            )
        )

    return results


def search_allrecipes(
    query: str,
    max_results: int = 10,
    timeout: int = SEARCH_TIMEOUT_SECONDS,
    dietary_restrictions: Optional[List[str]] = None,
    cuisines: Optional[List[str]] = None,
    events: Optional[List[str]] = None,
    food_types: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
    excluded_ingredients: Optional[List[str]] = None,
    complexity_level: Optional[str] = None,
) -> List[RecipeResult]:
    return list(
        search_allrecipes_stream(
            query=query,
            max_results=max_results,
            timeout=timeout,
            dietary_restrictions=dietary_restrictions,
            cuisines=cuisines,
            events=events,
            food_types=food_types,
            allergies=allergies,
            excluded_ingredients=excluded_ingredients,
            complexity_level=complexity_level,
        )
    )


def search_allrecipes_stream(
    query: str,
    max_results: int = 10,
    timeout: int = SEARCH_TIMEOUT_SECONDS,
    dietary_restrictions: Optional[List[str]] = None,
    cuisines: Optional[List[str]] = None,
    events: Optional[List[str]] = None,
    food_types: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
    excluded_ingredients: Optional[List[str]] = None,
    complexity_level: Optional[str] = None,
) -> Iterator[RecipeResult]:
    if cloudscraper is not None:
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    else:
        session = requests.Session()

    session.headers.update(HEADERS)

    yielded_count = 0
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    pages = max(1, (max_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)
    needs_validation = bool(
        dietary_restrictions or cuisines or events or food_types or allergies or excluded_ingredients or complexity_level
    )

    for page in range(1, pages + 1):
        remaining_slots = max_results - yielded_count
        if remaining_slots <= 0:
            return

        url = build_search_url(query, page)
        response = session.get(url, timeout=timeout)
        response.raise_for_status()

        candidates = extract_recipe_candidates(response.text, response.url)
        page_validation_payload: list[dict] = []
        page_enriched: dict[int, RecipeResult] = {}

        for item in candidates:
            if len(page_enriched) >= remaining_slots:
                break

            title_key = item.title.lower()
            if item.url in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(item.url)
            seen_titles.add(title_key)

            if needs_validation:
                ingredients, cook_time, directions = fetch_recipe_details(item.url, session, timeout)
                recipe_index = len(page_enriched)
                page_validation_payload.append(
                    {
                        "index": recipe_index,
                        "title": item.title,
                        "ingredients": ingredients or "",
                        "directions": directions or "",
                    }
                )
            else:
                ingredients, cook_time = None, None

            enriched_item = RecipeResult(
                title=item.title,
                rating=item.rating,
                ratings_count=item.ratings_count,
                image_url=item.image_url,
                image_alt=item.image_alt,
                url=item.url,
                cook_time=cook_time,
                ingredients=ingredients,
                dietary_info=None,
            )
            page_enriched[len(page_enriched)] = enriched_item

        if needs_validation and page_validation_payload:
            for idx, result in validate_recipes_with_gemini_parallel_stream(
                recipes=page_validation_payload,
                dietary_restrictions=dietary_restrictions,
                cuisines=cuisines,
                events=events,
                food_types=food_types,
                allergies=allergies,
                excluded_ingredients=excluded_ingredients,
                complexity_level=complexity_level,
            ):
                if yielded_count >= max_results:
                    return

                enriched = page_enriched.get(idx)
                if not enriched:
                    continue

                is_valid, dietary_info = result
                if not is_valid:
                    continue

                yield RecipeResult(
                    title=enriched.title,
                    rating=enriched.rating,
                    ratings_count=enriched.ratings_count,
                    image_url=enriched.image_url,
                    image_alt=enriched.image_alt,
                    url=enriched.url,
                    cook_time=enriched.cook_time,
                    ingredients=enriched.ingredients,
                    dietary_info=dietary_info,
                )
                yielded_count += 1
        else:
            for idx in sorted(page_enriched.keys()):
                if yielded_count >= max_results:
                    return
                yield page_enriched[idx]
                yielded_count += 1

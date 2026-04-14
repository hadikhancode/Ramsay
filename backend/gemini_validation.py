from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from config import (
    GEMINI_LOCATIONS,
    GEMINI_MAX_WORKERS,
    GEMINI_MODEL,
    GOOGLE_CLOUD_CONSOLE_PROJECT_ID,
    GEMINI_REGION_ROTATION_DELAY_SECONDS,
    GEMINI_REGION_ROTATION_MAX_ROUNDS,
)

try:
    from google import genai
except ImportError:
    genai = None

LOG_LOCK = threading.Lock()
CLIENT_LOCK = threading.Lock()
REGION_CURSOR_LOCK = threading.Lock()

_gemini_clients: dict[str, object] = {}
_region_cursor = 0


class GeminiValidationUnavailableError(RuntimeError):
    """Raised when Gemini validation cannot be completed safely."""


def _build_locations() -> list[str]:
    ordered_locations: list[str] = []

    for location in GEMINI_LOCATIONS:
        normalized = (location or '').strip()
        if normalized and normalized not in ordered_locations:
            ordered_locations.append(normalized)

    return ordered_locations


def _locations_for_request() -> list[str]:
    locations = _build_locations()
    if not locations:
        return locations

    global _region_cursor
    with REGION_CURSOR_LOCK:
        start_index = _region_cursor % len(locations)
        _region_cursor += 1

    return locations[start_index:] + locations[:start_index]


def _is_quota_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in (
            '429',
            'resource_exhausted',
            'quota',
            'rate limit',
            'too many requests',
        )
    )


def _get_gemini_client(location: str):
    with CLIENT_LOCK:
        if location in _gemini_clients:
            return _gemini_clients[location]

        client = genai.Client(vertexai=True, project=GOOGLE_CLOUD_CONSOLE_PROJECT_ID, location=location)
        _gemini_clients[location] = client
        return client


def _format_recipe_label(recipe_index: Optional[int], recipe_title: str) -> str:
    label = f'#{recipe_index}' if recipe_index is not None else '#?'
    return f'{label} {recipe_title}'.strip()


def _generate_content_with_failover(prompt: str, recipe_index: Optional[int] = None, recipe_title: str = ''):
    locations = _locations_for_request()
    if not locations:
        raise GeminiValidationUnavailableError('Gemini validation is unavailable (no configured regions).')

    rounds = GEMINI_REGION_ROTATION_MAX_ROUNDS
    unlimited_rounds = rounds <= 0
    if not unlimited_rounds:
        rounds = max(1, rounds)

    delay_seconds = max(0, GEMINI_REGION_ROTATION_DELAY_SECONDS)
    recipe_label = _format_recipe_label(recipe_index, recipe_title)

    round_index = 0
    while unlimited_rounds or round_index < rounds:
        for location in locations:
            try:
                client = _get_gemini_client(location)
                with LOG_LOCK:
                    print(f'[GEMINI][{recipe_label}][{location}] attempt')
                return client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
            except Exception as exc:
                message = str(exc)
                if _is_quota_error(message):
                    print(f'? [GEMINI][{recipe_label}][{location}] quota exhausted; trying next region')
                    continue

                print(f'? [GEMINI][{recipe_label}][{location}] error: {message}')
                raise GeminiValidationUnavailableError(
                    f'Gemini validation failed in {location}: {message}'
                ) from exc

        should_wait = unlimited_rounds or round_index < rounds - 1
        if should_wait and delay_seconds > 0:
            print(f'? [GEMINI][{recipe_label}] all regions exhausted, waiting {delay_seconds}s before retrying')
            time.sleep(delay_seconds)

        round_index += 1

    attempted_regions = ', '.join(locations)
    print(f'? [GEMINI][{recipe_label}] exhausted regions: {attempted_regions}')
    raise GeminiValidationUnavailableError(
        'Gemini quota exhausted across all configured regions '
        f'({attempted_regions}). Please try again shortly.'
    )


def validate_recipe_with_gemini(
    recipe_index: Optional[int],
    recipe_title: str,
    ingredients: Optional[str],
    directions: Optional[str],
    dietary_restrictions: Optional[List[str]],
    allergies: Optional[List[str]],
    excluded_ingredients: Optional[List[str]],
    complexity_level: Optional[str],
    **extra_filters,
) -> tuple[bool, Optional[List[str]]]:
    if not ingredients and not directions:
        return True, None

    if not genai:
        raise GeminiValidationUnavailableError('Gemini validation is unavailable.')

    cuisines = extra_filters.get('cuisines')
    events = extra_filters.get('events')
    food_types = extra_filters.get('food_types')

    if not dietary_restrictions and not cuisines and not events and not food_types and not allergies and not excluded_ingredients and not complexity_level:
        return True, None

    try:
        prompt_lines = [
            f'Title: {recipe_title}',
            'Ingredients (one item per line):',
            ingredients,
            '',
            'Directions:',
            directions or 'No directions provided.',
            '',
            'Check:',
        ]

        if allergies:
            prompt_lines.append(f"1. Must contain NONE of these allergens (critical): {', '.join(allergies)}")
            prompt_lines.extend([
                'Allergen decision policy (strict):',
                '- Return NO only when an allergen in the filter is explicitly present in the ingredient list.',
                '- Do NOT return NO for precautionary text such as "may contain" or "processed in a facility" unless the filter explicitly asks for precautionary-risk blocking.',
                '- Do NOT infer allergens from recipe title, cuisine, or assumptions; use ingredient evidence only.',
                '- Treat peanut and tree nuts as separate allergens.',
                '- If filter includes peanuts but not tree-nuts: almonds, walnuts, cashews, pecans, pistachios, and hazelnuts are SAFE and must not trigger NO.',
                '- If filter includes tree-nuts but not peanuts: peanut ingredients are SAFE for that tree-nuts check.',
                '- Apply this same strict explicit-evidence rule to every allergen in the filter.',
            ])

        if excluded_ingredients:
            prompt_lines.append(f"2. Must contain NONE of these excluded ingredients: {', '.join(excluded_ingredients)}")
            prompt_lines.append('If any excluded ingredient appears directly or as a clear ingredient match, return NO.')

        if dietary_restrictions:
            prompt_lines.append(f"3. Check which dietary restrictions it matches: {', '.join(dietary_restrictions)}")
        else:
            prompt_lines.append('3. No dietary restriction check required.')

        if cuisines:
            prompt_lines.append(
                f"4. Cuisine must match at least one of: {', '.join(cuisines)}. "
                'Use title + ingredients + directions evidence. Return NO when clearly mismatched.'
            )
        else:
            prompt_lines.append('4. No cuisine check required.')

        if events:
            prompt_lines.append(
                f"5. Event suitability must match at least one of: {', '.join(events)}. "
                'Use title + ingredients + directions evidence. Return NO when clearly unsuitable.'
            )
        else:
            prompt_lines.append('5. No event check required.')

        if food_types:
            prompt_lines.append(
                f"6. Food type must match at least one of: {', '.join(food_types)}. "
                'Examples: dessert, meal, baking, cake, snack, drink. Return NO when clearly mismatched.'
            )
        else:
            prompt_lines.append('6. No food type check required.')

        if complexity_level:
            prompt_lines.append(
                f"7. Recipe complexity must be exactly: {complexity_level}. "
                'Classify using the directions (technique count, timing coordination, and required skill). '
                'Return NO if classified complexity does not match exactly.'
            )
        else:
            prompt_lines.append('7. No complexity check required.')

        if dietary_restrictions:
            prompt_lines.extend([
                '',
                'Respond with exactly:',
                'YES or NO',
                'matching: (list of matches or "none")',
            ])
        else:
            prompt_lines.extend([
                '',
                'Respond with exactly:',
                'YES or NO',
                'No explanation.',
            ])

        prompt = '\n'.join(prompt_lines)
        recipe_label = _format_recipe_label(recipe_index, recipe_title)

        with LOG_LOCK:
            print(f'\n[GEMINI][{recipe_label}]')
            print(f'[INGREDIENTS][{recipe_label}] {ingredients}')
            print(f"[FILTERS][{recipe_label}] Allergies: {allergies or 'none'} | Dietary: {dietary_restrictions or 'none'}")
            print(f"[CUISINE][{recipe_label}] {cuisines or 'none'}")
            print(f"[EVENT][{recipe_label}] {events or 'none'}")
            print(f"[FOOD TYPE][{recipe_label}] {food_types or 'none'}")
            print(f"[EXCLUDED][{recipe_label}] {excluded_ingredients or 'none'}")
            print(f"[COMPLEXITY][{recipe_label}] {complexity_level or 'none'}")

        response = _generate_content_with_failover(prompt, recipe_index=recipe_index, recipe_title=recipe_title)

        response_text = (response.text or '').strip().lower()
        lines = response_text.split('\n')

        with LOG_LOCK:
            print(f'[RESULT][{recipe_label}] {response_text[:100]}')

        is_valid = 'yes' in lines[0]

        dietary_info = None
        if dietary_restrictions and len(lines) > 1:
            matching_line = lines[1].lower()
            if 'matching:' in matching_line:
                matching_text = matching_line.split('matching:')[1].strip()
                if matching_text and matching_text != 'none':
                    dietary_info = [item.strip() for item in matching_text.split(',') if item.strip()]

        return is_valid, dietary_info
    except Exception as exc:
        if isinstance(exc, GeminiValidationUnavailableError):
            raise

        message = str(exc)
        recipe_label = _format_recipe_label(recipe_index, recipe_title)
        print(f'? [ERROR][{recipe_label}] {message}')
        if _is_quota_error(message):
            raise GeminiValidationUnavailableError('Gemini validation service is temporarily busy.') from exc
        raise GeminiValidationUnavailableError('Gemini validation failed.') from exc


def validate_recipes_with_gemini_parallel(
    recipes: List[dict],
    dietary_restrictions: Optional[List[str]],
    allergies: Optional[List[str]],
    excluded_ingredients: Optional[List[str]],
    complexity_level: Optional[str],
    max_workers: int = GEMINI_MAX_WORKERS,
) -> dict[int, tuple[bool, Optional[List[str]]]]:
    default_result: dict[int, tuple[bool, Optional[List[str]]]] = {
        recipe['index']: (True, None) for recipe in recipes
    }

    if not recipes:
        return default_result

    if not genai:
        raise GeminiValidationUnavailableError('Gemini validation is unavailable.')

    if not dietary_restrictions and not _ignored_filters.get('cuisines') and not _ignored_filters.get('events') and not _ignored_filters.get('food_types') and not allergies and not excluded_ingredients and not complexity_level:
        return default_result

    worker_count = max(1, min(max_workers, len(recipes)))
    print(f'\n[GEMINI PARALLEL] validating {len(recipes)} recipes with {worker_count} workers')

    results = dict(default_result)
    validation_errors: list[str] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_index = {
            executor.submit(
                validate_recipe_with_gemini,
                recipe.get('index'),
                recipe.get('title') or '',
                recipe.get('ingredients') or '',
                recipe.get('directions') or '',
                dietary_restrictions,
                allergies,
                excluded_ingredients,
                complexity_level,
                **_ignored_filters,
            ): recipe['index']
            for recipe in recipes
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                print(f'? [GEMINI PARALLEL ERROR] index={index} error={exc}')
                validation_errors.append(f'index={index}: {exc}')

    if validation_errors:
        if any(_is_quota_error(err) for err in validation_errors):
            raise GeminiValidationUnavailableError('Gemini validation service is temporarily busy.')
        raise GeminiValidationUnavailableError('Gemini validation failed during parallel checks.')

    return results


def validate_recipes_with_gemini_parallel_stream(
    recipes: List[dict],
    dietary_restrictions: Optional[List[str]],
    allergies: Optional[List[str]],
    excluded_ingredients: Optional[List[str]],
    complexity_level: Optional[str],
    max_workers: int = GEMINI_MAX_WORKERS,
    **_ignored_filters,
):
    if not recipes:
        return

    if not genai:
        raise GeminiValidationUnavailableError('Gemini validation is unavailable.')

    if not dietary_restrictions and not _ignored_filters.get('cuisines') and not _ignored_filters.get('events') and not _ignored_filters.get('food_types') and not allergies and not excluded_ingredients and not complexity_level:
        for recipe in recipes:
            yield recipe['index'], (True, None)
        return

    worker_count = max(1, min(max_workers, len(recipes)))
    print(f'\n[GEMINI PARALLEL STREAM] validating {len(recipes)} recipes with {worker_count} workers')

    validation_errors: list[str] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_index = {
            executor.submit(
                validate_recipe_with_gemini,
                recipe.get('index'),
                recipe.get('title') or '',
                recipe.get('ingredients') or '',
                recipe.get('directions') or '',
                dietary_restrictions,
                allergies,
                excluded_ingredients,
                complexity_level,
                **_ignored_filters,
            ): recipe['index']
            for recipe in recipes
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                yield index, future.result()
            except Exception as exc:
                print(f'? [GEMINI PARALLEL STREAM ERROR] index={index} error={exc}')
                validation_errors.append(f'index={index}: {exc}')

    if validation_errors:
        if any(_is_quota_error(err) for err in validation_errors):
            raise GeminiValidationUnavailableError('Gemini validation service is temporarily busy.')
        raise GeminiValidationUnavailableError('Gemini validation failed during parallel checks.')


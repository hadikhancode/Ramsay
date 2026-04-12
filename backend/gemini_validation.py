from __future__ import annotations

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from config import (
    GEMINI_LOCATIONS,
    GEMINI_MAX_WORKERS,
    GEMINI_MODEL,
    GEMINI_PROJECT_ID,
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

    # Rotate so each request starts with a different region.
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

        client = genai.Client(vertexai=True, project=GEMINI_PROJECT_ID, location=location)
        _gemini_clients[location] = client
        return client


def _generate_content_with_failover(prompt: str):
    locations = _locations_for_request()
    if not locations:
        raise GeminiValidationUnavailableError('Gemini validation is unavailable (no configured regions).')

    rounds = max(1, GEMINI_REGION_ROTATION_MAX_ROUNDS)
    delay_seconds = max(0, GEMINI_REGION_ROTATION_DELAY_SECONDS)

    for round_index in range(rounds):
        for location in locations:
            try:
                client = _get_gemini_client(location)
                return client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
            except Exception as exc:
                message = str(exc)
                if _is_quota_error(message):
                    print(f'[GEMINI] quota exhausted in {location}; trying next region')
                    continue

                raise GeminiValidationUnavailableError(
                    f'Gemini validation failed in {location}: {message}'
                ) from exc

        if round_index < rounds - 1 and delay_seconds > 0:
            print(f'[GEMINI] all regions exhausted, waiting {delay_seconds}s before retrying')
            time.sleep(delay_seconds)

    attempted_regions = ', '.join(locations)
    raise GeminiValidationUnavailableError(
        'Gemini quota exhausted across all configured regions '
        f'({attempted_regions}). Please try again shortly.'
    )


def validate_recipe_with_gemini(
    recipe_title: str,
    ingredients: Optional[str],
    dietary_restrictions: Optional[List[str]],
    allergies: Optional[List[str]],
    excluded_ingredients: Optional[List[str]],
) -> tuple[bool, Optional[List[str]]]:
    if not ingredients:
        return True, None

    if not genai:
        raise GeminiValidationUnavailableError('Gemini validation is unavailable.')

    if not dietary_restrictions and not allergies and not excluded_ingredients:
        return True, None

    try:
        prompt_lines = [
            f'Title: {recipe_title}',
            'Ingredients (one item per line):',
            ingredients,
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

        with LOG_LOCK:
            print(f'\n[GEMINI] {recipe_title}')
            print(f'[INGREDIENTS] {ingredients}')
            print(f"[FILTERS] Allergies: {allergies or 'none'} | Dietary: {dietary_restrictions or 'none'}")
            print(f"[EXCLUDED] {excluded_ingredients or 'none'}")

        response = _generate_content_with_failover(prompt)

        response_text = (response.text or '').strip().lower()
        lines = response_text.split('\n')

        with LOG_LOCK:
            print(f'[RESULT][{recipe_title}] {response_text[:100]}')

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
        print(f'[ERROR] {message}')
        if _is_quota_error(message):
            raise GeminiValidationUnavailableError('Gemini validation service is temporarily busy.') from exc
        raise GeminiValidationUnavailableError('Gemini validation failed.') from exc


def validate_recipes_with_gemini_parallel(
    recipes: List[dict],
    dietary_restrictions: Optional[List[str]],
    allergies: Optional[List[str]],
    excluded_ingredients: Optional[List[str]],
    max_workers: int = GEMINI_MAX_WORKERS,
) -> dict[int, tuple[bool, Optional[List[str]]]]:
    default_result: dict[int, tuple[bool, Optional[List[str]]]] = {
        recipe['index']: (True, None) for recipe in recipes
    }

    if not recipes:
        return default_result

    if not genai:
        raise GeminiValidationUnavailableError('Gemini validation is unavailable.')

    if not dietary_restrictions and not allergies and not excluded_ingredients:
        return default_result

    worker_count = max(1, min(max_workers, len(recipes)))
    print(f'\n[GEMINI PARALLEL] validating {len(recipes)} recipes with {worker_count} workers')

    results = dict(default_result)
    validation_errors: list[str] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_index = {
            executor.submit(
                validate_recipe_with_gemini,
                recipe.get('title') or '',
                recipe.get('ingredients') or '',
                dietary_restrictions,
                allergies,
                excluded_ingredients,
            ): recipe['index']
            for recipe in recipes
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                print(f'[GEMINI PARALLEL ERROR] index={index} error={exc}')
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
    max_workers: int = GEMINI_MAX_WORKERS,
):
    if not recipes:
        return

    if not genai:
        raise GeminiValidationUnavailableError('Gemini validation is unavailable.')

    if not dietary_restrictions and not allergies and not excluded_ingredients:
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
                recipe.get('title') or '',
                recipe.get('ingredients') or '',
                dietary_restrictions,
                allergies,
                excluded_ingredients,
            ): recipe['index']
            for recipe in recipes
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                yield index, future.result()
            except Exception as exc:
                print(f'[GEMINI PARALLEL STREAM ERROR] index={index} error={exc}')
                validation_errors.append(f'index={index}: {exc}')

    if validation_errors:
        if any(_is_quota_error(err) for err in validation_errors):
            raise GeminiValidationUnavailableError('Gemini validation service is temporarily busy.')
        raise GeminiValidationUnavailableError('Gemini validation failed during parallel checks.')

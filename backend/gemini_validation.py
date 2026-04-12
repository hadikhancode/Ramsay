from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from config import GEMINI_LOCATION, GEMINI_MAX_WORKERS, GEMINI_MODEL, GEMINI_PROJECT_ID

try:
    from google import genai
except ImportError:
    genai = None

LOG_LOCK = threading.Lock()


gemini_client = None
if genai:
    try:
        gemini_client = genai.Client(vertexai=True, project=GEMINI_PROJECT_ID, location=GEMINI_LOCATION)
    except Exception:
        gemini_client = None


class GeminiValidationUnavailableError(RuntimeError):
    """Raised when Gemini validation cannot be completed safely."""


def validate_recipe_with_gemini(
    recipe_title: str,
    ingredients: Optional[str],
    dietary_restrictions: Optional[List[str]],
    allergies: Optional[List[str]],
    excluded_ingredients: Optional[List[str]],
) -> tuple[bool, Optional[List[str]]]:
    if not ingredients:
        return True, None

    if not gemini_client:
        raise GeminiValidationUnavailableError("Gemini validation is unavailable.")

    if not dietary_restrictions and not allergies and not excluded_ingredients:
        return True, None

    try:
        prompt_lines = [
            f"Title: {recipe_title}",
            "Ingredients (one item per line):",
            ingredients,
            "",
            "Check:",
        ]

        if allergies:
            prompt_lines.append(f"1. Must contain NONE of these allergens (critical): {', '.join(allergies)}")
            prompt_lines.append(
                "For allergen checks, decide NO if any listed ingredient is the selected allergen "
                "or is a known ingredient that contains that allergen "
                "(example: egg noodles -> eggs, mayonnaise -> eggs). "
                "Use ingredient text plus common ingredient knowledge to determine contains/does not contain."
            )

        if excluded_ingredients:
            prompt_lines.append(f"2. Must contain NONE of these excluded ingredients: {', '.join(excluded_ingredients)}")
            prompt_lines.append("If any excluded ingredient appears directly or as a clear ingredient match, return NO.")

        if dietary_restrictions:
            prompt_lines.append(f"3. Check which dietary restrictions it matches: {', '.join(dietary_restrictions)}")
        else:
            prompt_lines.append("3. No dietary restriction check required.")

        if dietary_restrictions:
            prompt_lines.extend([
                "",
                "Respond with exactly:",
                "YES or NO",
                'matching: (list of matches or "none")',
            ])
        else:
            prompt_lines.extend([
                "",
                "Respond with exactly:",
                "YES or NO",
                "No explanation.",
            ])

        prompt = "\n".join(prompt_lines)

        with LOG_LOCK:
            print(f"\n[GEMINI] {recipe_title}")
            print(f"[INGREDIENTS] {ingredients}")
            print(f"[FILTERS] Allergies: {allergies or 'none'} | Dietary: {dietary_restrictions or 'none'}")
            print(f"[EXCLUDED] {excluded_ingredients or 'none'}")

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        response_text = (response.text or "").strip().lower()
        lines = response_text.split("\n")

        with LOG_LOCK:
            print(f"[RESULT][{recipe_title}] {response_text[:100]}")

        is_valid = "yes" in lines[0]

        dietary_info = None
        if dietary_restrictions and len(lines) > 1:
            matching_line = lines[1].lower()
            if "matching:" in matching_line:
                matching_text = matching_line.split("matching:")[1].strip()
                if matching_text and matching_text != "none":
                    dietary_info = [item.strip() for item in matching_text.split(",") if item.strip()]

        return is_valid, dietary_info
    except Exception as exc:
        message = str(exc)
        print(f"[ERROR] {message}")
        if "429" in message or "RESOURCE_EXHAUSTED" in message:
            raise GeminiValidationUnavailableError("Gemini rate limit hit (429 RESOURCE_EXHAUSTED).") from exc
        raise GeminiValidationUnavailableError("Gemini validation failed.") from exc


def validate_recipes_with_gemini_parallel(
    recipes: List[dict],
    dietary_restrictions: Optional[List[str]],
    allergies: Optional[List[str]],
    excluded_ingredients: Optional[List[str]],
    max_workers: int = GEMINI_MAX_WORKERS,
) -> dict[int, tuple[bool, Optional[List[str]]]]:
    default_result: dict[int, tuple[bool, Optional[List[str]]]] = {
        recipe["index"]: (True, None) for recipe in recipes
    }

    if not recipes:
        return default_result

    if not gemini_client:
        raise GeminiValidationUnavailableError("Gemini validation is unavailable.")

    if not dietary_restrictions and not allergies and not excluded_ingredients:
        return default_result

    worker_count = max(1, min(max_workers, len(recipes)))
    print(f"\n[GEMINI PARALLEL] validating {len(recipes)} recipes with {worker_count} workers")

    results = dict(default_result)
    validation_errors: list[str] = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_index = {
            executor.submit(
                validate_recipe_with_gemini,
                recipe.get("title") or "",
                recipe.get("ingredients") or "",
                dietary_restrictions,
                allergies,
                excluded_ingredients,
            ): recipe["index"]
            for recipe in recipes
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                print(f"[GEMINI PARALLEL ERROR] index={index} error={exc}")
                validation_errors.append(f"index={index}: {exc}")

    if validation_errors:
        if any("429" in err or "RESOURCE_EXHAUSTED" in err for err in validation_errors):
            raise GeminiValidationUnavailableError("Gemini rate limit hit (429 RESOURCE_EXHAUSTED).")
        raise GeminiValidationUnavailableError("Gemini validation failed during parallel checks.")

    return results

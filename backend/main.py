from __future__ import annotations

import json
import logging
import os
import time

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
import requests

from config import APP_PORT, API_MAX_RESULTS_DEFAULT, API_MAX_RESULTS_MAX, API_MAX_RESULTS_MIN, FRONTEND_DIR
from gemini_validation import GeminiValidationUnavailableError
from scraper import get_recipe_context, search_allrecipes, search_allrecipes_stream

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")

QUOTA_RETRY_DELAY_SECONDS = 3
QUOTA_RETRY_ATTEMPTS = 2
FEATHERLESS_CHAT_URL = "https://api.featherless.ai/v1/chat/completions"
FEATHERLESS_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"
RAMSAY_PERSONA = (
    "You are Gordon Ramsay in MasterChef Junior mode. "
    "You are high-energy, encouraging, and use British slang like 'spot on' and 'stunning'. "
    "You never insult the user and always give constructive cooking advice. "
    "Always refer to the user as 'Chef'."
)


def _safe_positive_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _is_quota_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "too many requests",
        )
    )


def _parse_complexity_filter(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"simple", "intermediate", "complex"}:
        return normalized
    return None


def _compact_chat_history(history: object) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []

    cleaned: list[dict[str, str]] = []
    for item in history[-12:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        cleaned.append({"role": role, "content": content})
    return cleaned


@app.get("/")
def index() -> object:
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/api/search")
def api_search() -> object:
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Please enter one or more ingredients."}), 400

    max_results = _safe_positive_int(
        request.args.get("max_results"),
        default=API_MAX_RESULTS_DEFAULT,
        minimum=API_MAX_RESULTS_MIN,
        maximum=API_MAX_RESULTS_MAX,
    )

    dietary_restrictions_str = request.args.get("dietary_restrictions", "").strip()
    dietary_restrictions = None
    if dietary_restrictions_str:
        dietary_restrictions = [r.strip() for r in dietary_restrictions_str.split(",") if r.strip()]

    cuisines_str = request.args.get("cuisines", "").strip()
    cuisines = None
    if cuisines_str:
        cuisines = [c.strip() for c in cuisines_str.split(",") if c.strip()]

    events_str = request.args.get("events", "").strip()
    events = None
    if events_str:
        events = [e.strip() for e in events_str.split(",") if e.strip()]

    food_types_str = request.args.get("food_types", "").strip()
    food_types = None
    if food_types_str:
        food_types = [f.strip() for f in food_types_str.split(",") if f.strip()]

    allergies_str = request.args.get("allergies", "").strip()
    allergies = None
    if allergies_str:
        allergies = [a.strip() for a in allergies_str.split(",") if a.strip()]

    excluded_ingredients_str = request.args.get("excluded_ingredients", "").strip()
    excluded_ingredients = None
    if excluded_ingredients_str:
        excluded_ingredients = [i.strip() for i in excluded_ingredients_str.split(",") if i.strip()]

    complexity_level = _parse_complexity_filter(request.args.get("complexity"))

    try:
        last_gemini_error: GeminiValidationUnavailableError | None = None
        results = None

        for attempt in range(QUOTA_RETRY_ATTEMPTS):
            try:
                results = search_allrecipes(
                    query,
                    max_results=max_results,
                    dietary_restrictions=dietary_restrictions,
                    cuisines=cuisines,
                    events=events,
                    food_types=food_types,
                    allergies=allergies,
                    excluded_ingredients=excluded_ingredients,
                    complexity_level=complexity_level,
                )
                break
            except GeminiValidationUnavailableError as exc:
                last_gemini_error = exc
                if attempt < QUOTA_RETRY_ATTEMPTS - 1 and _is_quota_error(str(exc)):
                    print(f"[GEMINI] quota hit, retrying full request in {QUOTA_RETRY_DELAY_SECONDS}s")
                    time.sleep(QUOTA_RETRY_DELAY_SECONDS)
                    continue
                raise

        if results is None:
            raise last_gemini_error or GeminiValidationUnavailableError("Recipe safety validation is temporarily unavailable.")

        return jsonify(
            {
                "query": query,
                "count": len(results),
                "results": [
                    {
                        "title": item.title,
                        "rating": item.rating,
                        "ratings_count": item.ratings_count,
                        "image_url": item.image_url,
                        "image_alt": item.image_alt,
                        "url": item.url,
                        "cook_time": item.cook_time,
                        "dietary_info": item.dietary_info,
                    }
                    for item in results
                ],
            }
        )
    except GeminiValidationUnavailableError as exc:
        details = str(exc)
        if _is_quota_error(details):
            details = "Validation service is busy right now. Please try again in a few seconds."
        return jsonify(
            {
                "error": "Recipe safety validation is temporarily unavailable.",
                "details": details,
                "code": "GEMINI_VALIDATION_UNAVAILABLE",
            }
        ), 503
    except requests.RequestException as exc:
        return jsonify({"error": "Failed to reach Allrecipes.", "details": str(exc)}), 502
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return jsonify({"error": "Unexpected error.", "details": str(exc)}), 500


@app.get("/api/search/stream")
def api_search_stream() -> object:
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Please enter one or more ingredients."}), 400

    max_results = _safe_positive_int(
        request.args.get("max_results"),
        default=API_MAX_RESULTS_DEFAULT,
        minimum=API_MAX_RESULTS_MIN,
        maximum=API_MAX_RESULTS_MAX,
    )

    dietary_restrictions_str = request.args.get("dietary_restrictions", "").strip()
    dietary_restrictions = None
    if dietary_restrictions_str:
        dietary_restrictions = [r.strip() for r in dietary_restrictions_str.split(",") if r.strip()]

    cuisines_str = request.args.get("cuisines", "").strip()
    cuisines = None
    if cuisines_str:
        cuisines = [c.strip() for c in cuisines_str.split(",") if c.strip()]

    events_str = request.args.get("events", "").strip()
    events = None
    if events_str:
        events = [e.strip() for e in events_str.split(",") if e.strip()]

    food_types_str = request.args.get("food_types", "").strip()
    food_types = None
    if food_types_str:
        food_types = [f.strip() for f in food_types_str.split(",") if f.strip()]

    allergies_str = request.args.get("allergies", "").strip()
    allergies = None
    if allergies_str:
        allergies = [a.strip() for a in allergies_str.split(",") if a.strip()]

    excluded_ingredients_str = request.args.get("excluded_ingredients", "").strip()
    excluded_ingredients = None
    if excluded_ingredients_str:
        excluded_ingredients = [i.strip() for i in excluded_ingredients_str.split(",") if i.strip()]

    complexity_level = _parse_complexity_filter(request.args.get("complexity"))

    @stream_with_context
    def generate() -> object:
        yielded = 0
        yield json.dumps({"type": "start", "query": query}) + "\n"

        for attempt in range(QUOTA_RETRY_ATTEMPTS):
            try:
                for item in search_allrecipes_stream(
                    query,
                    max_results=max_results,
                    dietary_restrictions=dietary_restrictions,
                    cuisines=cuisines,
                    events=events,
                    food_types=food_types,
                    allergies=allergies,
                    excluded_ingredients=excluded_ingredients,
                    complexity_level=complexity_level,
                ):
                    yielded += 1
                    yield json.dumps(
                        {
                            "type": "item",
                            "count": yielded,
                            "item": {
                                "title": item.title,
                                "rating": item.rating,
                                "ratings_count": item.ratings_count,
                                "image_url": item.image_url,
                                "image_alt": item.image_alt,
                                "url": item.url,
                                "cook_time": item.cook_time,
                                "dietary_info": item.dietary_info,
                            },
                        }
                    ) + "\n"

                break
            except GeminiValidationUnavailableError as exc:
                details = str(exc)
                if attempt < QUOTA_RETRY_ATTEMPTS - 1 and _is_quota_error(details):
                    print(f"[GEMINI] quota hit, retrying stream request in {QUOTA_RETRY_DELAY_SECONDS}s")
                    time.sleep(QUOTA_RETRY_DELAY_SECONDS)
                    continue

                if _is_quota_error(details):
                    details = "Validation service is busy right now. Please try again in a few seconds."
                yield json.dumps({"type": "error", "error": details, "code": "GEMINI_VALIDATION_UNAVAILABLE"}) + "\n"
                return
            except requests.RequestException as exc:
                yield json.dumps({"type": "error", "error": f"Failed to reach Allrecipes: {exc}"}) + "\n"
                return
            except Exception as exc:  # pragma: no cover - defensive catch-all
                yield json.dumps({"type": "error", "error": f"Unexpected error: {exc}"}) + "\n"
                return

        yield json.dumps({"type": "done", "query": query, "count": yielded}) + "\n"

    return Response(generate(), mimetype="application/x-ndjson")


@app.get("/api/recipe/context")
def api_recipe_context() -> object:
    recipe_url = request.args.get("url", "").strip()
    if not recipe_url:
        return jsonify({"error": "Recipe URL is required."}), 400

    try:
        context = get_recipe_context(recipe_url)
        return jsonify(
            {
                "url": recipe_url,
                "ingredients": context.get("ingredients"),
                "directions": context.get("directions"),
                "cook_time": context.get("cook_time"),
            }
        )
    except requests.RequestException as exc:
        return jsonify({"error": "Failed to fetch recipe details.", "details": str(exc)}), 502
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return jsonify({"error": "Unexpected error.", "details": str(exc)}), 500


@app.post("/api/chat/recipe")
def api_chat_recipe() -> object:
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    recipe = payload.get("recipe") if isinstance(payload.get("recipe"), dict) else {}
    history = _compact_chat_history(payload.get("history"))

    if not message:
        return jsonify({"error": "Message is required."}), 400

    recipe_title = str(recipe.get("title", "")).strip()
    recipe_url = str(recipe.get("url", "")).strip()
    ingredients = str(recipe.get("ingredients", "") or "").strip() or "Not available"
    directions = str(recipe.get("directions", "") or "").strip() or "Not available"
    cook_time = str(recipe.get("cook_time", "") or "").strip() or "Unknown"

    if not recipe_title:
        return jsonify({"error": "A selected recipe is required before chatting."}), 400

    api_key = os.getenv("FEATHERLESS_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "Chat service is not configured."}), 503

    system_context = (
        f"{RAMSAY_PERSONA}\n"
        "You are answering questions about one selected recipe only.\n"
        f"Recipe Title: {recipe_title}\n"
        f"Recipe URL: {recipe_url or 'N/A'}\n"
        f"Cook Time: {cook_time}\n"
        f"Ingredients:\n{ingredients}\n\n"
        f"Directions:\n{directions}\n"
    )

    messages = [{"role": "system", "content": system_context}] + history + [{"role": "user", "content": message}]

    try:
        response = requests.post(
            FEATHERLESS_CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": FEATHERLESS_MODEL,
                "messages": messages,
                "temperature": 0.7,
            },
            timeout=45,
        )
        response.raise_for_status()
        reply = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not reply:
            reply = "Chef, the kitchen is a bit noisy right now. Ask me again in a moment."
        return jsonify({"reply": reply})
    except requests.RequestException as exc:
        return jsonify({"error": "Failed to reach Ramsay chat service.", "details": str(exc)}), 502
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return jsonify({"error": "Unexpected chat error.", "details": str(exc)}), 500


if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    print(f"Server running at http://127.0.0.1:{APP_PORT}")
    app.run(debug=False, port=APP_PORT)
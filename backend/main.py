from __future__ import annotations

import json
import logging
import time

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
import requests

from config import APP_PORT, API_MAX_RESULTS_DEFAULT, API_MAX_RESULTS_MAX, API_MAX_RESULTS_MIN, FRONTEND_DIR
from gemini_validation import GeminiValidationUnavailableError
from scraper import search_allrecipes, search_allrecipes_stream

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/frontend")

QUOTA_RETRY_DELAY_SECONDS = 3
QUOTA_RETRY_ATTEMPTS = 2


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

    allergies_str = request.args.get("allergies", "").strip()
    allergies = None
    if allergies_str:
        allergies = [a.strip() for a in allergies_str.split(",") if a.strip()]

    excluded_ingredients_str = request.args.get("excluded_ingredients", "").strip()
    excluded_ingredients = None
    if excluded_ingredients_str:
        excluded_ingredients = [i.strip() for i in excluded_ingredients_str.split(",") if i.strip()]

    try:
        last_gemini_error: GeminiValidationUnavailableError | None = None
        results = None

        for attempt in range(QUOTA_RETRY_ATTEMPTS):
            try:
                results = search_allrecipes(
                    query,
                    max_results=max_results,
                    dietary_restrictions=dietary_restrictions,
                    allergies=allergies,
                    excluded_ingredients=excluded_ingredients,
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

    allergies_str = request.args.get("allergies", "").strip()
    allergies = None
    if allergies_str:
        allergies = [a.strip() for a in allergies_str.split(",") if a.strip()]

    excluded_ingredients_str = request.args.get("excluded_ingredients", "").strip()
    excluded_ingredients = None
    if excluded_ingredients_str:
        excluded_ingredients = [i.strip() for i in excluded_ingredients_str.split(",") if i.strip()]

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
                    allergies=allergies,
                    excluded_ingredients=excluded_ingredients,
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


if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    print(f"Server running at http://127.0.0.1:{APP_PORT}")
    app.run(debug=False, port=APP_PORT)
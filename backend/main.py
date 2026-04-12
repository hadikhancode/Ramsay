from __future__ import annotations

import logging

from flask import Flask, jsonify, request, send_from_directory
import requests

from config import API_MAX_RESULTS_DEFAULT, API_MAX_RESULTS_MAX, API_MAX_RESULTS_MIN, FRONTEND_DIR
from gemini_validation import GeminiValidationUnavailableError
from scraper import search_allrecipes

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/frontend")


def _safe_positive_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


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
        results = search_allrecipes(
            query,
            max_results=max_results,
            dietary_restrictions=dietary_restrictions,
            allergies=allergies,
            excluded_ingredients=excluded_ingredients,
        )
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
        return jsonify(
            {
                "error": "Recipe safety validation is temporarily unavailable.",
                "details": str(exc),
                "code": "GEMINI_VALIDATION_UNAVAILABLE",
            }
        ), 503
    except requests.RequestException as exc:
        return jsonify({"error": "Failed to reach Allrecipes.", "details": str(exc)}), 502
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return jsonify({"error": "Unexpected error.", "details": str(exc)}), 500


if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(debug=False)
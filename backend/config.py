from __future__ import annotations

from pathlib import Path

BASE_URL = "https://www.allrecipes.com/search"
RESULTS_PER_PAGE = 24
SEARCH_TIMEOUT_SECONDS = 15
DETAIL_TIMEOUT_SECONDS = 10

API_MAX_RESULTS_DEFAULT = 10
API_MAX_RESULTS_MIN = 1
API_MAX_RESULTS_MAX = 50

GEMINI_PROJECT_ID = "ramsay-493101"
GEMINI_LOCATION = "global"
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
GEMINI_MAX_WORKERS = 6

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

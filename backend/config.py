from __future__ import annotations

from pathlib import Path

BASE_URL = "https://www.allrecipes.com/search"
RESULTS_PER_PAGE = 24
SEARCH_TIMEOUT_SECONDS = 15
DETAIL_TIMEOUT_SECONDS = 10

API_MAX_RESULTS_DEFAULT = 10
API_MAX_RESULTS_MIN = 1
API_MAX_RESULTS_MAX = 50
APP_PORT = 5000

GEMINI_PROJECT_ID = "ramsay-493101"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MAX_WORKERS = 10
GEMINI_LOCATIONS = (
    'us-central1',
    'us-east4',
    'us-east1',
    'us-west1',
    'us-west4',
    'us-south1',
    'us-east5',
    'northamerica-northeast1',
    'southamerica-east1',
    'europe-west1',
    'europe-west4',
    'europe-west2',
    'europe-west3',
    'europe-west9',
    'europe-north1',
    'europe-southwest1',
    'europe-central2',
    'asia-northeast1',
    'asia-northeast3',
    'asia-southeast1',
    'asia-south1',
    'australia-southeast1'
)
GEMINI_REGION_ROTATION_MAX_ROUNDS = 2
GEMINI_REGION_ROTATION_DELAY_SECONDS = 3

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

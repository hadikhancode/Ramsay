from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

load_dotenv(BASE_DIR / ".env")


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return default


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    return parsed or default

BASE_URL = _env_str("BASE_URL", "https://www.allrecipes.com/search")
RESULTS_PER_PAGE = _env_int("RESULTS_PER_PAGE", 24)
SEARCH_TIMEOUT_SECONDS = _env_int("SEARCH_TIMEOUT_SECONDS", 15)
DETAIL_TIMEOUT_SECONDS = _env_int("DETAIL_TIMEOUT_SECONDS", 10)

API_MAX_RESULTS_DEFAULT = _env_int("API_MAX_RESULTS_DEFAULT", 10)
API_MAX_RESULTS_MIN = _env_int("API_MAX_RESULTS_MIN", 1)
API_MAX_RESULTS_MAX = _env_int("API_MAX_RESULTS_MAX", 50)
APP_PORT = _env_int("APP_PORT", 5000)

GOOGLE_CLOUD_CONSOLE_PROJECT_ID = _env_str("GOOGLE_CLOUD_CONSOLE_PROJECT_ID", "your-google-cloud-console-project-id")
GEMINI_MODEL = _env_str("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MAX_WORKERS = _env_int("GEMINI_MAX_WORKERS", 10)
GEMINI_LOCATIONS = _env_csv(
    "GEMINI_LOCATIONS",
    (
        "us-central1",
        "us-east4",
        "us-east1",
        "us-west1",
        "us-west4",
        "us-south1",
        "us-east5",
        "northamerica-northeast1",
        "southamerica-east1",
        "europe-west1",
        "europe-west4",
        "europe-west2",
        "europe-west3",
        "europe-west9",
        "europe-north1",
        "europe-southwest1",
        "europe-central2",
        "asia-northeast1",
        "asia-northeast3",
        "asia-southeast1",
        "asia-south1",
        "australia-southeast1",
    ),
)

# Set to 0 for unlimited rotation rounds.
GEMINI_REGION_ROTATION_MAX_ROUNDS = _env_int("GEMINI_REGION_ROTATION_MAX_ROUNDS", 0)
GEMINI_REGION_ROTATION_DELAY_SECONDS = _env_int("GEMINI_REGION_ROTATION_DELAY_SECONDS", 3)

QUOTA_RETRY_DELAY_SECONDS = _env_int("QUOTA_RETRY_DELAY_SECONDS", 3)
QUOTA_RETRY_ATTEMPTS = _env_int("QUOTA_RETRY_ATTEMPTS", 2)

FEATHERLESS_API_KEY = _env_str("FEATHERLESS_API_KEY", "your-featherless-api-key")
FEATHERLESS_CHAT_URL = _env_str("FEATHERLESS_CHAT_URL", "https://api.featherless.ai/v1/chat/completions")
FEATHERLESS_MODEL = _env_str("FEATHERLESS_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
FEATHERLESS_TIMEOUT_SECONDS = _env_int("FEATHERLESS_TIMEOUT_SECONDS", 45)
FEATHERLESS_TEMPERATURE = _env_float("FEATHERLESS_TEMPERATURE", 0.7)

RAMSAY_PERSONA = _env_str(
    "RAMSAY_PERSONA",
    (
        "You are Gordon Ramsay in MasterChef Junior mode. "
        "You are high-energy, encouraging, and use British slang like 'spot on' and 'stunning'. "
        "You never insult the user and always give constructive cooking advice. "
        "Always refer to the user as 'Chef'."
    ),
)

HEADERS = {
    "User-Agent": _env_str(
        "HTTP_USER_AGENT",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    ),
    "Accept-Language": _env_str("HTTP_ACCEPT_LANGUAGE", "en-US,en;q=0.9"),
}

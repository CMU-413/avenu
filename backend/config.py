import os
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI must be set")

DB_NAME = os.getenv("DB_NAME", "avenu_db")
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_samesite(name: str, default: str) -> str:
    raw = os.getenv(name, default).strip().lower()
    allowed = {
        "lax": "Lax",
        "strict": "Strict",
        "none": "None",
    }
    if raw not in allowed:
        raise RuntimeError(f"{name} must be one of: Lax, Strict, None")
    return allowed[raw]


SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
SESSION_COOKIE_PARTITIONED = _env_bool("SESSION_COOKIE_PARTITIONED", False)
SESSION_COOKIE_SAMESITE = _env_samesite("SESSION_COOKIE_SAMESITE", "Lax")

SCHEDULER_INTERNAL_TOKEN = os.getenv("SCHEDULER_INTERNAL_TOKEN", "").strip()


def parse_frontend_origins() -> tuple[str, ...]:
    raw = os.getenv("FRONTEND_ORIGINS", "")
    values = [item.strip() for item in raw.split(",")]
    return tuple(item for item in values if item)

FRONTEND_ORIGINS = parse_frontend_origins()

client = MongoClient(
    MONGO_URI,
    server_api=ServerApi("1") if MONGO_URI.startswith("mongodb+srv://") else None,
)

db = client[DB_NAME]

users_collection = db["users"]
teams_collection = db["teams"]
mailboxes_collection = db["mailboxes"]
mail_collection = db["mail"]
idempotency_keys_collection = db["idempotency_keys"]
notification_log_collection = db["notification_log"]


def ensure_indexes() -> None:
    users_collection.create_index([("optixId", ASCENDING)], unique=True, name="users_optixid_uq")
    users_collection.create_index([("email", ASCENDING)], unique=True, name="users_email_uq")
    users_collection.create_index([("teamIds", ASCENDING)], name="users_teamids_idx")

    teams_collection.create_index([("optixId", ASCENDING)], unique=True, name="teams_optixid_uq")
    teams_collection.create_index([("name", ASCENDING)], name="teams_name_idx")

    mailboxes_collection.create_index(
        [("type", ASCENDING), ("refId", ASCENDING)],
        unique=True,
        name="mailboxes_type_refid_uq",
    )
    mailboxes_collection.create_index([("refId", ASCENDING)], name="mailboxes_refid_idx")

    mail_collection.create_index([("mailboxId", ASCENDING), ("date", DESCENDING)], name="mail_mailbox_date_idx")

    idempotency_keys_collection.create_index(
        [("key", ASCENDING), ("route", ASCENDING), ("method", ASCENDING)],
        unique=True,
        name="idempotency_key_route_method_uq",
    )
    idempotency_keys_collection.create_index([("expiresAt", ASCENDING)], expireAfterSeconds=0, name="idempotency_expires_ttl")

    notification_log_collection.create_index(
        [("userId", ASCENDING), ("type", ASCENDING), ("weekStart", ASCENDING), ("status", ASCENDING)],
        name="notification_log_user_type_week_status_idx",
    )
    notification_log_collection.create_index(
        [("userId", ASCENDING), ("weekStart", ASCENDING)],
        name="notification_log_user_week_idx",
    )

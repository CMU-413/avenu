import os
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI must be set")

DB_NAME = os.getenv("DB_NAME", "avenu_db")

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

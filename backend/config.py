import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI must be set")

DB_NAME = os.getenv("DB_NAME", "avenu_db")

client = MongoClient(
    MONGO_URI,
    server_api=ServerApi("1") if MONGO_URI.startswith("mongodb+srv://") else None
)

db = client[DB_NAME]

users_collection = db["users"]
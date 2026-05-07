from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
datasets_collection = db["datasets"]
semantic_registry_collection = db["semantic_registry"]
users_collection = db["users"]
history_collection = db["history"]  # ← explicitly defined
dashboards_collection = db["dashboards"]
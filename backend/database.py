"""MongoDB connection for Adion (MongoEngine). The database name comes from MONGO_URI (default: devsquad)."""

import os
import mongoengine as me
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/devsquad')


def init_db(app=None):
    """Connect to MongoDB. Returns the connection, or None (with a warning) if it is unreachable."""
    try:
        connection = me.connect(host=MONGO_URI, alias='default', serverSelectionTimeoutMS=3000)
        print(f"[OK] Connected to MongoDB via MongoEngine: {MONGO_URI}")
        return connection
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] Could not connect to MongoDB at {MONGO_URI}: {e}")
        return None

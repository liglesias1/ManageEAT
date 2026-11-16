"""All runtime configuration of the sales service comes from environment variables."""
import os
from pathlib import Path

HOST = "0.0.0.0"  # listen on every interface, so the service can be reached from outside its container
PORT = int(os.getenv("PORT", "8000"))

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "sales.db"   # SQLite until step 3, when it becomes DATABASE_URL (SQL Server)

# If true, an empty database gets the demo restaurant's data on startup
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"

# Checks the login tokens that personnel signs; it must be the same value in both services. No default:
# app.py refuses to start without it.
TOKEN_SECRET = os.getenv("TOKEN_SECRET")

# Where the personnel service is, and how long to wait for it before showing the page without wages (ADR-6).
# The default is its name in docker-compose; on Azure the pipeline sets its public URL.
PERSONNEL_URL = os.getenv("PERSONNEL_URL", "http://personnel:8000")
PERSONNEL_TIMEOUT_S = float(os.getenv("PERSONNEL_TIMEOUT_S", "5"))
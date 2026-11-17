"""All runtime configuration of the personnel service comes from environment variables."""
import os
from pathlib import Path

HOST = "0.0.0.0"  # listen on every interface, so the service can be reached from outside its container
PORT = int(os.getenv("PORT", "8000"))

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "personnel.db"   # SQLite until step 3, when it becomes DATABASE_URL (SQL Server)

# If true, an empty database gets the demo restaurant and its data on startup
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"

# Signs the login tokens; the sales service checks them with the same value. It has no default on
# purpose: app.py refuses to start without it, so the service can never run with a secret everyone knows.
TOKEN_SECRET = os.getenv("TOKEN_SECRET")

# How long a token is valid. The same number limits how long a removed manager can still use sales, and
# how long logged-in managers keep using sales while personnel is down (ADR-6).
TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES", "15"))

# Where the sales service is, and how long to wait for its covers before using the last ones received (ADR-6).
# The default is its name in docker-compose; on Azure the pipeline sets its public URL.
SALES_URL = os.getenv("SALES_URL", "http://sales:8000")
SALES_TIMEOUT_S = float(os.getenv("SALES_TIMEOUT_S", "5"))
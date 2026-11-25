"""All runtime configuration of the sales service comes from environment variables."""
import os
from pathlib import Path

HOST = "0.0.0.0"  # listen on every interface, so the service can be reached from outside its container
PORT = int(os.getenv("PORT", "8000"))

BASE_DIR = Path(__file__).resolve().parent

# Connection string of sales' own database: mssql://sales_app:<password>@<host>:1433/sales.
# It contains a password, so it has no default: app.py refuses to start without it.
DATABASE_URL = os.getenv("DATABASE_URL")

# How long to keep retrying while the database is not ready (a paused Azure SQL database takes up to
# about a minute to resume).
DB_CONNECT_RETRY_S = float(os.getenv("DB_CONNECT_RETRY_S", "90"))

# If true, an empty database gets the demo restaurant's data on startup
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"

# Checks the login tokens that personnel signs; it must be the same value in both services. No default:
# app.py refuses to start without it.
TOKEN_SECRET = os.getenv("TOKEN_SECRET")

# Where the personnel service is, and how long to wait for it before showing the page without wages (ADR-6).
# The default is its name in docker-compose; on Azure the pipeline sets its public URL.
PERSONNEL_URL = os.getenv("PERSONNEL_URL", "http://personnel:8000")
PERSONNEL_TIMEOUT_S = float(os.getenv("PERSONNEL_TIMEOUT_S", "5"))

# The git commit this copy of the service was built from. The Dockerfile receives it as a build argument
# and sets it as an environment variable, so GET /health can say which version is running.
VERSION = os.getenv("GIT_SHA", "dev")

# The origins (scheme://host[:port]) whose pages may call this service from the browser, separated by
# commas. The default is the UI served by nginx in docker-compose; on Azure the pipeline sets the storage
# static website's address. Never "*": no other site can use a manager's token against the API.
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",")
                if origin.strip()]

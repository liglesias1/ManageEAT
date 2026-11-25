"""Observability: GET /health, one log line per request, and CORS for the UI's origin (A2 §3, §1a).

The same file is in services/personnel and services/sales, as database.py and migrations.py are: each
service is built into its own image from its own folder, so they cannot share a module.

- GET /health answers 200 only if the service can write to and read from its own database, and 503
  otherwise. It never calls the other service, so it reports this service's own state. The pipeline calls
  it after every deploy (§5).
- log_requests writes method, path, status and duration of every request to stdout, where Docker and
  Azure Container Apps collect it.
- CORS lets the browser call the service from the UI's origin only (CORS_ORIGINS). It is done here and not
  in Container Apps, whose ingress CORS refuses the preflight of JSON requests.
"""
import logging
import time
from typing import Literal

from fastapi import APIRouter, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from database import get_connection

request_logger = logging.getLogger("requests")
logger = logging.getLogger(__name__)

# /health must answer quickly: one connection attempt, waiting at most this long for it
HEALTH_LOGIN_TIMEOUT_S = 5

# Writes the single row (creating it if it is missing) and reads it back, in one transaction
WRITE_CHECK = """
    UPDATE health_checks SET checked_at = SYSUTCDATETIME() WHERE id = 1;
    IF @@ROWCOUNT = 0
        INSERT INTO health_checks (id, checked_at) VALUES (1, SYSUTCDATETIME());
"""
READ_CHECK = "SELECT checked_at FROM health_checks WHERE id = 1"


# ---------- Request log ----------

async def log_requests(request, call_next):
    """One line per request: method, path, status and how long it took, e.g. `GET /health 200 12.3ms`.

    Only the path is logged, not the query string. If the route raises an error, the line says 500 and the
    error carries on to FastAPI, which answers 500.
    """
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        request_logger.info("%s %s %d %.1fms", request.method, request.url.path, status, duration_ms)


# ---------- Health ----------

class Health(BaseModel):
    status: Literal["ok", "error"]
    db: Literal["ok", "error"]
    version: str                    # the git commit the image was built from (GIT_SHA), or "dev"


router = APIRouter(tags=["health"])


def database_works():
    """True if the service can write to its own database and read back what it wrote."""
    db = get_connection(retry_s=0, login_timeout=HEALTH_LOGIN_TIMEOUT_S)
    try:
        with db:
            db.execute(WRITE_CHECK)
            row = db.execute(READ_CHECK).fetchone()
        return row is not None
    finally:
        db.close()


@router.get("/health", response_model=Health,
            responses={503: {"model": Health, "description": "The service cannot write to or read from its database"}})
def health(response: Response):
    """200 with db "ok" if the service can use its own database; 503 with db "error" if it cannot."""
    try:
        working = database_works()
    except Exception as error:      # any failure (paused database, wrong login, missing table) means "not healthy"
        logger.warning("Health check failed: %s", error)
        working = False
    response.status_code = 200 if working else 503
    state = "ok" if working else "error"
    return Health(status=state, db=state, version=config.VERSION)


# ---------- Wiring ----------

def install(app):
    """Adds CORS, the request log and /health to the app.

    The middleware added last runs first, so the request log wraps CORS and also logs the preflight
    (OPTIONS) requests that CORS answers by itself.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],     # the login token and JSON bodies
        allow_credentials=False,                              # the token travels in a header, not a cookie
        max_age=600,                                          # the browser may reuse a preflight for 10 minutes
    )
    app.middleware("http")(log_requests)
    app.include_router(router)

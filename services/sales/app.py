"""Entry point of the sales service: orders, menu, inventory, suppliers and profit and loss. Start with: python app.py"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import config
import observability
from database import get_connection
from domain.routes import router as sales_router
from domain.seed import seed_sales_if_empty
from migrations import apply_migrations

# Every log line goes to stdout, where Docker and Azure Container Apps collect it
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# The demo restaurant is created by personnel, which owns the restaurants table. Sales only stores its id,
# so both services must agree on it (ADR-6, ADR-7).
DEMO_RESTAURANT_ID = 1


@asynccontextmanager
async def lifespan(app):
    """Before accepting requests: check the configuration, bring the schema up to date, load the demo data."""
    for name in ("DATABASE_URL", "TOKEN_SECRET"):
        if not getattr(config, name):
            raise RuntimeError(f"{name} is not set: the service cannot start without it")
    db = get_connection()
    try:
        apply_migrations(db)
        if config.SEED_DEMO_DATA:
            seed_sales_if_empty(db, DEMO_RESTAURANT_ID)
    finally:
        db.close()
    yield


app = FastAPI(title="ManageEAT sales", lifespan=lifespan)
app.include_router(sales_router)
observability.install(app)          # CORS for the UI, one log line per request, GET /health


if __name__ == "__main__":
    # access_log=False: observability.log_requests already writes one line per request, with its duration
    uvicorn.run(app, host=config.HOST, port=config.PORT, access_log=False)
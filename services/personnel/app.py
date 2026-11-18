"""Entry point of the personnel service: staff, payroll and restaurant accounts. Start with: python app.py"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import config
from accounts.routes import router as accounts_router
from accounts.seed import seed_demo_restaurant
from database import get_connection
from domain.routes import router as personnel_router
from domain.seed import seed_personnel_if_empty
from migrations import apply_migrations

# Every log line goes to stdout, where Docker and Azure Container Apps collect it
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


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
            # The demo account owns the demo data; restaurants that register later start empty
            demo = seed_demo_restaurant(db)
            seed_personnel_if_empty(db, demo)
    finally:
        db.close()
    yield


app = FastAPI(title="ManageEAT personnel", lifespan=lifespan)
app.include_router(accounts_router)
app.include_router(personnel_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
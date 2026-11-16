"""Entry point of the personnel service: staff, payroll and restaurant accounts. Start with: python app.py"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import config
from accounts.routes import router as accounts_router
from accounts.seed import seed_demo_restaurant
from accounts.tables import ACCOUNTS_SCHEMA
from database import get_connection, init_db
from domain.routes import router as personnel_router
from domain.seed import seed_personnel_if_empty
from domain.tables import PERSONNEL_SCHEMA


@asynccontextmanager
async def lifespan(app):
    if not config.TOKEN_SECRET:
        raise RuntimeError("TOKEN_SECRET is not set: the service cannot sign login tokens without it")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        init_db(conn, [ACCOUNTS_SCHEMA, PERSONNEL_SCHEMA])
        if config.SEED_DEMO_DATA:
            # The demo account owns the demo data; restaurants that register later start empty
            demo = seed_demo_restaurant(conn)
            seed_personnel_if_empty(conn, demo)
    finally:
        conn.close()
    yield


app = FastAPI(title="ManageEAT personnel", lifespan=lifespan)
app.include_router(accounts_router)
app.include_router(personnel_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
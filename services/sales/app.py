"""Entry point of the sales service: orders, menu, inventory, suppliers and profit and loss. Start with: python app.py"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import config
from database import get_connection, init_db
from domain.routes import router as sales_router
from domain.seed import seed_sales_if_empty
from domain.tables import SALES_SCHEMA, WAGES_SNAPSHOT_SCHEMA

# The demo restaurant is created by personnel, which owns the restaurants table. Sales only stores its id,
# so both services must agree on it (ADR-6, ADR-7).
DEMO_RESTAURANT_ID = 1


@asynccontextmanager
async def lifespan(app):
    if not config.TOKEN_SECRET:
        raise RuntimeError("TOKEN_SECRET is not set: the service cannot check login tokens without it")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        init_db(conn, [SALES_SCHEMA, WAGES_SNAPSHOT_SCHEMA])
        if config.SEED_DEMO_DATA:
            seed_sales_if_empty(conn, DEMO_RESTAURANT_ID)
    finally:
        conn.close()
    yield


app = FastAPI(title="ManageEAT sales", lifespan=lifespan)
app.include_router(sales_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
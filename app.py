"""Punto de entrada de la web: el archivo principal que se ejecuta para que arranque la app. Start with: python app.py"""
from contextlib import asynccontextmanager

import uvicorn  # the server that runs the FastAPI application
from fastapi import FastAPI  # the web framework that creates the endpoints and handles requests and responses

import config
from database import get_connection, init_db
from domains.personnel.routes import router as personnel_router  # se renombran porque los dos routers se llaman "router" y chocarían
from domains.sales.routes import router as sales_router
from domains.sales.seed import seed_sales_if_empty
from domains.sales.tables import SALES_SCHEMA
from ingestion.schema import INPUT_SCHEMA
from ingestion.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        init_db(conn, [INPUT_SCHEMA, SALES_SCHEMA])
        if config.SEED_DEMO_DATA:
            seed_if_empty(conn)
            seed_sales_if_empty(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="ManageEAT", lifespan=lifespan)
app.include_router(sales_router)
app.include_router(personnel_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
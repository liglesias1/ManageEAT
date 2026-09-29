""" punto de entrada de la web, el archivo prinicpal que se ejecuta para que arranque la web. """

from contextlib import asynccontextmanager

import uvicorn #the server that runs the FastAPI application
from fastapi import FastAPI #the web framework that allows to create the API endpoints and handle requests and responses.

import config
from domains.personnel.routes import router as personnel_router #les cambia los nombres pq sino chocarían los routers de los dos dominios, pq ambos se llaman router.
from domains.sales.routes import router as sales_router


@asynccontextmanager
async def lifespan(app):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="ManageEAT", lifespan=lifespan)
app.include_router(sales_router)
app.include_router(personnel_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
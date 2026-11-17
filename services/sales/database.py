"""SQLite connection helpers shared by every domain."""

#este archivo se conecta a la base de datos SQLite y crea las tablas.

import sqlite3 #allows to connect to SQLite databases and execute SQL queries.

import config #ruta de la base de datos, que aparece en el archivo config.py


def get_connection(db_path=None): #para abrir la base de datos
    # check_same_thread=False: FastAPI may open the connection in one worker thread and use it in another
    # while serving the same request; each request still has its own connection, never shared.
    conn = sqlite3.connect(db_path or config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["price"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """One connection per request, given to the routes with Depends(get_db) and always closed afterwards.

    Routes receive the connection instead of opening it themselves (dependency injection), so no route
    can forget to close it, and tests could hand them a different database.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db(conn, schemas): #para crear las tablas de la base de datos.
    """Create every table that does not exist yet. `schemas` is a list of SQL scripts."""
    for schema in schemas:
        conn.executescript(schema)
    conn.commit()
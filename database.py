"""SQLite connection helpers shared by every domain."""

#este archivo se conecta a la base de datos SQLite y crea las tablas.

import sqlite3 #allows to connect to SQLite databases and execute SQL queries.

import config #ruta de la base de datos, que aparece en el archivo config.py


def get_connection(db_path=None): #para abrir la base de datos
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["price"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn, schemas): #para crear las tablas de la base de datos.
    """Create every table that does not exist yet. `schemas` is a list of SQL scripts."""
    for schema in schemas:
        conn.executescript(schema)
    conn.commit()
    
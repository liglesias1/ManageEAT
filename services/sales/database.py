"""SQL Server connection helpers: connect with retries, rows that behave like sqlite3.Row, and transactions.

The service reads its connection string from DATABASE_URL, e.g. mssql://sales_app:<password>@sqlserver:1433/sales
(locally) or the Azure SQL server's address (on Azure). The driver is pymssql, which needs no ODBC driver in
the image.

Database wraps the pymssql connection so the repositories keep working as they did with SQLite: rows can be
read as row["price"] or row[0] and turned into dict(row), dates come back as ISO text ('2026-09-01' or
'2026-09-01T13:05:00') and DECIMAL columns as float, so services.py and its tests did not change. What did
change is the SQL itself (T-SQL), and the parameter placeholder, which is %s in pymssql instead of ?.
"""
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import unquote, urlparse

import pymssql

import config

logger = logging.getLogger(__name__)

IntegrityError = pymssql.IntegrityError       # raised when a constraint (CHECK, UNIQUE, FOREIGN KEY) is broken

# SQL Server errors that never go away by waiting, so connecting is not retried:
# 18456 login failed (wrong user or password), 4060 the login cannot open that database
NOT_RETRIED = {18456, 4060}


# ---------- Rows ----------

def _plain(value):
    """DATE/DATETIME2 -> ISO text and DECIMAL -> float: the types the code got from SQLite."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class Row:
    """One result row, readable by column name or position, like sqlite3.Row: row["name"], row[0], dict(row)."""

    def __init__(self, names, values):
        self._names = names
        self._values = tuple(_plain(v) for v in values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._names.index(key)]

    def keys(self):
        return list(self._names)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"Row({dict(zip(self._names, self._values))})"


class Result:
    """What execute() returns: the rows of a query, and the id of an inserted row."""

    def __init__(self, cursor):
        self._cursor = cursor
        self._names = [column[0] for column in cursor.description] if cursor.description else []

    def fetchone(self):
        values = self._cursor.fetchone()
        return Row(self._names, values) if values is not None else None

    def fetchall(self):
        return [Row(self._names, values) for values in self._cursor.fetchall()]

    @property
    def lastrowid(self):
        """The IDENTITY value of the row just inserted."""
        return int(self._cursor.lastrowid)

    @property
    def rowcount(self):
        return self._cursor.rowcount


# ---------- Connection ----------

class Database:
    """A connection to the service's own database.

    `with db:` is a transaction, as with sqlite3: everything inside is committed together at the end, or
    rolled back if anything fails, so a dish is never saved without its recipe.
    """

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=None):
        cursor = self._connection.cursor()
        cursor.execute(sql, tuple(params) if params is not None else None)
        return Result(cursor)

    def executemany(self, sql, rows):
        cursor = self._connection.cursor()
        cursor.executemany(sql, [tuple(row) for row in rows])
        return Result(cursor)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, error_type, error, traceback):
        if error_type is None:
            self.commit()
        else:
            self.rollback()
        return False            # an error inside the block is raised again after the rollback


def parse_url(url):
    """mssql://user:password@host:port/database -> the arguments pymssql.connect() expects."""
    parts = urlparse(url)
    if parts.scheme != "mssql" or not parts.hostname or not parts.path.strip("/"):
        raise ValueError("DATABASE_URL must look like mssql://user:password@host:port/database")
    return {
        "server": parts.hostname,
        "port": parts.port or 1433,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": parts.path.strip("/"),
    }


def error_code(error):
    """The error number inside a pymssql error, or None.

    pymssql wraps it in a tuple with the message: error.args == ((18456, b"Login failed for user ..."),).
    A bare number in args[0] is accepted too.
    """
    first = error.args[0] if error.args else None
    if isinstance(first, tuple) and first and isinstance(first[0], int):
        return first[0]
    return first if isinstance(first, int) else None


def get_connection(url=None, retry_s=None, login_timeout=15):
    """Connects to the database, retrying with growing waits while it is not ready.

    A serverless Azure SQL database pauses when idle and takes up to about a minute to resume; meanwhile
    connections fail (error 40613, or with pymssql a DB-Lib 20002/20003 connection timeout). Locally, SQL
    Server may still be starting. So every failure except a wrong login is retried, waiting 1, 2, 4, 8...
    seconds (at most 15 between tries), for up to `retry_s` seconds in total (DB_CONNECT_RETRY_S by
    default). GET /health passes retry_s=0: one attempt, so it answers 503 at once instead of waiting.
    """
    arguments = parse_url(url or config.DATABASE_URL)
    budget = config.DB_CONNECT_RETRY_S if retry_s is None else retry_s
    deadline = time.monotonic() + budget
    wait = 1
    while True:
        try:
            return Database(pymssql.connect(**arguments, login_timeout=login_timeout, autocommit=False))
        except pymssql.OperationalError as error:
            code = error_code(error)
            if code in NOT_RETRIED or time.monotonic() + wait > deadline:
                raise
            logger.warning("Database not ready (error %s), trying again in %ss", code, wait)
            time.sleep(wait)
            wait = min(wait * 2, 15)


def get_db():
    """One connection per request, given to the routes with Depends(get_db) and always closed afterwards.

    Routes receive the connection instead of opening it themselves (dependency injection), so no route
    can forget to close it, and tests could hand them a different database.
    """
    db = get_connection()
    try:
        yield db
    finally:
        db.close()


# ---------- Inserting many rows ----------

MAX_PARAMETERS = 2000      # SQL Server accepts at most 2100 parameters in one statement


def insert_rows(db, table, columns, rows, keep_ids=False):
    """Inserts many rows with a few multi-row INSERTs instead of one round trip per row.

    One INSERT per row would take minutes for the demo orders on Azure, where each round trip to the
    database costs tens of milliseconds. `keep_ids=True` inserts the given ids into an IDENTITY column
    (SET IDENTITY_INSERT), which the demo data needs because other demo rows refer to those ids.
    """
    rows = [tuple(row) for row in rows]
    if not rows:
        return
    per_statement = min(1000, MAX_PARAMETERS // len(columns))      # 1000 is SQL Server's limit of rows
    column_list = ", ".join(columns)
    one_row = "(" + ", ".join(["%s"] * len(columns)) + ")"
    if keep_ids:
        db.execute(f"SET IDENTITY_INSERT {table} ON")
    try:
        for start in range(0, len(rows), per_statement):
            chunk = rows[start:start + per_statement]
            sql = f"INSERT INTO {table} ({column_list}) VALUES " + ", ".join([one_row] * len(chunk))
            db.execute(sql, [value for row in chunk for value in row])
    finally:
        if keep_ids:
            db.execute(f"SET IDENTITY_INSERT {table} OFF")

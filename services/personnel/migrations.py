"""Versioned migrations: the schema is the result of the numbered SQL files in migrations/, applied in order.

Each file (001_init.sql, 002_..., ...) runs once. When it has run, its name is recorded in the table
schema_migrations, so the next start skips it: a second start applies nothing, and the data already in the
tables stays. A file runs inside one transaction, so a migration that fails changes nothing and the
service does not start. Files that have been applied are never edited; a correction is a new file.

Migrations run at startup, before the service accepts requests. On Azure the service runs at most one
replica (maxReplicas 1), so two copies never apply the same migration at the same time.
"""
import logging
import re

import config

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = config.BASE_DIR / "migrations"
FILE_NAME = re.compile(r"^\d{3}_[a-z0-9_]+\.sql$")        # 001_init.sql, 002_add_due_date.sql
BATCH_SEPARATOR = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)


def migration_files(directory=MIGRATIONS_DIR):
    """The migration files in the order they must run (by their number)."""
    return sorted(path for path in directory.iterdir() if FILE_NAME.match(path.name))


def batches(sql):
    """Splits a migration on lines that only say GO, like SQL Server's own tools do, and drops empty parts."""
    return [batch.strip() for batch in BATCH_SEPARATOR.split(sql) if batch.strip()]


def apply_migrations(db, directory=MIGRATIONS_DIR):
    """Applies every migration not applied yet, in order, and returns the names of the ones it applied."""
    db.execute("""
        IF OBJECT_ID('schema_migrations') IS NULL
            CREATE TABLE schema_migrations (
                version     NVARCHAR(100) NOT NULL PRIMARY KEY,
                applied_at  DATETIME2(0)  NOT NULL DEFAULT SYSUTCDATETIME()
            )
    """)
    db.commit()
    done = {row["version"] for row in db.execute("SELECT version FROM schema_migrations").fetchall()}

    applied = []
    for path in migration_files(directory):
        version = path.stem
        if version in done:
            continue
        logger.info("Applying migration %s", version)
        with db:                                    # one transaction: all of the file, or nothing
            for batch in batches(path.read_text(encoding="utf-8")):
                db.execute(batch)
            db.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        logger.info("Applied migration %s", version)
        applied.append(version)

    if not applied:
        logger.info("No migrations to apply; the schema is up to date (%d applied)", len(done))
    return applied

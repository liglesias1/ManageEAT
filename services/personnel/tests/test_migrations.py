"""The migration runner: files run in order, once each, and a second start applies nothing (§4)."""
from migrations import apply_migrations, batches, migration_files


def test_the_migrations_are_the_numbered_sql_files_in_order():
    names = [path.name for path in migration_files()]
    assert names[0] == "001_init.sql"
    assert names == sorted(names)


def test_a_migration_is_split_on_go_lines():
    assert batches("CREATE TABLE a (x INT);\nGO\n\nCREATE TABLE b (y INT)\n  go  \n") == \
        ["CREATE TABLE a (x INT);", "CREATE TABLE b (y INT)"]


def test_every_migration_is_recorded_once(conn):
    versions = [row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()]
    assert versions == [path.stem for path in migration_files()]


def test_applying_again_changes_nothing_and_keeps_the_data(conn):
    conn.execute("INSERT INTO restaurants (name) VALUES ('Kept')")
    conn.commit()
    assert apply_migrations(conn) == []                       # the test database already has every migration
    assert conn.execute("SELECT name FROM restaurants").fetchone()["name"] == "Kept"

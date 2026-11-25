"""GET /health, the request log and CORS (A2 §3, §1a), through the whole service on the test database."""
import logging

import pymssql

import config
import observability

UI_ORIGIN = "http://localhost:8080"         # the default of CORS_ORIGINS: the UI served by nginx in compose


def preflight(visitor, origin):
    """What the browser asks before a POST with a JSON body and a token, from a page on `origin`."""
    return visitor.options("/auth/login", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })


# ---------- Health ----------

def test_health_is_ok_when_the_service_can_write_and_read_its_database(visitor, conn):
    response = visitor.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "version": config.VERSION}
    assert conn.execute("SELECT COUNT(*) AS n FROM health_checks").fetchone()["n"] == 1    # it really wrote


def test_health_keeps_a_single_row(visitor, conn):
    for _ in range(3):
        assert visitor.get("/health").status_code == 200
    assert conn.execute("SELECT COUNT(*) AS n FROM health_checks").fetchone()["n"] == 1


def test_health_reports_the_version_it_was_built_from(visitor, monkeypatch):
    monkeypatch.setattr(config, "VERSION", "4f2c9e1")
    assert visitor.get("/health").json()["version"] == "4f2c9e1"


def test_health_is_503_when_the_database_cannot_be_reached(visitor, monkeypatch):
    def paused(**arguments):
        raise pymssql.OperationalError(40613, b"Database is not currently available")

    monkeypatch.setattr(observability, "get_connection", paused)
    response = visitor.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error", "version": config.VERSION}


def test_health_does_not_depend_on_sales(visitor, sales):
    sales.mode = "down"
    assert visitor.get("/health").status_code == 200
    assert sales.requests == []                 # health never calls the other service


# ---------- Request log ----------

def test_every_request_is_logged_with_method_path_status_and_duration(visitor, caplog):
    with caplog.at_level(logging.INFO, logger="requests"):
        visitor.get("/health")
        visitor.get("/personnel/payroll")       # no token: 401
    lines = [record.getMessage() for record in caplog.records if record.name == "requests"]
    assert len(lines) == 2
    assert lines[0].startswith("GET /health 200 ") and lines[0].endswith("ms")
    assert lines[1].startswith("GET /personnel/payroll 401 ")


def test_the_query_string_is_not_logged(visitor, caplog):
    with caplog.at_level(logging.INFO, logger="requests"):
        visitor.get("/personnel/labor-cost?start=2026-09-01&end=2026-09-30")
    lines = [record.getMessage() for record in caplog.records if record.name == "requests"]
    assert len(lines) == 1 and "start=" not in lines[0]


# ---------- CORS ----------

def test_the_ui_origin_may_send_json_with_a_token(visitor):
    response = preflight(visitor, UI_ORIGIN)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == UI_ORIGIN
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed and "content-type" in allowed


def test_any_other_origin_is_refused(visitor):
    response = preflight(visitor, "https://evil.example")
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_answers_to_the_ui_carry_the_cors_header(visitor):
    response = visitor.get("/health", headers={"Origin": UI_ORIGIN})
    assert response.headers["access-control-allow-origin"] == UI_ORIGIN

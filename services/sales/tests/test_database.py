"""Connecting with retries (database.get_connection), without a real server: pymssql.connect is replaced."""
import pymssql
import pytest

import database

URL = "mssql://app_login:secret@sqlserver:1433/app_db"     # any valid address: nothing connects to it


class FakeServer:
    """Fails with the given SQL Server error numbers, in order, and then connects."""

    def __init__(self, *errors):
        self.errors = list(errors)
        self.attempts = 0

    def connect(self, **arguments):
        self.attempts += 1
        if self.errors:
            code = self.errors.pop(0)
            raise pymssql.OperationalError((code, b"error message from the server"))   # the shape pymssql uses
        return object()


@pytest.fixture
def waits(monkeypatch):
    """Records the waits instead of sleeping, and moves a fake clock forward by each wait."""
    slept = []
    clock = [1000.0]

    def sleep(seconds):
        slept.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(database.time, "sleep", sleep)
    monkeypatch.setattr(database.time, "monotonic", lambda: clock[0])
    return slept


def use(monkeypatch, server):
    monkeypatch.setattr(database.pymssql, "connect", server.connect)
    return server


@pytest.mark.parametrize("args, code", [
    (((18456, b"Login failed"),), 18456),        # what pymssql raises
    ((40613,), 40613),                           # a bare number
    (("no number",), None),
    ((), None),
])
def test_error_code_reads_the_number_pymssql_puts_in_a_tuple(args, code):
    assert database.error_code(pymssql.OperationalError(*args)) == code


def test_a_paused_database_is_retried_with_growing_waits_until_it_answers(monkeypatch, waits):
    server = use(monkeypatch, FakeServer(40613, 40613, 40613))
    assert isinstance(database.get_connection(URL, retry_s=60), database.Database)
    assert server.attempts == 4
    assert waits == [1, 2, 4]


@pytest.mark.parametrize("code", [18456, 4060])
def test_a_wrong_login_or_database_fails_at_once(monkeypatch, waits, code):
    server = use(monkeypatch, FakeServer(code))
    with pytest.raises(pymssql.OperationalError):
        database.get_connection(URL, retry_s=60)
    assert server.attempts == 1 and waits == []


def test_retrying_stops_when_the_time_is_up(monkeypatch, waits):
    server = use(monkeypatch, FakeServer(*[40613] * 10))
    with pytest.raises(pymssql.OperationalError):
        database.get_connection(URL, retry_s=10)
    assert waits == [1, 2, 4]                    # one more wait of 8 s would end after the 10 s budget
    assert server.attempts == 4


def test_retry_s_zero_means_a_single_attempt(monkeypatch, waits):
    server = use(monkeypatch, FakeServer(40613))
    with pytest.raises(pymssql.OperationalError):
        database.get_connection(URL, retry_s=0)
    assert server.attempts == 1 and waits == []
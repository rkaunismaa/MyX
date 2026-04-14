import pytest
from db.connection import get_connection, get_enabled_targets


def test_get_connection_returns_open_connection(db_conn):
    assert db_conn.is_connected()


def test_get_enabled_targets_returns_list(db_conn):
    targets = get_enabled_targets(db_conn)
    assert isinstance(targets, list)

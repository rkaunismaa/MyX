import pytest
from db.connection import get_connection, get_enabled_targets


def test_get_connection_returns_open_connection(test_config):
    conn = get_connection(test_config)
    assert conn.is_connected()
    conn.close()


def test_get_enabled_targets_returns_list(test_config):
    conn = get_connection(test_config)
    targets = get_enabled_targets(conn)
    assert isinstance(targets, list)
    conn.close()

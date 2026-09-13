"""Opt-in checks for the PostgreSQL and Redis services from deploy compose.

Run with AP2WEB_INTEGRATION_DATABASE_URL and AP2WEB_INTEGRATION_REDIS_URL set.
They intentionally skip in the SQLite-only local suite.
"""
import os

import pytest


PG_URL = os.getenv("AP2WEB_INTEGRATION_DATABASE_URL")
REDIS_URL = os.getenv("AP2WEB_INTEGRATION_REDIS_URL")


@pytest.mark.skipif(not PG_URL, reason="AP2WEB_INTEGRATION_DATABASE_URL not configured")
def test_postgresql_service_is_reachable():
    import psycopg

    with psycopg.connect(PG_URL) as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1


@pytest.mark.skipif(not REDIS_URL, reason="AP2WEB_INTEGRATION_REDIS_URL not configured")
def test_redis_service_is_reachable():
    import redis

    client = redis.Redis.from_url(REDIS_URL)
    try:
        assert client.ping() is True
    finally:
        client.close()

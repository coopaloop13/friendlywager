from app.db import sessionmaker


def test_engine_pings_pooled_connections():
    # Neon suspends idle compute and drops server-side connections; stale pooled
    # connections must be detected before use or the next request 500s.
    assert sessionmaker().kw["bind"].pool._pre_ping

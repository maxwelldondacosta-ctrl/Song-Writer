from songwriter.api.deps import get_db


def test_get_db_yields_connection_and_closes(settings):
    gen = get_db(settings)
    conn = next(gen)
    row = conn.execute("SELECT COUNT(*) AS c FROM genres").fetchone()
    assert row["c"] == 12
    # exhaust the generator → closes the connection
    gen.close()


def test_get_db_uses_settings_db_path(settings):
    gen = get_db(settings)
    conn = next(gen)
    assert conn.execute("SELECT 1").fetchone()[0] == 1
    gen.close()

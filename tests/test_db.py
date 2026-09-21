import sqlite3
from src.db.schema import init_db


def test_init_db_creates_all_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert tables == {"agents", "posts", "interactions", "follows", "events", "evolution_log"}


def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # 두 번 호출해도 오류 없어야 함

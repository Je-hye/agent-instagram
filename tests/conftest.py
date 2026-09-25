import pytest

from src.db.schema import init_db


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path

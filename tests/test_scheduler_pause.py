from src.scheduler import pause_file_path


def test_pause_file_path_derived_from_db_path(tmp_path):
    db_path = str(tmp_path / "simulation.db")
    assert pause_file_path(db_path) == tmp_path / "PAUSED"


def test_pause_file_path_consistent_with_web_app(tmp_path):
    # web app과 scheduler가 동일 경로를 바라보는지 확인
    # app.py: Path(db_path).parent / "PAUSED"
    from pathlib import Path
    db_path = str(tmp_path / "simulation.db")
    scheduler_path = pause_file_path(db_path)
    web_path = Path(db_path).parent / "PAUSED"
    assert scheduler_path == web_path

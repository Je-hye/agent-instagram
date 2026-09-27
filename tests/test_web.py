import subprocess
import sys
import uuid
from pathlib import Path

_REPO_ROOT = str(Path(__file__).parent.parent)
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.agents.factory import create_random_agent
from src.db.repository import AgentRepo, PostRepo
from src.db.schema import init_db
from src.models import Post
from src.web.app import create_app


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return TestClient(create_app(db_path)), db_path


def test_stats_returns_zero_counts(client):
    c, _ = client
    resp = c.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_count"] == 0
    assert data["post_count"] == 0
    assert data["ig_published"] == 0
    assert data["avg_quality"] is None


def test_stats_avg_quality_with_scored_post(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    PostRepo(db_path).save(Post(
        id=str(uuid.uuid4()), agent_id=agent.id, topic="t",
        caption="c", image_path=None, ig_post_id=None,
        quality_score=0.8,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    c = TestClient(create_app(db_path))
    data = c.get("/api/stats").json()
    assert abs(data["avg_quality"] - 0.8) < 0.01


def test_agents_returns_list(client):
    c, _ = client
    resp = c.get("/api/agents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_posts_returns_list(client):
    c, _ = client
    resp = c.get("/api/posts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_posts_limit_param(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    for _ in range(10):
        PostRepo(db_path).save(Post(
            id=str(uuid.uuid4()), agent_id=agent.id, topic="t",
            caption="c", image_path=None, ig_post_id=None,
            quality_score=None,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
    c = TestClient(create_app(db_path))
    assert len(c.get("/api/posts?limit=5").json()) == 5


def test_posts_limit_capped_at_500(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    for _ in range(10):
        PostRepo(db_path).save(Post(
            id=str(uuid.uuid4()), agent_id=agent.id, topic="t",
            caption="c", image_path=None, ig_post_id=None,
            quality_score=None,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
    c = TestClient(create_app(db_path))
    resp = c.get("/api/posts?limit=1000")
    assert resp.status_code == 200
    assert len(resp.json()) == 10


def test_explore_returns_html(client):
    c, _ = client
    resp = c.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "agent-instagram" in resp.text


def test_dashboard_returns_html(client):
    c, _ = client
    resp = c.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "agent-instagram" in resp.text


def test_profile_returns_html(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    from src.agents.factory import create_random_agent
    from src.db.repository import AgentRepo
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    c = TestClient(create_app(db_path))
    resp = c.get(f"/agents/{agent.id}")
    assert resp.status_code == 200
    assert agent.name in resp.text


def test_profile_404_unknown_agent(client):
    c, _ = client
    resp = c.get("/agents/nonexistent-id")
    assert resp.status_code == 404


def test_partial_stats_returns_html(client):
    c, _ = client
    resp = c.get("/partials/stats")
    assert resp.status_code == 200
    assert "통계" in resp.text


def test_partial_agents_returns_html(client):
    c, _ = client
    resp = c.get("/partials/agents")
    assert resp.status_code == 200
    assert "에이전트" in resp.text


def test_partial_posts_returns_html(client):
    c, _ = client
    resp = c.get("/partials/posts")
    assert resp.status_code == 200
    assert "포스트" in resp.text


def test_main_web_help():
    result = subprocess.run(
        [sys.executable, "main.py", "web", "--help"],
        capture_output=True, text=True, check=False,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0
    assert "--port" in result.stdout


def test_main_simulate_help():
    result = subprocess.run(
        [sys.executable, "main.py", "simulate", "--help"],
        capture_output=True, text=True, check=False,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0
    assert "--agents" in result.stdout


# ── 시뮬레이션 pause / resume / status ────────────────────────

def test_simulation_status_default_running(client):
    c, _ = client
    resp = c.get("/api/simulation/status")
    assert resp.status_code == 200
    assert resp.json() == {"status": "running"}


def test_simulation_status_in_stats(client):
    c, _ = client
    data = c.get("/api/stats").json()
    assert data["simulation_status"] == "running"


def test_simulation_pause_creates_file(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    c = TestClient(create_app(db_path))

    resp = c.post("/api/simulation/pause")
    assert resp.status_code == 200
    assert resp.json() == {"status": "paused"}
    assert (tmp_path / "PAUSED").exists()


def test_simulation_pause_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    c = TestClient(create_app(db_path))

    c.post("/api/simulation/pause")
    resp = c.post("/api/simulation/pause")
    assert resp.json() == {"status": "already_paused"}


def test_simulation_resume_deletes_file(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    (tmp_path / "PAUSED").touch()
    c = TestClient(create_app(db_path))

    resp = c.post("/api/simulation/resume")
    assert resp.status_code == 200
    assert resp.json() == {"status": "running"}
    assert not (tmp_path / "PAUSED").exists()


def test_simulation_resume_idempotent(client):
    c, _ = client
    resp = c.post("/api/simulation/resume")
    assert resp.json() == {"status": "already_running"}


def test_simulation_status_reflects_pause_resume(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    c = TestClient(create_app(db_path))

    assert c.get("/api/simulation/status").json() == {"status": "running"}
    c.post("/api/simulation/pause")
    assert c.get("/api/simulation/status").json() == {"status": "paused"}
    c.post("/api/simulation/resume")
    assert c.get("/api/simulation/status").json() == {"status": "running"}

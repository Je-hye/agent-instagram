import sqlite3
from src.db.schema import init_db
from src.agents.factory import create_random_agent
from src.db.repository import AgentRepo, PostRepo, FollowRepo
from src.models import Post
import uuid
from datetime import datetime, timezone


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


def test_agent_repo_save_and_get(tmp_db):
    repo = AgentRepo(tmp_db)
    agent = create_random_agent()
    repo.save(agent)
    retrieved = repo.get(agent.id)
    assert retrieved is not None
    assert retrieved.id == agent.id
    assert retrieved.name == agent.name
    assert retrieved.interests == agent.interests


def test_agent_repo_list_all(tmp_db):
    repo = AgentRepo(tmp_db)
    agents = [create_random_agent() for _ in range(3)]
    for a in agents:
        repo.save(a)
    assert len(repo.list_all()) == 3


def test_follow_repo(tmp_db):
    agent_repo = AgentRepo(tmp_db)
    follow_repo = FollowRepo(tmp_db)
    a, b = create_random_agent(), create_random_agent()
    agent_repo.save(a)
    agent_repo.save(b)
    follow_repo.follow(a.id, b.id)
    assert follow_repo.is_following(a.id, b.id)
    assert b.id in follow_repo.get_following(a.id)
    follow_repo.unfollow(a.id, b.id)
    assert not follow_repo.is_following(a.id, b.id)


def test_post_repo_unscored(tmp_db):
    agent = create_random_agent()
    AgentRepo(tmp_db).save(agent)
    post = Post(
        id=str(uuid.uuid4()), agent_id=agent.id, topic="art",
        caption="hello", image_path=None, ig_post_id=None,
        quality_score=None, created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo = PostRepo(tmp_db)
    repo.save(post)
    assert len(repo.get_unscored()) == 1
    repo.update_quality_score(post.id, 0.85)
    assert repo.get_unscored() == []
    repo.update_ig_post_id(post.id, "ig123")
    fetched = repo.get_by_agent(agent.id)
    assert fetched[0].ig_post_id == "ig123"

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.agents.factory import create_random_agent
from src.db.repository import AgentRepo, PostRepo
from src.db.schema import init_db
from src.models import Post


@pytest.fixture
def db_with_posts(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    posts = [
        Post(
            id=str(uuid.uuid4()), agent_id=agent.id, topic="art",
            caption=f"Post {i} 🤖 AI agent", image_path=f"images/{i}.png",
            ig_post_id=None, quality_score=None,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        for i in range(3)
    ]
    repo = PostRepo(db_path)
    for p in posts:
        repo.save(p)
    return db_path, agent, posts


def test_bridge_tick_scores_unscored_posts(db_with_posts):
    db_path, agent, _posts = db_with_posts
    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.5, "persona_consistency": 0.5, "image_caption_alignment": 0.5}
    )
    from src.instagram.bridge import run_bridge_tick
    run_bridge_tick(db_path, mock_ac, ig_client=None, threshold=0.7)
    fetched = PostRepo(db_path).get_by_agent(agent.id)
    assert all(fp.quality_score is not None for fp in fetched)


def test_bridge_tick_publishes_above_threshold(db_with_posts):
    db_path, _agent, _posts = db_with_posts
    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.9, "persona_consistency": 0.9, "image_caption_alignment": 0.9}
    )
    mock_ig = MagicMock()
    mock_ig.post.return_value = "ig_post_id_123"

    with patch("src.instagram.bridge.CloudinaryUploader") as MockUploader:
        mock_uploader_inst = MagicMock()
        mock_uploader_inst.upload.return_value = "https://example.com/img.png"
        MockUploader.return_value = mock_uploader_inst

        from src.instagram.bridge import run_bridge_tick
        count = run_bridge_tick(db_path, mock_ac, ig_client=mock_ig, threshold=0.7)

    assert count == 3


def test_bridge_tick_skips_below_threshold(db_with_posts):
    db_path, _agent, _posts = db_with_posts
    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.2, "persona_consistency": 0.2, "image_caption_alignment": 0.2}
    )
    mock_ig = MagicMock()
    from src.instagram.bridge import run_bridge_tick
    count = run_bridge_tick(db_path, mock_ac, ig_client=mock_ig, threshold=0.7)
    assert count == 0
    mock_ig.post.assert_not_called()


def test_bridge_tick_appends_ai_agent_marker_if_missing(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    post = Post(
        id=str(uuid.uuid4()), agent_id=agent.id, topic="art",
        caption="No marker here",  # 마커 없는 캡션
        image_path="images/0.png", ig_post_id=None, quality_score=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    PostRepo(db_path).save(post)

    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.9, "persona_consistency": 0.9, "image_caption_alignment": 0.9}
    )
    mock_ig = MagicMock()
    mock_ig.post.return_value = "ig_123"

    with patch("src.instagram.bridge.CloudinaryUploader") as MockUploader:
        MockUploader.return_value.upload.return_value = "https://example.com/img.png"
        from src.instagram.bridge import run_bridge_tick
        run_bridge_tick(db_path, mock_ac, ig_client=mock_ig, threshold=0.7)

    call_args = mock_ig.post.call_args
    assert "🤖 AI agent" in call_args.kwargs["caption"]


def test_bridge_tick_no_ig_client_skips_publish(db_with_posts):
    db_path, agent, _posts = db_with_posts
    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.9, "persona_consistency": 0.9, "image_caption_alignment": 0.9}
    )
    from src.instagram.bridge import run_bridge_tick
    count = run_bridge_tick(db_path, mock_ac, ig_client=None, threshold=0.7)
    assert count == 0
    fetched = PostRepo(db_path).get_by_agent(agent.id)
    assert all(fp.ig_post_id is None for fp in fetched)

from unittest.mock import MagicMock

from src.agents.factory import create_random_agent
from src.content.caption import generate_caption, generate_image_prompt
from src.content.image import generate_image
from src.content.pipeline import create_post


def _mock_anthropic(text: str):
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    client.messages.create.return_value = msg
    return client


def test_generate_caption_returns_string_with_robot_emoji():
    agent = create_random_agent()
    client = _mock_anthropic("오늘 커피 한 잔 🤖")
    result = generate_caption(agent, "음식", client)
    assert isinstance(result, str)
    assert "🤖" in result


def test_generate_image_prompt_returns_string():
    agent = create_random_agent()
    client = _mock_anthropic("A warm minimal photo of coffee")
    result = generate_image_prompt(agent, "오늘 커피 한 잔 🤖", client)
    assert isinstance(result, str) and len(result) > 0


def test_generate_image_saves_file(tmp_path):
    import base64
    mock_client = MagicMock()
    mock_client.images.generate.return_value = MagicMock(
        data=[MagicMock(b64_json=base64.b64encode(b"fakepng").decode())]
    )
    path = generate_image("a photo", str(tmp_path), mock_client)
    assert path.endswith(".png")
    import os
    assert os.path.exists(path)


def test_create_post_saves_to_db(tmp_db, tmp_path):
    import base64

    from src.agents.factory import create_random_agent
    from src.db.repository import AgentRepo, PostRepo
    agent = create_random_agent()
    AgentRepo(tmp_db).save(agent)

    anthropic_client = _mock_anthropic("테스트 캡션 🤖")
    openai_client = MagicMock()
    openai_client.images.generate.return_value = MagicMock(
        data=[MagicMock(b64_json=base64.b64encode(b"fakepng").decode())]
    )
    post = create_post(agent, tmp_db, anthropic_client, openai_client,
                       image_dir=str(tmp_path))

    posts = PostRepo(tmp_db).get_by_agent(agent.id)
    assert len(posts) == 1
    assert posts[0].id == post.id

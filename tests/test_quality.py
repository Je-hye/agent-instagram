import json
from unittest.mock import MagicMock, patch
import pytest
from src.content.quality import generate_quality_score
from src.models import Agent, Personality, Aesthetic, Post


@pytest.fixture
def sample_agent():
    return Agent(
        id="a1", name="Mia", age=24,
        personality=Personality(energy=0.8, valence=0.7, openness=0.9),
        interests={"photography": 0.9, "travel": 0.6},
        aesthetic=Aesthetic(palette="warm", composition="rule_of_thirds"),
        caption_style="poetic",
        post_freq=1.5,
        created_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_post():
    return Post(
        id="p1", agent_id="a1", topic="photography",
        caption="Golden hour whispers through the lens ✨ 🤖 AI agent",
        image_path="images/test.png",
        ig_post_id=None, quality_score=None,
        created_at="2026-01-01T00:00:00Z",
    )


def test_quality_score_returns_float(sample_agent, sample_post):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.8, "persona_consistency": 0.9, "image_caption_alignment": 0.7}
    )
    score = generate_quality_score(sample_post, sample_agent, mock_client)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_quality_score_averages_three_dimensions(sample_agent, sample_post):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.6, "persona_consistency": 0.6, "image_caption_alignment": 0.6}
    )
    score = generate_quality_score(sample_post, sample_agent, mock_client)
    assert abs(score - 0.6) < 0.01


def test_quality_score_handles_malformed_json(sample_agent, sample_post):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content[0].text = "not json at all"
    score = generate_quality_score(sample_post, sample_agent, mock_client)
    assert score == 0.0


def test_quality_score_uses_haiku_model(sample_agent, sample_post):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.5, "persona_consistency": 0.5, "image_caption_alignment": 0.5}
    )
    generate_quality_score(sample_post, sample_agent, mock_client)
    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs.kwargs["model"] == "claude-haiku-4-5-20251001"

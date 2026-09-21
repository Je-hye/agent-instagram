from src.agents.factory import create_random_agent
from src.models import Agent


def test_create_random_agent_returns_agent():
    agent = create_random_agent()
    assert isinstance(agent, Agent)


def test_create_random_agent_age_in_range():
    for _ in range(20):
        agent = create_random_agent()
        assert 18 <= agent.age <= 40


def test_create_random_agent_interests_count():
    for _ in range(20):
        agent = create_random_agent()
        assert 3 <= len(agent.interests) <= 5


def test_create_random_agent_post_freq_in_range():
    for _ in range(20):
        agent = create_random_agent()
        assert 0.3 <= agent.post_freq <= 3.0


def test_create_random_agent_has_unique_id():
    ids = {create_random_agent().id for _ in range(10)}
    assert len(ids) == 10

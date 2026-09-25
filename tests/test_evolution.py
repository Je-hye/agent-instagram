import json
from unittest.mock import MagicMock

from src.agents.evolution import check_evolution, evolve_agent
from src.agents.factory import create_random_agent


def test_check_evolution_false_when_low_influence():
    agent = create_random_agent()
    agent.influence_received = {"other": 1.0}
    assert check_evolution(agent) is False


def test_check_evolution_true_when_high_influence():
    agent = create_random_agent()
    agent.influence_received = {"a": 1.5, "b": 1.5}
    assert check_evolution(agent) is True


def test_evolve_agent_keeps_same_keys(tmp_db):
    from src.db.repository import AgentRepo
    agent = create_random_agent()
    AgentRepo(tmp_db).save(agent)

    new_interests = {k: round(v * 1.1, 2) for k, v in agent.interests.items()}
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(new_interests))]
    )
    evolved = evolve_agent(agent, tmp_db, client)
    assert set(evolved.interests.keys()) == set(agent.interests.keys())


def test_evolve_agent_resets_influence(tmp_db):
    from src.db.repository import AgentRepo
    agent = create_random_agent()
    agent.influence_received = {"x": 2.0}
    AgentRepo(tmp_db).save(agent)

    new_interests = {k: v for k, v in agent.interests.items()}
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(new_interests))]
    )
    evolved = evolve_agent(agent, tmp_db, client)
    assert evolved.influence_received == {}

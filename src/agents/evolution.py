import json
import uuid

import anthropic

from src.db.repository import AgentRepo, EvolutionRepo
from src.models import Agent

_INFLUENCE_THRESHOLD = 3.0
_MAX_DRIFT = 0.20


def check_evolution(agent: Agent) -> bool:
    return sum(agent.influence_received.values()) >= _INFLUENCE_THRESHOLD


def evolve_agent(agent: Agent, db_path: str, client: anthropic.Anthropic) -> Agent:
    agent_repo = AgentRepo(db_path)
    evo_repo = EvolutionRepo(db_path)

    prompt = (
        f"에이전트의 현재 관심사: {json.dumps(agent.interests, ensure_ascii=False)}\n"
        f"최근 영향을 준 에이전트 ID별 누적 영향도: {json.dumps(agent.influence_received)}\n\n"
        f"이 에이전트의 관심사 가중치가 어떻게 변해야 할지 JSON으로만 반환해줘.\n"
        f"규칙:\n"
        f"1. 기존 관심사 키만 사용 (새 키 추가 금지)\n"
        f"2. 각 값은 원래 값의 ±{int(_MAX_DRIFT*100)}% 이내\n"
        f"3. 모든 값은 0.1~1.0 사이\n"
        f"형식: {{\"관심사\": 가중치, ...}}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        new_interests: dict[str, float] = json.loads(response.content[0].text)
        # 드리프트 상한 적용
        for k in agent.interests:
            if k in new_interests:
                original = agent.interests[k]
                clamped = max(original * (1 - _MAX_DRIFT),
                              min(original * (1 + _MAX_DRIFT), new_interests[k]))
                new_interests[k] = round(max(0.1, min(1.0, clamped)), 2)
    except (json.JSONDecodeError, KeyError):
        new_interests = agent.interests  # 파싱 실패 시 원본 유지

    before = {"interests": agent.interests}
    agent.interests = new_interests
    agent.influence_received = {}
    after = {"interests": agent.interests}

    agent_repo.save(agent)
    evo_repo.log(str(uuid.uuid4()), agent.id, before, after, trigger="influence_threshold")
    return agent

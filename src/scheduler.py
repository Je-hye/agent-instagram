import os
import random

import anthropic
import openai
from apscheduler.schedulers.blocking import BlockingScheduler

from src.agents.evolution import check_evolution, evolve_agent
from src.agents.factory import create_random_agent
from src.agents.wake import run_wake_cycle
from src.db.repository import AgentRepo, FollowRepo
from src.db.schema import init_db
from src.instagram.bridge import run_bridge_tick
from src.instagram.client import InstagramClient


def _setup_agents(n: int, db_path: str) -> None:
    repo = AgentRepo(db_path)
    follow_repo = FollowRepo(db_path)
    existing = repo.list_all()
    needed = n - len(existing)
    if needed <= 0:
        return
    new_agents = [create_random_agent() for _ in range(needed)]
    for agent in new_agents:
        repo.save(agent)
    all_agents = repo.list_all()
    for agent in new_agents:
        others = [a for a in all_agents if a.id != agent.id]
        n_follows = min(len(others), random.randint(2, 5))
        for target in random.sample(others, n_follows):
            follow_repo.follow(agent.id, target.id)


def run_simulation(
    n_agents: int = 5,
    db_path: str = "data/simulation.db",
    image_dir: str = "images",
    interval_seconds: int = 300,
) -> None:
    init_db(db_path)
    _setup_agents(n_agents, db_path)

    ac = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    oc = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    ig_user_id = os.environ.get("IG_USER_ID")
    ig_access_token = os.environ.get("IG_ACCESS_TOKEN")
    ig_client = (
        InstagramClient(ig_user_id=ig_user_id, access_token=ig_access_token)
        if ig_user_id and ig_access_token
        else None
    )

    def tick():
        agent_repo = AgentRepo(db_path)
        agents = agent_repo.list_all()
        random.shuffle(agents)
        for agent in agents:
            run_wake_cycle(agent.id, db_path, ac, oc, image_dir)
            fresh = agent_repo.get(agent.id)
            if fresh and check_evolution(fresh):
                evolve_agent(fresh, db_path, ac)

    def bridge_tick():
        n = run_bridge_tick(db_path, ac, ig_client)
        if n:
            print(f"[bridge] Instagram 게시: {n}건")

    scheduler = BlockingScheduler()
    scheduler.add_job(tick, "interval", seconds=interval_seconds, id="tick")
    scheduler.add_job(bridge_tick, "interval", seconds=interval_seconds * 2, id="bridge")
    print(f"시뮬레이션 시작: {n_agents}명 에이전트, {interval_seconds}초 간격")
    tick()
    scheduler.start()

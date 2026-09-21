import pytest
from unittest.mock import MagicMock, patch
from src.agents.wake import should_post
from src.agents.factory import create_random_agent
from src.models import Agent


def test_should_post_none_last_time():
    agent = create_random_agent()
    assert should_post(agent, None) is True


def test_should_post_just_posted_low_freq():
    agent = create_random_agent()
    agent.post_freq = 0.3
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    # 방금 포스팅했으면 확률이 매우 낮아야 함
    results = [should_post(agent, now) for _ in range(100)]
    assert sum(results) < 10  # 100번 중 10번 미만


def test_should_post_long_ago_high_freq():
    agent = create_random_agent()
    agent.post_freq = 3.0
    from datetime import datetime, timezone, timedelta
    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    results = [should_post(agent, old) for _ in range(20)]
    assert all(results)  # 오래됐으면 항상 True

import math
import random
import uuid
from datetime import datetime, timezone

import anthropic
import openai

from src.content.pipeline import create_post
from src.db.repository import (
    AgentRepo, InteractionRepo, FollowRepo, PostRepo
)
from src.events.bus import EventBus
from src.models import Agent
from src.social.feed import get_feed
from src.social.resonance import (
    resonance_score, like_threshold, comment_threshold
)

_UNFOLLOW_THRESHOLD = 0.1
_UNFOLLOW_CHECK_COUNT = 20
_FOLLOW_LIKE_COUNT = 3


def should_post(agent: Agent, last_post_time: str | None) -> bool:
    if last_post_time is None:
        return True
    elapsed_hours = (
        datetime.now(timezone.utc) - datetime.fromisoformat(last_post_time)
    ).total_seconds() / 3600
    rate = agent.post_freq / 24
    prob = 1 - math.exp(-rate * elapsed_hours)
    return random.random() < prob


def _generate_comment(agent: Agent, caption: str, client: anthropic.Anthropic) -> str:
    from src.content.caption import _persona_prompt
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        system=_persona_prompt(agent),
        messages=[{"role": "user", "content": f"이 포스트에 짧은 댓글을 달아줘: {caption}"}],
    )
    return msg.content[0].text


def run_wake_cycle(
    agent_id: str,
    db_path: str,
    anthropic_client: anthropic.Anthropic,
    openai_client: openai.OpenAI,
    image_dir: str = "images",
) -> None:
    agent_repo = AgentRepo(db_path)
    post_repo = PostRepo(db_path)
    follow_repo = FollowRepo(db_path)
    interaction_repo = InteractionRepo(db_path)
    bus = EventBus(db_path)

    agent = agent_repo.get(agent_id)
    if agent is None:
        return

    # 피드 확인 및 반응
    feed = get_feed(agent_id, follow_repo, post_repo)
    like_posts: dict[str, int] = {}

    for post in feed:
        if post.agent_id == agent_id:
            continue
        poster = agent_repo.get(post.agent_id)
        if poster is None:
            continue

        score = resonance_score(agent, poster)

        if score > like_threshold(agent) and not interaction_repo.has_liked(agent_id, post.id):
            interaction_repo.save(str(uuid.uuid4()), agent_id, post.id, "like", None, score)
            bus.publish("LikeAdded", {"from_agent_id": agent_id, "to_post_id": post.id})
            agent_repo.update_influence(post.agent_id, agent_id, 0.1)
            like_posts[post.agent_id] = like_posts.get(post.agent_id, 0) + 1

        if score > comment_threshold(agent):
            comment = _generate_comment(agent, post.caption, anthropic_client)
            interaction_repo.save(str(uuid.uuid4()), agent_id, post.id, "comment", comment, score)
            bus.publish("CommentAdded", {"from_agent_id": agent_id, "to_post_id": post.id, "content": comment})
            agent_repo.update_influence(post.agent_id, agent_id, 0.1)

    # 팔로우 성장: 많이 좋아요한 에이전트 팔로우
    for poster_id, count in like_posts.items():
        if count >= _FOLLOW_LIKE_COUNT and not follow_repo.is_following(agent_id, poster_id):
            follow_repo.follow(agent_id, poster_id)
            bus.publish("FollowAdded", {"follower_id": agent_id, "following_id": poster_id})

    # 언팔로우 체크
    for following_id in follow_repo.get_following(agent_id):
        scores = interaction_repo.get_recent_resonances(agent_id, following_id, _UNFOLLOW_CHECK_COUNT)
        if len(scores) >= _UNFOLLOW_CHECK_COUNT and (sum(scores) / len(scores)) < _UNFOLLOW_THRESHOLD:
            follow_repo.unfollow(agent_id, following_id)

    # 포스팅 결정
    last_time = post_repo.get_last_post_time(agent_id)
    if should_post(agent, last_time):
        create_post(agent, db_path, anthropic_client, openai_client, image_dir)

import random
import uuid
from datetime import datetime, timezone

import anthropic
import openai

from src.content.caption import generate_caption, generate_image_prompt
from src.content.image import generate_image
from src.db.repository import PostRepo
from src.events.bus import EventBus
from src.models import Agent, Post


def pick_topic(agent: Agent) -> str:
    topics = list(agent.interests.keys())
    weights = list(agent.interests.values())
    return random.choices(topics, weights=weights, k=1)[0]


def create_post(
    agent: Agent,
    db_path: str,
    anthropic_client: anthropic.Anthropic,
    openai_client: openai.OpenAI,
    image_dir: str = "images",
) -> Post:
    topic = pick_topic(agent)
    caption = generate_caption(agent, topic, anthropic_client)
    img_prompt = generate_image_prompt(agent, caption, anthropic_client)
    image_path = generate_image(img_prompt, image_dir, openai_client)

    post = Post(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        topic=topic,
        caption=caption,
        image_path=image_path,
        ig_post_id=None,
        quality_score=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    PostRepo(db_path).save(post)
    EventBus(db_path).publish("PostCreated", {"post_id": post.id, "agent_id": agent.id})
    return post

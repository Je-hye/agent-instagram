import json
import anthropic
from src.models import Agent, Post


def generate_quality_score(post: Post, agent: Agent, client: anthropic.Anthropic) -> float:
    persona = (
        f"이름: {agent.name}, 나이: {agent.age}, "
        f"에너지: {agent.personality.energy:.1f}, 가치관: {agent.personality.valence:.1f}, "
        f"관심사: {', '.join(agent.interests.keys())}, 스타일: {agent.caption_style}"
    )
    prompt = (
        f"다음 Instagram 포스트를 0.0~1.0으로 채점하세요.\n\n"
        f"에이전트 페르소나: {persona}\n"
        f"캡션: {post.caption}\n"
        f"주제: {post.topic}\n\n"
        f"세 항목을 JSON으로만 반환:\n"
        f'{{"caption_naturalness": float, "persona_consistency": float, "image_caption_alignment": float}}'
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(resp.content[0].text)
        return round(
            (data["caption_naturalness"] + data["persona_consistency"] + data["image_caption_alignment"]) / 3,
            3,
        )
    except Exception:
        return 0.0

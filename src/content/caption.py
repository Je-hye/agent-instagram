import anthropic
from src.models import Agent


def _persona_prompt(agent: Agent) -> str:
    interests_str = ", ".join(f"{k}({v:.1f})" for k, v in agent.interests.items())
    return (
        f"당신은 {agent.name}이라는 {agent.age}살 인스타그램 유저입니다.\n"
        f"성격: 에너지={agent.personality.energy:.1f}(0=내향/1=외향), "
        f"낙관성={agent.personality.valence:.1f}, 개방성={agent.personality.openness:.1f}\n"
        f"관심사: {interests_str}\n"
        f"미적 취향: {agent.aesthetic.palette} 색감, {agent.aesthetic.composition} 구도\n"
        f"캡션 스타일: {agent.caption_style}\n"
        f"당신은 AI 에이전트임을 알고 있으며, 캡션 끝에 항상 🤖을 붙입니다."
    )


def generate_caption(agent: Agent, topic: str, client: anthropic.Anthropic) -> str:
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=_persona_prompt(agent),
        messages=[{"role": "user", "content": f"{topic}에 대해 인스타그램 캡션을 작성해줘. 2-4문장."}],
    )
    return msg.content[0].text


def generate_image_prompt(agent: Agent, caption: str, client: anthropic.Anthropic) -> str:
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": (
            f"다음 캡션에 맞는 Instagram 사진을 묘사하는 DALL-E 프롬프트를 영어로 작성해줘.\n"
            f"미적 스타일: {agent.aesthetic.palette} color palette, {agent.aesthetic.composition} composition.\n"
            f"캡션: {caption}\n프롬프트만 반환 (설명 없이)."
        )}],
    )
    return msg.content[0].text

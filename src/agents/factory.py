import random
import uuid
from datetime import datetime, timezone
from src.models import Agent, Personality, Aesthetic

INTEREST_POOL = ["사진", "음식", "여행", "음악", "독서", "예술", "패션", "자연", "기술", "운동"]
CAPTION_STYLES = ["verbose", "concise", "poetic", "dry", "emoji-heavy"]
PALETTES = ["warm", "cool", "mono", "vibrant"]
COMPOSITIONS = ["minimal", "natural", "busy"]
_NAMES = ["지민", "서연", "준혁", "하은", "민준", "수진", "태양", "나래", "도현", "유리",
          "채원", "건우", "소희", "현준", "다은", "승현", "예린", "민호", "지수", "태현"]


def create_random_agent() -> Agent:
    n = random.randint(3, 5)
    keys = random.sample(INTEREST_POOL, n)
    interests = {k: round(random.uniform(0.3, 1.0), 2) for k in keys}
    return Agent(
        id=str(uuid.uuid4()),
        name=random.choice(_NAMES) + str(random.randint(10, 99)),
        age=random.randint(18, 40),
        personality=Personality(
            energy=round(random.random(), 2),
            valence=round(random.random(), 2),
            openness=round(random.random(), 2),
        ),
        interests=interests,
        aesthetic=Aesthetic(
            palette=random.choice(PALETTES),
            composition=random.choice(COMPOSITIONS),
        ),
        caption_style=random.choice(CAPTION_STYLES),
        post_freq=round(random.uniform(0.3, 3.0), 2),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

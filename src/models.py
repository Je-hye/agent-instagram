from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Personality:
    energy: float    # 0=내향, 1=외향
    valence: float   # 0=비관적, 1=낙관적
    openness: float  # 0=루틴형, 1=호기심형


@dataclass
class Aesthetic:
    palette: Literal["warm", "cool", "mono", "vibrant"]
    composition: Literal["minimal", "natural", "busy"]


@dataclass
class Agent:
    id: str
    name: str
    age: int
    personality: Personality
    interests: dict[str, float]
    aesthetic: Aesthetic
    caption_style: Literal["verbose", "concise", "poetic", "dry", "emoji-heavy"]
    post_freq: float
    influence_received: dict[str, float] = field(default_factory=dict)
    created_at: str = ""
    evolved_at: str | None = None


@dataclass
class Post:
    id: str
    agent_id: str
    topic: str
    caption: str
    image_path: str | None
    ig_post_id: str | None
    quality_score: float | None
    created_at: str

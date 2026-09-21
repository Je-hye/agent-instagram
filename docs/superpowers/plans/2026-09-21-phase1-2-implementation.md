# Natural Agent Instagram Phase 1-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 랜덤 생성된 에이전트들이 콘텐츠를 생성하고, 서로 반응하며, 상호작용을 통해 성격이 진화하는 로컬 시뮬레이션을 구축한다.

**Architecture:** SQLite 기반 EventBus를 중심으로 에이전트들이 독립적으로 wake cycle을 수행한다. Scheduler가 주기적으로 에이전트를 깨우고, 에이전트는 피드를 확인해 반응 여부를 결정하거나 새 포스트를 생성한다.

**Tech Stack:** Python 3.11+, anthropic SDK, openai SDK, APScheduler, SQLite, pytest

**Spec:** `docs/superpowers/specs/2026-09-21-natural-agent-instagram-design.md`

## Global Constraints

- Python 3.11+
- anthropic SDK: `claude-haiku-4-5-20251001` (캡션/프롬프트), `claude-sonnet-4-6` (진화)
- openai SDK: DALL-E 3 standard, 1024×1024
- DB: SQLite, 파일 경로 `data/simulation.db`
- 이미지 저장: `images/` 디렉터리
- 환경변수: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (`.env` 파일)
- 모든 타임스탬프: UTC ISO 8601 문자열
- 에이전트 캡션 끝에 항상 `🤖` 포함
- pytest로 모든 테스트 실행

---

## File Structure

```
agent-instagram/
├── src/
│   ├── __init__.py
│   ├── models.py           # Agent, Personality, Aesthetic, Post 데이터클래스
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.py       # CREATE TABLE 문 + init_db()
│   │   └── repository.py   # CRUD: AgentRepo, PostRepo, InteractionRepo, FollowRepo, EvolutionRepo
│   ├── events/
│   │   ├── __init__.py
│   │   └── bus.py          # EventBus (publish / consume)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── factory.py      # create_random_agent()
│   │   ├── wake.py         # Agent wake cycle (should_post, pick_topic, decide_interactions)
│   │   └── evolution.py    # check_evolution(), evolve_agent()
│   ├── content/
│   │   ├── __init__.py
│   │   ├── caption.py      # generate_caption(), generate_image_prompt()
│   │   ├── image.py        # generate_image()
│   │   └── pipeline.py     # create_post() — 전체 파이프라인 오케스트레이터
│   ├── social/
│   │   ├── __init__.py
│   │   ├── resonance.py    # interest_overlap(), aesthetic_compat(), personality_compat(), resonance_score()
│   │   └── feed.py         # get_feed(), process_feed_interactions()
│   └── scheduler.py        # APScheduler 설정 + run_simulation()
├── tests/
│   ├── conftest.py         # tmp DB fixture
│   ├── test_models.py
│   ├── test_db.py
│   ├── test_events.py
│   ├── test_factory.py
│   ├── test_resonance.py
│   ├── test_content.py     # API 호출 mock
│   ├── test_wake.py
│   └── test_evolution.py   # API 호출 mock
├── images/
├── data/
├── main.py                 # CLI 진입점
├── requirements.txt
└── .env.example
```

---

### Task 1: 프로젝트 셋업 + DB 스키마

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `src/__init__.py`, `src/db/__init__.py`
- Create: `src/models.py`
- Create: `src/db/schema.py`
- Create: `tests/conftest.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Produces: `init_db(db_path: str) -> None` — 모든 테이블 생성
- Produces: `Agent`, `Personality`, `Aesthetic`, `Post` 데이터클래스

- [ ] **Step 1: requirements.txt 작성**

```
anthropic>=0.40.0
openai>=1.50.0
apscheduler>=3.10.0
python-dotenv>=1.0.0
httpx>=0.27.0
pytest>=8.0.0
pytest-mock>=3.14.0
```

- [ ] **Step 2: .env.example 작성**

```
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
DB_PATH=data/simulation.db
IMAGE_DIR=images
```

- [ ] **Step 3: 의존성 설치**

```bash
pip install -r requirements.txt
```

- [ ] **Step 4: src/models.py 작성**

```python
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
```

- [ ] **Step 5: src/db/schema.py 작성**

```python
import sqlite3

_TABLES = [
    """CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        personality_json TEXT NOT NULL,
        interests_json TEXT NOT NULL,
        aesthetic_json TEXT NOT NULL,
        caption_style TEXT NOT NULL,
        post_freq REAL NOT NULL,
        influence_received_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        evolved_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        topic TEXT NOT NULL,
        caption TEXT NOT NULL,
        image_path TEXT,
        ig_post_id TEXT,
        quality_score REAL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (agent_id) REFERENCES agents(id)
    )""",
    """CREATE TABLE IF NOT EXISTS interactions (
        id TEXT PRIMARY KEY,
        from_agent_id TEXT NOT NULL,
        to_post_id TEXT NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('like', 'comment')),
        content TEXT,
        resonance_score REAL NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (from_agent_id) REFERENCES agents(id),
        FOREIGN KEY (to_post_id) REFERENCES posts(id)
    )""",
    """CREATE TABLE IF NOT EXISTS follows (
        follower_id TEXT NOT NULL,
        following_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (follower_id, following_id),
        FOREIGN KEY (follower_id) REFERENCES agents(id),
        FOREIGN KEY (following_id) REFERENCES agents(id)
    )""",
    """CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        processed_at TEXT,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS evolution_log (
        id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        before_json TEXT NOT NULL,
        after_json TEXT NOT NULL,
        trigger TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (agent_id) REFERENCES agents(id)
    )""",
]


def init_db(db_path: str) -> None:
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        for stmt in _TABLES:
            conn.execute(stmt)
```

- [ ] **Step 6: tests/conftest.py 작성**

```python
import pytest
import tempfile
import os
from src.db.schema import init_db


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path
```

- [ ] **Step 7: tests/test_db.py 작성 (failing)**

```python
import sqlite3
from src.db.schema import init_db


def test_init_db_creates_all_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert tables == {"agents", "posts", "interactions", "follows", "events", "evolution_log"}


def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # 두 번 호출해도 오류 없어야 함
```

- [ ] **Step 8: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_db.py -v
```
Expected: FAIL (schema.py 없음)

- [ ] **Step 9: 테스트 통과 확인**

```bash
pytest tests/test_db.py -v
```
Expected: 2 passed

- [ ] **Step 10: 커밋**

```bash
git add src/ tests/ requirements.txt .env.example
git commit -m "feat: project setup, data models, and DB schema"
```

---

### Task 2: AgentRepository + AgentFactory

**Files:**
- Create: `src/db/repository.py`
- Create: `src/agents/__init__.py`
- Create: `src/agents/factory.py`
- Create: `tests/test_factory.py`

**Interfaces:**
- Consumes: `Agent`, `Personality`, `Aesthetic` (from `src/models.py`), `init_db` (from `src/db/schema.py`)
- Produces: `AgentRepo.save(agent: Agent) -> None`
- Produces: `AgentRepo.get(agent_id: str) -> Agent | None`
- Produces: `AgentRepo.list_all() -> list[Agent]`
- Produces: `AgentRepo.update_influence(agent_id: str, from_id: str, delta: float) -> None`
- Produces: `create_random_agent() -> Agent`

- [ ] **Step 1: tests/test_factory.py 작성 (failing)**

```python
from src.agents.factory import create_random_agent
from src.models import Agent


def test_create_random_agent_returns_agent():
    agent = create_random_agent()
    assert isinstance(agent, Agent)


def test_create_random_agent_age_in_range():
    for _ in range(20):
        agent = create_random_agent()
        assert 18 <= agent.age <= 40


def test_create_random_agent_interests_count():
    for _ in range(20):
        agent = create_random_agent()
        assert 3 <= len(agent.interests) <= 5


def test_create_random_agent_post_freq_in_range():
    for _ in range(20):
        agent = create_random_agent()
        assert 0.3 <= agent.post_freq <= 3.0


def test_create_random_agent_has_unique_id():
    ids = {create_random_agent().id for _ in range(10)}
    assert len(ids) == 10
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_factory.py -v
```
Expected: FAIL

- [ ] **Step 3: src/agents/factory.py 작성**

```python
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
```

- [ ] **Step 4: src/db/repository.py 작성**

```python
import json
import sqlite3
from datetime import datetime, timezone
from src.models import Agent, Personality, Aesthetic, Post


def _agent_from_row(row) -> Agent:
    return Agent(
        id=row[0], name=row[1], age=row[2],
        personality=Personality(**json.loads(row[3])),
        interests=json.loads(row[4]),
        aesthetic=Aesthetic(**json.loads(row[5])),
        caption_style=row[6], post_freq=row[7],
        influence_received=json.loads(row[8]),
        created_at=row[9], evolved_at=row[10],
    )


class AgentRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def save(self, agent: Agent) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (agent.id, agent.name, agent.age,
                 json.dumps(agent.personality.__dict__),
                 json.dumps(agent.interests),
                 json.dumps(agent.aesthetic.__dict__),
                 agent.caption_style, agent.post_freq,
                 json.dumps(agent.influence_received),
                 agent.created_at, agent.evolved_at),
            )

    def get(self, agent_id: str) -> Agent | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE id=?", (agent_id,)
            ).fetchone()
        return _agent_from_row(row) if row else None

    def list_all(self) -> list[Agent]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM agents").fetchall()
        return [_agent_from_row(r) for r in rows]

    def update_influence(self, agent_id: str, from_id: str, delta: float) -> None:
        agent = self.get(agent_id)
        if agent is None:
            return
        agent.influence_received[from_id] = round(
            agent.influence_received.get(from_id, 0.0) + delta, 3
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE agents SET influence_received_json=? WHERE id=?",
                (json.dumps(agent.influence_received), agent_id),
            )


class PostRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def save(self, post: Post) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?,?,?)",
                (post.id, post.agent_id, post.topic, post.caption,
                 post.image_path, post.ig_post_id, post.quality_score, post.created_at),
            )

    def get_by_agent(self, agent_id: str, limit: int = 20) -> list[Post]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM posts WHERE agent_id=? ORDER BY created_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
        return [Post(*r) for r in rows]

    def get_feed(self, following_ids: list[str], limit: int = 30) -> list[Post]:
        if not following_ids:
            return []
        placeholders = ",".join("?" * len(following_ids))
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM posts WHERE agent_id IN ({placeholders}) "
                f"ORDER BY created_at DESC LIMIT ?",
                (*following_ids, limit),
            ).fetchall()
        return [Post(*r) for r in rows]

    def get_last_post_time(self, agent_id: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT created_at FROM posts WHERE agent_id=? ORDER BY created_at DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
        return row[0] if row else None


class InteractionRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def save(self, interaction_id: str, from_agent_id: str, to_post_id: str,
             itype: str, content: str | None, resonance_score: float) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO interactions VALUES (?,?,?,?,?,?,?)",
                (interaction_id, from_agent_id, to_post_id, itype,
                 content, resonance_score, datetime.now(timezone.utc).isoformat()),
            )

    def has_liked(self, from_agent_id: str, to_post_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM interactions WHERE from_agent_id=? AND to_post_id=? AND type='like'",
                (from_agent_id, to_post_id),
            ).fetchone()
        return row is not None

    def get_recent_resonances(self, agent_id: str, poster_id: str, limit: int = 20) -> list[float]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT i.resonance_score FROM interactions i
                   JOIN posts p ON i.to_post_id = p.id
                   WHERE i.from_agent_id=? AND p.agent_id=?
                   ORDER BY i.created_at DESC LIMIT ?""",
                (agent_id, poster_id, limit),
            ).fetchall()
        return [r[0] for r in rows]


class FollowRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def follow(self, follower_id: str, following_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO follows VALUES (?,?,?)",
                (follower_id, following_id, datetime.now(timezone.utc).isoformat()),
            )

    def unfollow(self, follower_id: str, following_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM follows WHERE follower_id=? AND following_id=?",
                (follower_id, following_id),
            )

    def get_following(self, agent_id: str) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT following_id FROM follows WHERE follower_id=?", (agent_id,)
            ).fetchall()
        return [r[0] for r in rows]

    def is_following(self, follower_id: str, following_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM follows WHERE follower_id=? AND following_id=?",
                (follower_id, following_id),
            ).fetchone()
        return row is not None


class EvolutionRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def log(self, log_id: str, agent_id: str, before: dict, after: dict, trigger: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO evolution_log VALUES (?,?,?,?,?,?)",
                (log_id, agent_id, json.dumps(before), json.dumps(after),
                 trigger, datetime.now(timezone.utc).isoformat()),
            )
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_factory.py -v
```
Expected: 5 passed

- [ ] **Step 6: Repository 통합 테스트 추가 및 실행**

`tests/test_db.py`에 추가:

```python
from src.agents.factory import create_random_agent
from src.db.repository import AgentRepo, PostRepo, FollowRepo
from src.models import Post
import uuid
from datetime import datetime, timezone


def test_agent_repo_save_and_get(tmp_db):
    repo = AgentRepo(tmp_db)
    agent = create_random_agent()
    repo.save(agent)
    retrieved = repo.get(agent.id)
    assert retrieved is not None
    assert retrieved.id == agent.id
    assert retrieved.name == agent.name
    assert retrieved.interests == agent.interests


def test_agent_repo_list_all(tmp_db):
    repo = AgentRepo(tmp_db)
    agents = [create_random_agent() for _ in range(3)]
    for a in agents:
        repo.save(a)
    assert len(repo.list_all()) == 3


def test_follow_repo(tmp_db):
    agent_repo = AgentRepo(tmp_db)
    follow_repo = FollowRepo(tmp_db)
    a, b = create_random_agent(), create_random_agent()
    agent_repo.save(a)
    agent_repo.save(b)
    follow_repo.follow(a.id, b.id)
    assert follow_repo.is_following(a.id, b.id)
    assert b.id in follow_repo.get_following(a.id)
    follow_repo.unfollow(a.id, b.id)
    assert not follow_repo.is_following(a.id, b.id)
```

```bash
pytest tests/test_db.py -v
```
Expected: 4 passed

- [ ] **Step 7: 커밋**

```bash
git add src/ tests/
git commit -m "feat: agent model, factory, and repository layer"
```

---

### Task 3: EventBus

**Files:**
- Create: `src/events/__init__.py`
- Create: `src/events/bus.py`
- Create: `tests/test_events.py`

**Interfaces:**
- Consumes: `init_db` (from `src/db/schema.py`)
- Produces: `EventBus(db_path: str)`
- Produces: `EventBus.publish(event_type: str, payload: dict) -> str`
- Produces: `EventBus.consume(event_type: str, limit: int = 50) -> list[Event]`
- Produces: `Event` dataclass: `id: str`, `type: str`, `payload: dict`, `created_at: str`

- [ ] **Step 1: tests/test_events.py 작성 (failing)**

```python
from src.events.bus import EventBus, Event


def test_publish_returns_event_id(tmp_db):
    bus = EventBus(tmp_db)
    event_id = bus.publish("PostCreated", {"post_id": "abc"})
    assert isinstance(event_id, str) and len(event_id) > 0


def test_consume_returns_published_events(tmp_db):
    bus = EventBus(tmp_db)
    bus.publish("PostCreated", {"post_id": "abc"})
    events = bus.consume("PostCreated")
    assert len(events) == 1
    assert events[0].type == "PostCreated"
    assert events[0].payload == {"post_id": "abc"}


def test_consume_marks_events_processed(tmp_db):
    bus = EventBus(tmp_db)
    bus.publish("PostCreated", {"post_id": "abc"})
    bus.consume("PostCreated")
    events_again = bus.consume("PostCreated")
    assert len(events_again) == 0


def test_consume_filters_by_type(tmp_db):
    bus = EventBus(tmp_db)
    bus.publish("PostCreated", {"post_id": "a"})
    bus.publish("LikeAdded", {"post_id": "a", "from": "x"})
    events = bus.consume("LikeAdded")
    assert len(events) == 1
    assert events[0].type == "LikeAdded"
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_events.py -v
```
Expected: FAIL

- [ ] **Step 3: src/events/bus.py 작성**

```python
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class Event:
    id: str
    type: str
    payload: dict[str, Any]
    created_at: str


class EventBus:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def publish(self, event_type: str, payload: dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO events (id, type, payload_json, created_at) VALUES (?,?,?,?)",
                (event_id, event_type, json.dumps(payload),
                 datetime.now(timezone.utc).isoformat()),
            )
        return event_id

    def consume(self, event_type: str, limit: int = 50) -> list[Event]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, type, payload_json, created_at FROM events "
                "WHERE type=? AND processed_at IS NULL "
                "ORDER BY created_at ASC LIMIT ?",
                (event_type, limit),
            ).fetchall()
            if rows:
                ids = [r[0] for r in rows]
                conn.execute(
                    f"UPDATE events SET processed_at=? WHERE id IN ({','.join('?'*len(ids))})",
                    [datetime.now(timezone.utc).isoformat(), *ids],
                )
        return [Event(id=r[0], type=r[1], payload=json.loads(r[2]), created_at=r[3])
                for r in rows]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_events.py -v
```
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/events/ tests/test_events.py
git commit -m "feat: SQLite-backed EventBus with publish/consume"
```

---

### Task 4: Resonance Score + Feed Engine

**Files:**
- Create: `src/social/__init__.py`
- Create: `src/social/resonance.py`
- Create: `src/social/feed.py`
- Create: `tests/test_resonance.py`

**Interfaces:**
- Consumes: `Agent` (from `src/models.py`)
- Produces: `resonance_score(viewer: Agent, poster: Agent) -> float` — 0.0~1.0
- Produces: `like_threshold(agent: Agent) -> float`
- Produces: `comment_threshold(agent: Agent) -> float`
- Produces: `get_feed(agent_id: str, follow_repo: FollowRepo, post_repo: PostRepo) -> list[Post]`

- [ ] **Step 1: tests/test_resonance.py 작성 (failing)**

```python
from src.models import Agent, Personality, Aesthetic
from src.social.resonance import (
    interest_overlap, aesthetic_compat, personality_compat,
    resonance_score, like_threshold, comment_threshold,
)


def _make_agent(interests, palette="warm", composition="minimal", energy=0.5):
    return Agent(
        id="x", name="test", age=25,
        personality=Personality(energy=energy, valence=0.5, openness=0.5),
        interests=interests,
        aesthetic=Aesthetic(palette=palette, composition=composition),
        caption_style="concise", post_freq=1.0,
    )


def test_interest_overlap_identical():
    a = _make_agent({"사진": 0.8, "음식": 0.5})
    assert interest_overlap(a, a) == pytest.approx(1.0, abs=0.01)


def test_interest_overlap_no_shared():
    a = _make_agent({"사진": 0.8})
    b = _make_agent({"음식": 0.8})
    assert interest_overlap(a, b) == 0.0


def test_aesthetic_compat_same():
    a = _make_agent({}, "warm", "minimal")
    assert aesthetic_compat(a, a) == 1.0


def test_aesthetic_compat_different():
    a = _make_agent({}, "warm", "minimal")
    b = _make_agent({}, "cool", "busy")
    assert aesthetic_compat(a, b) < 1.0


def test_resonance_score_range():
    a = _make_agent({"사진": 0.8, "음식": 0.5})
    b = _make_agent({"사진": 0.7, "여행": 0.4})
    score = resonance_score(a, b)
    assert 0.0 <= score <= 1.0


def test_like_threshold_extrovert_lower():
    introverted = _make_agent({}, energy=0.1)
    extroverted = _make_agent({}, energy=0.9)
    assert like_threshold(extroverted) < like_threshold(introverted)


def test_comment_threshold_higher_than_like():
    agent = _make_agent({}, energy=0.5)
    assert comment_threshold(agent) > like_threshold(agent)
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_resonance.py -v
```
Expected: FAIL

- [ ] **Step 3: import pytest 추가 후 src/social/resonance.py 작성**

`tests/test_resonance.py` 상단에 `import pytest` 추가.

```python
from src.models import Agent


def interest_overlap(a: Agent, b: Agent) -> float:
    shared = set(a.interests) & set(b.interests)
    if not shared:
        return 0.0
    score = sum(min(a.interests[k], b.interests[k]) for k in shared)
    max_possible = sum(sorted(a.interests.values(), reverse=True)[:len(shared)])
    return score / max_possible if max_possible > 0 else 0.0


def aesthetic_compat(a: Agent, b: Agent) -> float:
    palette_match = 1.0 if a.aesthetic.palette == b.aesthetic.palette else 0.3
    comp_match = 1.0 if a.aesthetic.composition == b.aesthetic.composition else 0.3
    return (palette_match + comp_match) / 2


def personality_compat(a: Agent, b: Agent) -> float:
    energy_diff = abs(a.personality.energy - b.personality.energy)
    valence_diff = abs(a.personality.valence - b.personality.valence)
    return 1.0 - (energy_diff + valence_diff) / 2


def resonance_score(viewer: Agent, poster: Agent) -> float:
    return (
        interest_overlap(viewer, poster) * 0.5
        + aesthetic_compat(viewer, poster) * 0.3
        + personality_compat(viewer, poster) * 0.2
    )


def like_threshold(agent: Agent) -> float:
    return round(0.7 - agent.personality.energy * 0.4, 3)


def comment_threshold(agent: Agent) -> float:
    return round(like_threshold(agent) + 0.15, 3)
```

- [ ] **Step 4: src/social/feed.py 작성**

```python
from src.db.repository import FollowRepo, PostRepo
from src.models import Post


def get_feed(agent_id: str, follow_repo: FollowRepo, post_repo: PostRepo,
             limit: int = 30) -> list[Post]:
    following = follow_repo.get_following(agent_id)
    return post_repo.get_feed(following, limit=limit)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_resonance.py -v
```
Expected: 7 passed

- [ ] **Step 6: 커밋**

```bash
git add src/social/ tests/test_resonance.py
git commit -m "feat: resonance scoring and feed engine"
```

---

### Task 5: Content Generation Pipeline

**Files:**
- Create: `src/content/__init__.py`
- Create: `src/content/caption.py`
- Create: `src/content/image.py`
- Create: `src/content/pipeline.py`
- Create: `tests/test_content.py`

**Interfaces:**
- Consumes: `Agent` (from `src/models.py`)
- Produces: `generate_caption(agent: Agent, topic: str, client: anthropic.Anthropic) -> str`
- Produces: `generate_image_prompt(agent: Agent, caption: str, client: anthropic.Anthropic) -> str`
- Produces: `generate_image(prompt: str, save_dir: str, client: openai.OpenAI) -> str` — 저장된 파일 경로 반환
- Produces: `create_post(agent: Agent, db_path: str, anthropic_client, openai_client) -> Post`

- [ ] **Step 1: tests/test_content.py 작성 (failing)**

```python
from unittest.mock import MagicMock, patch
from src.agents.factory import create_random_agent
from src.content.caption import generate_caption, generate_image_prompt
from src.content.image import generate_image
from src.content.pipeline import create_post


def _mock_anthropic(text: str):
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    client.messages.create.return_value = msg
    return client


def test_generate_caption_returns_string_with_robot_emoji():
    agent = create_random_agent()
    client = _mock_anthropic("오늘 커피 한 잔 🤖")
    result = generate_caption(agent, "음식", client)
    assert isinstance(result, str)
    assert "🤖" in result


def test_generate_image_prompt_returns_string():
    agent = create_random_agent()
    client = _mock_anthropic("A warm minimal photo of coffee")
    result = generate_image_prompt(agent, "오늘 커피 한 잔 🤖", client)
    assert isinstance(result, str) and len(result) > 0


def test_generate_image_saves_file(tmp_path):
    mock_client = MagicMock()
    mock_client.images.generate.return_value = MagicMock(
        data=[MagicMock(url="http://example.com/img.png")]
    )
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(content=b"fakepng")
        path = generate_image("a photo", str(tmp_path), mock_client)
    assert path.endswith(".png")
    import os
    assert os.path.exists(path)


def test_create_post_saves_to_db(tmp_db, tmp_path):
    from src.db.repository import AgentRepo, PostRepo
    from src.agents.factory import create_random_agent
    agent = create_random_agent()
    AgentRepo(tmp_db).save(agent)

    anthropic_client = _mock_anthropic("테스트 캡션 🤖")
    openai_client = MagicMock()
    openai_client.images.generate.return_value = MagicMock(
        data=[MagicMock(url="http://example.com/img.png")]
    )
    with patch("httpx.get", return_value=MagicMock(content=b"fakepng")):
        post = create_post(agent, tmp_db, anthropic_client, openai_client,
                           image_dir=str(tmp_path))

    posts = PostRepo(tmp_db).get_by_agent(agent.id)
    assert len(posts) == 1
    assert posts[0].id == post.id
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_content.py -v
```
Expected: FAIL

- [ ] **Step 3: src/content/caption.py 작성**

```python
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
```

- [ ] **Step 4: src/content/image.py 작성**

```python
import uuid
import httpx
import openai
from pathlib import Path


def generate_image(prompt: str, save_dir: str, client: openai.OpenAI) -> str:
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    image_url = response.data[0].url
    image_data = httpx.get(image_url).content
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    filepath = Path(save_dir) / f"{uuid.uuid4()}.png"
    filepath.write_bytes(image_data)
    return str(filepath)
```

- [ ] **Step 5: src/content/pipeline.py 작성**

```python
import os
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
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
pytest tests/test_content.py -v
```
Expected: 4 passed

- [ ] **Step 7: 커밋**

```bash
git add src/content/ tests/test_content.py
git commit -m "feat: content generation pipeline (caption + image)"
```

---

### Task 6: Agent Wake Cycle

**Files:**
- Create: `src/agents/wake.py`
- Create: `tests/test_wake.py`

**Interfaces:**
- Consumes: `Agent` (from `src/models.py`), `resonance_score`, `like_threshold`, `comment_threshold` (from `src/social/resonance.py`), `get_feed` (from `src/social/feed.py`), `AgentRepo`, `PostRepo`, `InteractionRepo`, `FollowRepo` (from `src/db/repository.py`), `EventBus` (from `src/events/bus.py`), `create_post` (from `src/content/pipeline.py`)
- Produces: `should_post(agent: Agent, last_post_time: str | None) -> bool`
- Produces: `run_wake_cycle(agent_id: str, db_path: str, anthropic_client, openai_client, image_dir: str) -> None`

- [ ] **Step 1: tests/test_wake.py 작성 (failing)**

```python
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
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_wake.py -v
```
Expected: FAIL

- [ ] **Step 3: src/agents/wake.py 작성**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_wake.py -v
```
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add src/agents/wake.py tests/test_wake.py
git commit -m "feat: agent wake cycle with feed reactions and post decision"
```

---

### Task 7: Personality Evolution

**Files:**
- Create: `src/agents/evolution.py`
- Create: `tests/test_evolution.py`

**Interfaces:**
- Consumes: `Agent` (from `src/models.py`), `AgentRepo`, `InteractionRepo`, `EvolutionRepo` (from `src/db/repository.py`)
- Produces: `check_evolution(agent: Agent) -> bool`
- Produces: `evolve_agent(agent: Agent, db_path: str, client: anthropic.Anthropic) -> Agent`

- [ ] **Step 1: tests/test_evolution.py 작성 (failing)**

```python
from unittest.mock import MagicMock
from src.agents.factory import create_random_agent
from src.agents.evolution import check_evolution, evolve_agent
import json


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
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_evolution.py -v
```
Expected: FAIL

- [ ] **Step 3: src/agents/evolution.py 작성**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_evolution.py -v
```
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/agents/evolution.py tests/test_evolution.py
git commit -m "feat: personality evolution via influence accumulation"
```

---

### Task 8: Scheduler + 진입점 (2-에이전트 스모크 테스트)

**Files:**
- Create: `src/scheduler.py`
- Create: `main.py`

**Interfaces:**
- Consumes: `run_wake_cycle` (from `src/agents/wake.py`), `evolve_agent`, `check_evolution` (from `src/agents/evolution.py`), `AgentRepo` (from `src/db/repository.py`), `create_random_agent` (from `src/agents/factory.py`), `FollowRepo` (from `src/db/repository.py`), `init_db` (from `src/db/schema.py`)
- Produces: `run_simulation(n_agents: int, db_path: str, image_dir: str, interval_seconds: int) -> None`

- [ ] **Step 1: src/scheduler.py 작성**

```python
import os
import random
import time

import anthropic
import openai
from apscheduler.schedulers.blocking import BlockingScheduler

from src.agents.evolution import check_evolution, evolve_agent
from src.agents.factory import create_random_agent
from src.agents.wake import run_wake_cycle
from src.db.repository import AgentRepo, FollowRepo
from src.db.schema import init_db


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
    # 초기 랜덤 팔로우 (각자 2~5개)
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

    def tick():
        agent_repo = AgentRepo(db_path)
        agents = agent_repo.list_all()
        random.shuffle(agents)
        for agent in agents:
            run_wake_cycle(agent.id, db_path, ac, oc, image_dir)
            fresh = agent_repo.get(agent.id)
            if fresh and check_evolution(fresh):
                evolve_agent(fresh, db_path, ac)

    scheduler = BlockingScheduler()
    scheduler.add_job(tick, "interval", seconds=interval_seconds, id="tick")
    print(f"시뮬레이션 시작: {n_agents}명 에이전트, {interval_seconds}초 간격")
    tick()  # 즉시 1회 실행
    scheduler.start()
```

- [ ] **Step 2: main.py 작성**

```python
import argparse
import os
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Agent Instagram Simulator")
    parser.add_argument("--agents", type=int, default=5, help="에이전트 수")
    parser.add_argument("--db", default="data/simulation.db", help="DB 경로")
    parser.add_argument("--images", default="images", help="이미지 저장 경로")
    parser.add_argument("--interval", type=int, default=300, help="wake cycle 간격(초)")
    args = parser.parse_args()

    from src.scheduler import run_simulation
    run_simulation(
        n_agents=args.agents,
        db_path=args.db,
        image_dir=args.images,
        interval_seconds=args.interval,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: .env 파일 생성 (실제 키 입력)**

```bash
cp .env.example .env
# ANTHROPIC_API_KEY, OPENAI_API_KEY 실제 값으로 편집
```

- [ ] **Step 4: 전체 테스트 실행**

```bash
pytest tests/ -v
```
Expected: 전체 통과

- [ ] **Step 5: 2-에이전트 스모크 테스트 실행**

```bash
python main.py --agents 2 --interval 60
```

확인 항목:
- `data/simulation.db` 생성됨
- `images/` 에 PNG 파일 생성됨
- 에이전트 2명이 DB에 저장됨
- 첫 포스트 생성 후 PostCreated 이벤트 발행됨

```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/simulation.db')
print('agents:', conn.execute('SELECT name, age FROM agents').fetchall())
print('posts:', conn.execute('SELECT COUNT(*) FROM posts').fetchone())
print('events:', conn.execute('SELECT type, COUNT(*) FROM events GROUP BY type').fetchall())
"
```

- [ ] **Step 6: 커밋**

```bash
git add src/scheduler.py main.py
git commit -m "feat: scheduler and main entry point — Phase 1 complete"
```

---

## 전체 테스트 실행

```bash
pytest tests/ -v --tb=short
```

Expected: 모든 테스트 통과

---

## Phase 3 (후속 계획)

Instagram 브리지는 실계정 준비 후 별도 계획으로 진행:
- `docs/superpowers/plans/YYYY-MM-DD-phase3-ig-bridge.md`
- instagrapi 또는 Graph API 연동
- 품질 점수 필터링 로직

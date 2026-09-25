# Phase 3 — Instagram Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로컬 시뮬레이션에서 생성된 포스트에 품질 점수를 부여하고, 임계값을 초과한 포스트를 실제 Instagram 계정에 게시한다.

**Architecture:** 주기적 bridge tick이 채점되지 않은 포스트를 가져와 Claude Haiku로 품질 점수를 계산하고, 점수가 threshold(0.7) 이상인 포스트는 Cloudinary에 이미지를 업로드한 뒤 Instagram Graph API로 게시한다. 기존 posts 테이블의 `quality_score`, `ig_post_id` 컬럼을 활용한다.

**Tech Stack:** Anthropic SDK (claude-haiku-4-5-20251001), cloudinary Python SDK, httpx, Instagram Graph API v18.0

**Spec:** `docs/superpowers/specs/2026-09-21-natural-agent-instagram-design.md` (섹션 6)

## Global Constraints

- Python 3.11+
- Instagram Business 또는 Creator 계정 + Facebook Page 연결 필수
- Instagram Graph API v18.0 사용 (`https://graph.facebook.com/v18.0`)
- 필요 권한: `instagram_basic`, `instagram_content_publish`
- 모든 Instagram 캡션에 `🤖 AI agent` 포함 (spec 명시)
- 품질 채점 모델: `claude-haiku-4-5-20251001`
- 이미지 호스팅: Cloudinary (CLOUDINARY_URL 환경 변수)
- 기존 `posts` 테이블 스키마 유지 (컬럼 추가 없음 — `quality_score`, `ig_post_id` 이미 존재)
- 테스트는 모두 mock 기반 (실제 API 호출 없음)

---

## 파일 구조

```
src/
  content/
    quality.py          # NEW: 품질 점수 생성
  instagram/
    __init__.py         # NEW: 패키지 init
    client.py           # NEW: Cloudinary 업로드 + Graph API 래퍼
    bridge.py           # NEW: 품질 필터 + DB 업데이트 + 게시 결정
  db/
    repository.py       # MODIFY: PostRepo에 3개 메서드 추가
  scheduler.py          # MODIFY: bridge tick job 추가
tests/
  test_quality.py       # NEW
  test_instagram.py     # NEW
requirements.txt        # MODIFY: cloudinary 추가
.env.example            # MODIFY: IG/Cloudinary 자격증명 추가
```

---

### Task 1: Quality Score Module + PostRepo 확장

**Files:**
- Create: `src/content/quality.py`
- Modify: `src/db/repository.py` (PostRepo에 3개 메서드 추가)
- Test: `tests/test_quality.py`

**Interfaces:**
- Consumes: `Post` (from `src/models.py`), `Agent` (from `src/models.py`), `anthropic.Anthropic`
- Produces:
  - `generate_quality_score(post: Post, agent: Agent, client: anthropic.Anthropic) -> float`
  - `PostRepo.get_unscored(db_path: str) -> list[Post]` (quality_score IS NULL, ig_post_id IS NULL)
  - `PostRepo.update_quality_score(post_id: str, score: float) -> None`
  - `PostRepo.update_ig_post_id(post_id: str, ig_post_id: str) -> None`

- [ ] **Step 1: tests/test_quality.py 작성**

```python
import json
from unittest.mock import MagicMock, patch
import pytest
from src.content.quality import generate_quality_score
from src.models import Agent, Personality, Aesthetic, Post


@pytest.fixture
def sample_agent():
    return Agent(
        id="a1", name="Mia", age=24,
        personality=Personality(energy=0.8, valence=0.7, openness=0.9),
        interests={"photography": 0.9, "travel": 0.6},
        aesthetic=Aesthetic(palette="warm", composition="rule_of_thirds"),
        caption_style="poetic",
        post_freq=1.5,
        created_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_post():
    return Post(
        id="p1", agent_id="a1", topic="photography",
        caption="Golden hour whispers through the lens ✨ 🤖 AI agent",
        image_path="images/test.png",
        ig_post_id=None, quality_score=None,
        created_at="2026-01-01T00:00:00Z",
    )


def test_quality_score_returns_float(sample_agent, sample_post):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.8, "persona_consistency": 0.9, "image_caption_alignment": 0.7}
    )
    score = generate_quality_score(sample_post, sample_agent, mock_client)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_quality_score_averages_three_dimensions(sample_agent, sample_post):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.6, "persona_consistency": 0.6, "image_caption_alignment": 0.6}
    )
    score = generate_quality_score(sample_post, sample_agent, mock_client)
    assert abs(score - 0.6) < 0.01


def test_quality_score_handles_malformed_json(sample_agent, sample_post):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content[0].text = "not json at all"
    score = generate_quality_score(sample_post, sample_agent, mock_client)
    assert score == 0.0


def test_quality_score_uses_haiku_model(sample_agent, sample_post):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.5, "persona_consistency": 0.5, "image_caption_alignment": 0.5}
    )
    generate_quality_score(sample_post, sample_agent, mock_client)
    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs.kwargs["model"] == "claude-haiku-4-5-20251001"
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_quality.py -v
```
Expected: `ImportError` 또는 `ModuleNotFoundError`

- [ ] **Step 3: src/content/quality.py 작성**

```python
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
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

```bash
pytest tests/test_quality.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: src/db/repository.py — PostRepo에 메서드 3개 추가**

`PostRepo` 클래스 끝에 추가:

```python
    def get_unscored(self) -> list["Post"]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM posts WHERE quality_score IS NULL AND ig_post_id IS NULL"
            ).fetchall()
        return [Post(*r) for r in rows]

    def update_quality_score(self, post_id: str, score: float) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE posts SET quality_score=? WHERE id=?", (score, post_id)
            )

    def update_ig_post_id(self, post_id: str, ig_post_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE posts SET ig_post_id=? WHERE id=?", (ig_post_id, post_id)
            )
```

- [ ] **Step 6: PostRepo 메서드 테스트 (tests/test_db.py에 추가)**

```python
def test_post_repo_unscored(tmp_db):
    from src.agents.factory import create_random_agent
    from src.db.repository import AgentRepo, PostRepo
    from src.models import Post
    import uuid
    from datetime import datetime, timezone

    agent = create_random_agent()
    AgentRepo(tmp_db).save(agent)
    post = Post(
        id=str(uuid.uuid4()), agent_id=agent.id, topic="art",
        caption="hello", image_path=None, ig_post_id=None,
        quality_score=None, created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo = PostRepo(tmp_db)
    repo.save(post)
    unscored = repo.get_unscored()
    assert len(unscored) == 1
    repo.update_quality_score(post.id, 0.85)
    assert repo.get_unscored() == []
    repo.update_ig_post_id(post.id, "ig123")
    fetched = repo.get_by_agent(agent.id)
    assert fetched[0].ig_post_id == "ig123"
```

- [ ] **Step 7: 전체 테스트 실행**

```bash
pytest tests/ -v
```
Expected: 37 PASSED (기존 33 + 질 채점 4개)

- [ ] **Step 8: 커밋**

```bash
git add src/content/quality.py src/db/repository.py tests/test_quality.py tests/test_db.py
git commit -m "feat: quality score module and PostRepo unscored/update methods"
```

---

### Task 2: Instagram Client (Cloudinary + Graph API)

**Files:**
- Create: `src/instagram/__init__.py`
- Create: `src/instagram/client.py`
- Modify: `requirements.txt`
- Test: `tests/test_instagram.py`

**Interfaces:**
- Consumes: `CLOUDINARY_URL` (env), `IG_USER_ID` (env), `IG_ACCESS_TOKEN` (env)
- Produces:
  - `CloudinaryUploader.upload(image_path: str) -> str` (public URL)
  - `InstagramClient(ig_user_id: str, access_token: str)`.`post(image_url: str, caption: str) -> str` (ig_post_id)

- [ ] **Step 1: requirements.txt에 cloudinary 추가**

```
cloudinary>=1.36.0
```

```bash
pip install cloudinary
```

- [ ] **Step 2: tests/test_instagram.py 작성**

```python
import pytest
from unittest.mock import MagicMock, patch


def test_cloudinary_uploader_returns_url():
    with patch("cloudinary.uploader.upload") as mock_upload:
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/test/image.png"}
        from src.instagram.client import CloudinaryUploader
        url = CloudinaryUploader().upload("images/test.png")
    assert url == "https://res.cloudinary.com/test/image.png"


def test_instagram_client_post_returns_ig_id():
    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "container_123"}),
            MagicMock(status_code=200, json=lambda: {"id": "ig_post_456"}),
        ]
        from src.instagram.client import InstagramClient
        client = InstagramClient(ig_user_id="user1", access_token="token1")
        ig_id = client.post(
            image_url="https://example.com/img.png",
            caption="Test caption 🤖 AI agent",
        )
    assert ig_id == "ig_post_456"


def test_instagram_client_raises_on_container_error():
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=400,
            json=lambda: {"error": {"message": "Invalid image"}},
        )
        from src.instagram.client import InstagramClient
        client = InstagramClient(ig_user_id="user1", access_token="token1")
        with pytest.raises(RuntimeError, match="container"):
            client.post(
                image_url="https://example.com/bad.png",
                caption="Test 🤖 AI agent",
            )


def test_instagram_client_raises_on_publish_error():
    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"id": "container_123"}),
            MagicMock(
                status_code=400,
                json=lambda: {"error": {"message": "Publish failed"}},
            ),
        ]
        from src.instagram.client import InstagramClient
        client = InstagramClient(ig_user_id="user1", access_token="token1")
        with pytest.raises(RuntimeError, match="publish"):
            client.post(
                image_url="https://example.com/img.png",
                caption="Test 🤖 AI agent",
            )


def test_cloudinary_uploader_uses_folder():
    with patch("cloudinary.uploader.upload") as mock_upload:
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/test/image.png"}
        from src.instagram.client import CloudinaryUploader
        CloudinaryUploader().upload("images/test.png")
    mock_upload.assert_called_once_with("images/test.png", folder="agent-instagram")
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_instagram.py -v
```
Expected: `ImportError`

- [ ] **Step 4: src/instagram/__init__.py 생성**

빈 파일:
```python
```

- [ ] **Step 5: src/instagram/client.py 작성**

```python
import cloudinary
import cloudinary.uploader
import httpx

_GRAPH_BASE = "https://graph.facebook.com/v18.0"


class CloudinaryUploader:
    def upload(self, image_path: str) -> str:
        result = cloudinary.uploader.upload(image_path, folder="agent-instagram")
        return result["secure_url"]


class InstagramClient:
    def __init__(self, ig_user_id: str, access_token: str):
        self._user_id = ig_user_id
        self._token = access_token

    def post(self, image_url: str, caption: str) -> str:
        with httpx.Client() as http:
            container_resp = http.post(
                f"{_GRAPH_BASE}/{self._user_id}/media",
                params={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": self._token,
                },
            )
            if container_resp.status_code != 200:
                raise RuntimeError(f"container creation failed: {container_resp.json()}")
            creation_id = container_resp.json()["id"]

            publish_resp = http.post(
                f"{_GRAPH_BASE}/{self._user_id}/media_publish",
                params={
                    "creation_id": creation_id,
                    "access_token": self._token,
                },
            )
            if publish_resp.status_code != 200:
                raise RuntimeError(f"publish failed: {publish_resp.json()}")
            return publish_resp.json()["id"]
```

- [ ] **Step 6: 테스트 실행 (통과 확인)**

```bash
pytest tests/test_instagram.py -v
```
Expected: 5 PASSED

- [ ] **Step 7: 전체 테스트 실행**

```bash
pytest tests/ -v
```
Expected: 42 PASSED

- [ ] **Step 8: 커밋**

```bash
git add src/instagram/ requirements.txt tests/test_instagram.py
git commit -m "feat: Cloudinary uploader and Instagram Graph API client"
```

---

### Task 3: Instagram Bridge + Scheduler 통합

**Files:**
- Create: `src/instagram/bridge.py`
- Modify: `src/scheduler.py` (bridge tick job 추가)
- Modify: `.env.example` (IG/Cloudinary 자격증명 추가)
- Test: `tests/test_bridge.py`

**Interfaces:**
- Consumes:
  - `generate_quality_score` (from `src/content/quality.py`)
  - `PostRepo.get_unscored`, `PostRepo.update_quality_score`, `PostRepo.update_ig_post_id` (from `src/db/repository.py`)
  - `AgentRepo.get` (from `src/db/repository.py`)
  - `CloudinaryUploader.upload` (from `src/instagram/client.py`)
  - `InstagramClient.post` (from `src/instagram/client.py`)
- Produces: `run_bridge_tick(db_path: str, anthropic_client, ig_client: InstagramClient | None, threshold: float = 0.7) -> int` (게시된 포스트 수)

- [ ] **Step 1: tests/test_bridge.py 작성**

```python
import pytest
from unittest.mock import MagicMock, patch, call
from src.db.schema import init_db
from src.agents.factory import create_random_agent
from src.db.repository import AgentRepo, PostRepo
from src.models import Post
import uuid
from datetime import datetime, timezone


@pytest.fixture
def db_with_posts(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    posts = [
        Post(
            id=str(uuid.uuid4()), agent_id=agent.id, topic="art",
            caption=f"Post {i} 🤖 AI agent", image_path=f"images/{i}.png",
            ig_post_id=None, quality_score=None,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        for i in range(3)
    ]
    repo = PostRepo(db_path)
    for p in posts:
        repo.save(p)
    return db_path, agent, posts


def test_bridge_tick_scores_unscored_posts(db_with_posts):
    import json
    db_path, agent, posts = db_with_posts
    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.5, "persona_consistency": 0.5, "image_caption_alignment": 0.5}
    )
    from src.instagram.bridge import run_bridge_tick
    run_bridge_tick(db_path, mock_ac, ig_client=None, threshold=0.7)
    repo = PostRepo(db_path)
    for p in posts:
        fetched = repo.get_by_agent(agent.id)
        assert all(fp.quality_score is not None for fp in fetched)


def test_bridge_tick_publishes_above_threshold(db_with_posts):
    import json
    db_path, agent, posts = db_with_posts
    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.9, "persona_consistency": 0.9, "image_caption_alignment": 0.9}
    )
    mock_ig = MagicMock()
    mock_ig.post.return_value = "ig_post_id_123"

    with patch("src.instagram.bridge.CloudinaryUploader") as MockUploader:
        mock_uploader_inst = MagicMock()
        mock_uploader_inst.upload.return_value = "https://example.com/img.png"
        MockUploader.return_value = mock_uploader_inst

        from src.instagram.bridge import run_bridge_tick
        count = run_bridge_tick(db_path, mock_ac, ig_client=mock_ig, threshold=0.7)

    assert count == 3


def test_bridge_tick_skips_below_threshold(db_with_posts):
    import json
    db_path, agent, posts = db_with_posts
    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.2, "persona_consistency": 0.2, "image_caption_alignment": 0.2}
    )
    mock_ig = MagicMock()
    from src.instagram.bridge import run_bridge_tick
    count = run_bridge_tick(db_path, mock_ac, ig_client=mock_ig, threshold=0.7)
    assert count == 0
    mock_ig.post.assert_not_called()


def test_bridge_tick_no_ig_client_skips_publish(db_with_posts):
    import json
    db_path, agent, posts = db_with_posts
    mock_ac = MagicMock()
    mock_ac.messages.create.return_value.content[0].text = json.dumps(
        {"caption_naturalness": 0.9, "persona_consistency": 0.9, "image_caption_alignment": 0.9}
    )
    from src.instagram.bridge import run_bridge_tick
    count = run_bridge_tick(db_path, mock_ac, ig_client=None, threshold=0.7)
    assert count == 0
    repo = PostRepo(db_path)
    fetched = repo.get_by_agent(agent.id)
    assert all(fp.ig_post_id is None for fp in fetched)
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_bridge.py -v
```
Expected: `ImportError`

- [ ] **Step 3: src/instagram/bridge.py 작성**

```python
import anthropic
from src.content.quality import generate_quality_score
from src.db.repository import AgentRepo, PostRepo
from src.instagram.client import CloudinaryUploader, InstagramClient


def run_bridge_tick(
    db_path: str,
    anthropic_client: anthropic.Anthropic,
    ig_client: InstagramClient | None,
    threshold: float = 0.7,
) -> int:
    post_repo = PostRepo(db_path)
    agent_repo = AgentRepo(db_path)
    unscored = post_repo.get_unscored()
    published = 0

    for post in unscored:
        agent = agent_repo.get(post.agent_id)
        if agent is None:
            continue
        score = generate_quality_score(post, agent, anthropic_client)
        post_repo.update_quality_score(post.id, score)

        if ig_client is None or score < threshold:
            continue

        try:
            uploader = CloudinaryUploader()
            image_url = uploader.upload(post.image_path)
            ig_post_id = ig_client.post(image_url=image_url, caption=post.caption)
            post_repo.update_ig_post_id(post.id, ig_post_id)
            published += 1
        except Exception as e:
            print(f"[bridge] 게시 실패 post={post.id}: {e}")

    return published
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

```bash
pytest tests/test_bridge.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: src/scheduler.py — bridge tick job 추가**

파일 상단 import 블록에 추가 (다른 `from src.*` import 아래):

```python
from src.instagram.bridge import run_bridge_tick
from src.instagram.client import InstagramClient
```

`run_simulation` 함수 내 `scheduler = BlockingScheduler()` 이후:

```python
    ig_user_id = os.environ.get("IG_USER_ID")
    ig_access_token = os.environ.get("IG_ACCESS_TOKEN")
    ig_client = (
        InstagramClient(ig_user_id=ig_user_id, access_token=ig_access_token)
        if ig_user_id and ig_access_token
        else None
    )

    def bridge_tick():
        n = run_bridge_tick(db_path, ac, ig_client)
        if n:
            print(f"[bridge] Instagram 게시: {n}건")
```

`scheduler.add_job(tick, ...)` 이후:

```python
    scheduler.add_job(bridge_tick, "interval", seconds=interval_seconds * 2, id="bridge")
```

전체 수정된 `run_simulation` 함수:

```python
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
```

- [ ] **Step 6: .env.example 업데이트**

```bash
cat >> .env.example << 'EOF'

# Instagram Graph API (Phase 3 — 실계정 연동 시 설정)
# 취득 방법: https://developers.facebook.com/docs/instagram-api/getting-started
IG_USER_ID=your_ig_user_id
IG_ACCESS_TOKEN=your_long_lived_token

# Cloudinary (이미지 공개 URL 호스팅)
# 취득 방법: https://cloudinary.com/documentation/cloudinary_sdks
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
EOF
```

- [ ] **Step 7: 전체 테스트 실행**

```bash
pytest tests/ -v
```
Expected: 46 PASSED (기존 37 + 브리지 4 + Instagram client 5)

- [ ] **Step 8: 커밋**

```bash
git add src/instagram/bridge.py src/scheduler.py .env.example tests/test_bridge.py
git commit -m "feat: Instagram bridge with quality filter and scheduler integration — Phase 3 complete"
```

---

## 전체 테스트 실행

```bash
pytest tests/ -v --tb=short
```

Expected: 46 PASSED

---

## 실제 Instagram 연동 설정 가이드

Phase 3 코드가 완성된 뒤 실계정에 연동하려면:

1. [Facebook Developers](https://developers.facebook.com) 앱 생성
2. Instagram Basic Display API + Content Publishing API 권한 추가
3. Instagram Business/Creator 계정을 Facebook Page에 연결
4. 앱 심사 또는 테스터 등록으로 `instagram_content_publish` 권한 획득
5. [Cloudinary](https://cloudinary.com) 무료 계정 생성 → `CLOUDINARY_URL` 복사
6. `.env`에 `IG_USER_ID`, `IG_ACCESS_TOKEN`, `CLOUDINARY_URL` 입력
7. `python main.py --agents 2 --interval 60` 실행

---

## Phase 4 (후속)

웹 대시보드 — 시뮬레이션 상태 모니터링, 포스트 갤러리, 에이전트 네트워크 시각화:
- `docs/superpowers/plans/YYYY-MM-DD-phase4-dashboard.md`

# Phase 4: 웹 대시보드 + CI/CD 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 실행 중인 시뮬레이션 DB를 읽어 에이전트·포스트·통계를 실시간 갱신하는 로컬 및 Fly.io 배포 가능한 웹 대시보드를 제공하고, GitHub Actions CI/CD로 테스트와 배포를 자동화한다.

**Architecture:** FastAPI + Jinja2 + htmx 조합으로 읽기 전용 웹 서버를 구현한다. 시뮬레이션 프로세스와 웹 서버는 완전히 분리되어 동일한 SQLite DB를 바라본다. Fly.io에는 두 프로세스(web, worker)를 동일 Volume에 마운트해 DB를 공유한다. `main.py`에 `simulate`/`web` 서브커맨드를 추가한다.

**Tech Stack:** FastAPI 0.111+, uvicorn 0.29+, Jinja2 3.1+, httpx 0.27+(기존), htmx 2.x (CDN), Python 3.12, Fly.io, GitHub Actions

**Spec:** docs/superpowers/plans/2026-09-25-phase4-web-dashboard.md (이 파일)

## Global Constraints

- Python 3.12+
- 기존 SQLite DB 스키마 변경 없음 (읽기 전용 쿼리만 추가)
- `src/db/repository.py` 패턴 유지 (`sqlite3.connect` 직접 사용, ORM 없음)
- htmx는 CDN으로 로드 (빌드 도구 없음)
- 대시보드는 읽기 전용 — 시뮬레이션 제어 기능 없음
- Fly.io region: `nrt` (도쿄)
- CI: PR 시 pytest + ruff, main push 시 fly deploy
- DB_PATH 환경 변수가 없으면 기본값 `data/simulation.db`

## Review Focus

1. **SQLite WAL 동시 접근**: 웹 서버(읽기)와 시뮬레이션(쓰기)이 동시에 접근 → `init_db`에서 `PRAGMA journal_mode=WAL` 활성화 필요; Task 1에서 처리
2. **Fly.io Volume 누락 시 DB 초기화**: `fly.toml`에 volume mount가 없으면 배포마다 DB가 비워짐 → Task 5에서 mounts 섹션 검증 테스트 필요
3. **`/api/posts` 무제한 조회**: DB가 커지면 응답이 느려짐 → `limit` 파라미터 최대값 500으로 제한, Task 2 테스트에 포함
4. **`avg_quality` NULL 처리**: 포스트가 없거나 전부 채점 전이면 `AVG(quality_score)`가 NULL → API 응답에서 `null` 반환, Task 2 테스트에 포함
5. **FLY_API_TOKEN 미설정 시 deploy job 실패**: secrets에 토큰 없으면 flyctl이 인증 오류 → deploy.yml에 `needs: test` 설정으로 테스트 통과 후에만 실행

---

## File Map

```
# 생성
src/web/__init__.py
src/web/app.py                      # FastAPI 앱 + 라우트 (stats/agents/posts/HTML)
src/web/templates/base.html         # 공통 레이아웃 (htmx CDN 포함)
src/web/templates/index.html        # 대시보드 (통계·에이전트·포스트)
Dockerfile
fly.toml
.github/workflows/test.yml
.github/workflows/deploy.yml
tests/test_web.py

# 수정
src/db/repository.py                # PostRepo.get_recent, AgentRepo.list_with_counts 추가
src/db/schema.py                    # PRAGMA journal_mode=WAL 추가
requirements.txt                    # fastapi, uvicorn, jinja2, ruff 추가
main.py                             # simulate/web 서브커맨드 추가
```

---

## Task 1: DB 확장 + SQLite WAL 모드

**Files:**
- Modify: `src/db/schema.py`
- Modify: `src/db/repository.py`
- Modify: `tests/test_db.py`

**Interfaces:**
- Consumes: 기존 `init_db(db_path)`, `AgentRepo`, `PostRepo`, `FollowRepo`
- Produces:
  - `PostRepo.get_recent(limit: int = 50) -> list[Post]` — 전체 포스트를 `created_at DESC`로 정렬, `agent_id`와 `agent_name`은 포함하지 않음 (Task 2에서 JOIN)
  - `AgentRepo.list_with_counts(db_path_override: str | None = None) -> list[dict]` — `{"id": str, "name": str, "age": int, "post_count": int, "follower_count": int, "evolved": bool}` 딕셔너리 목록

- [ ] **Step 1: 실패하는 테스트 작성 — get_recent**

```python
# tests/test_db.py 하단에 추가
import uuid as _uuid
from datetime import datetime, timezone

def test_get_recent_posts_returns_limit(tmp_path):
    from src.agents.factory import create_random_agent
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    repo = PostRepo(db_path)
    for i in range(10):
        repo.save(Post(
            id=str(_uuid.uuid4()), agent_id=agent.id, topic="t",
            caption=f"c{i}", image_path=None, ig_post_id=None,
            quality_score=None, created_at=datetime.now(timezone.utc).isoformat(),
        ))
    assert len(repo.get_recent(limit=5)) == 5

def test_get_recent_posts_default_limit(tmp_path):
    from src.agents.factory import create_random_agent
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    repo = PostRepo(db_path)
    for i in range(60):
        repo.save(Post(
            id=str(_uuid.uuid4()), agent_id=agent.id, topic="t",
            caption=f"c{i}", image_path=None, ig_post_id=None,
            quality_score=None, created_at=datetime.now(timezone.utc).isoformat(),
        ))
    assert len(repo.get_recent()) == 50
```

- [ ] **Step 2: 실패 확인**

```bash
cd /path/to/repo && pytest tests/test_db.py::test_get_recent_posts_returns_limit tests/test_db.py::test_get_recent_posts_default_limit -v
```
Expected: `AttributeError: 'PostRepo' object has no attribute 'get_recent'`

- [ ] **Step 3: PostRepo.get_recent 구현**

`src/db/repository.py`의 `PostRepo` 클래스에 다음 메서드 추가:

```python
def get_recent(self, limit: int = 50) -> list[Post]:
    with sqlite3.connect(self.db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [Post(*r) for r in rows]
```

- [ ] **Step 4: 실패하는 테스트 작성 — list_with_counts**

```python
# tests/test_db.py 하단에 추가
def test_agent_repo_list_with_counts(tmp_path):
    from src.agents.factory import create_random_agent
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    a1 = create_random_agent()
    a2 = create_random_agent()
    AgentRepo(db_path).save(a1)
    AgentRepo(db_path).save(a2)
    FollowRepo(db_path).follow(a2.id, a1.id)  # a2가 a1을 팔로우
    PostRepo(db_path).save(Post(
        id=str(_uuid.uuid4()), agent_id=a1.id, topic="t",
        caption="c", image_path=None, ig_post_id=None,
        quality_score=None, created_at=datetime.now(timezone.utc).isoformat(),
    ))
    rows = AgentRepo(db_path).list_with_counts()
    target = next(r for r in rows if r["id"] == a1.id)
    assert target["post_count"] == 1
    assert target["follower_count"] == 1
    assert isinstance(target["evolved"], bool)
```

- [ ] **Step 5: 실패 확인**

```bash
pytest tests/test_db.py::test_agent_repo_list_with_counts -v
```
Expected: `AttributeError: 'AgentRepo' object has no attribute 'list_with_counts'`

- [ ] **Step 6: AgentRepo.list_with_counts 구현**

`src/db/repository.py`의 `AgentRepo` 클래스에 다음 메서드 추가:

```python
def list_with_counts(self) -> list[dict]:
    with sqlite3.connect(self.db_path) as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.name, a.age, a.evolved_at,
                   COUNT(DISTINCT p.id) AS post_count,
                   COUNT(DISTINCT f.follower_id) AS follower_count
            FROM agents a
            LEFT JOIN posts p ON p.agent_id = a.id
            LEFT JOIN follows f ON f.following_id = a.id
            GROUP BY a.id
            ORDER BY a.name
            """
        ).fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "age": r[2],
            "evolved": r[3] is not None,
            "post_count": r[4],
            "follower_count": r[5],
        }
        for r in rows
    ]
```

- [ ] **Step 7: WAL 모드 활성화**

`src/db/schema.py`의 `init_db` 함수에서 `for stmt in _TABLES:` 루프 앞에 다음 줄 추가:

```python
conn.execute("PRAGMA journal_mode=WAL")
```

변경 후 `init_db`:
```python
def init_db(db_path: str) -> None:
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        for stmt in _TABLES:
            conn.execute(stmt)
```

- [ ] **Step 8: 전체 테스트 통과 확인**

```bash
pytest tests/ -q
```
Expected: 기존 48개 + 신규 3개 = 51개 통과

- [ ] **Step 9: 커밋**

```bash
git add src/db/schema.py src/db/repository.py tests/test_db.py
git commit -m "feat: add PostRepo.get_recent, AgentRepo.list_with_counts, WAL mode"
```

---

## Task 2: FastAPI 앱 + REST API

**Files:**
- Create: `src/web/__init__.py`
- Create: `src/web/app.py`
- Create: `tests/test_web.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes:
  - `PostRepo(db_path).get_recent(limit)` → `list[Post]`
  - `AgentRepo(db_path).list_with_counts()` → `list[dict]`
  - `sqlite3.connect(db_path).execute(stats_sql)`
- Produces:
  - `create_app(db_path: str) -> FastAPI` — TestClient에서 사용
  - `GET /api/stats` → `{"agent_count": int, "post_count": int, "interaction_count": int, "ig_published": int, "avg_quality": float | null}`
  - `GET /api/agents` → `[{"id": str, "name": str, "age": int, "post_count": int, "follower_count": int, "evolved": bool}]`
  - `GET /api/posts?limit=50` → `[{"id": str, "agent_id": str, "topic": str, "caption": str, "quality_score": float | null, "ig_post_id": str | null, "created_at": str}]`

- [ ] **Step 1: requirements.txt 업데이트**

`requirements.txt`에 다음 추가:
```
fastapi>=0.111.0
uvicorn>=0.29.0
jinja2>=3.1.0
ruff>=0.4.0
```

- [ ] **Step 2: 의존성 설치**

```bash
pip install fastapi uvicorn jinja2 ruff
```

- [ ] **Step 3: 실패하는 테스트 작성**

```python
# tests/test_web.py (새 파일)
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.agents.factory import create_random_agent
from src.db.repository import AgentRepo, PostRepo
from src.db.schema import init_db
from src.models import Post
from src.web.app import create_app


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return TestClient(create_app(db_path)), db_path


def test_stats_returns_zero_counts(client):
    c, _ = client
    resp = c.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_count"] == 0
    assert data["post_count"] == 0
    assert data["ig_published"] == 0
    assert data["avg_quality"] is None


def test_stats_avg_quality_with_scored_post(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    PostRepo(db_path).save(Post(
        id=str(uuid.uuid4()), agent_id=agent.id, topic="t",
        caption="c", image_path=None, ig_post_id=None,
        quality_score=0.8,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    c = TestClient(create_app(db_path))
    data = c.get("/api/stats").json()
    assert abs(data["avg_quality"] - 0.8) < 0.01


def test_agents_returns_list(client):
    c, _ = client
    resp = c.get("/api/agents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_posts_returns_list(client):
    c, _ = client
    resp = c.get("/api/posts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_posts_limit_param(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    for _ in range(10):
        PostRepo(db_path).save(Post(
            id=str(uuid.uuid4()), agent_id=agent.id, topic="t",
            caption="c", image_path=None, ig_post_id=None,
            quality_score=None,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
    c = TestClient(create_app(db_path))
    assert len(c.get("/api/posts?limit=5").json()) == 5


def test_posts_limit_capped_at_500(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    agent = create_random_agent()
    AgentRepo(db_path).save(agent)
    for _ in range(10):
        PostRepo(db_path).save(Post(
            id=str(uuid.uuid4()), agent_id=agent.id, topic="t",
            caption="c", image_path=None, ig_post_id=None,
            quality_score=None,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
    c = TestClient(create_app(db_path))
    # limit=1000이어도 실제 데이터(10개)만큼만 반환되는지 확인 (500 cap 검증)
    resp = c.get("/api/posts?limit=1000")
    assert resp.status_code == 200
    assert len(resp.json()) == 10  # 데이터가 10개뿐이므로 10개
```

- [ ] **Step 4: 실패 확인**

```bash
pytest tests/test_web.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.web'`

- [ ] **Step 5: src/web/__init__.py 생성**

```python
# src/web/__init__.py
# (빈 파일)
```

- [ ] **Step 6: src/web/app.py 구현**

```python
# src/web/app.py
import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.db.repository import AgentRepo, PostRepo


def _get_stats(db_path: str) -> dict:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM agents),
                (SELECT COUNT(*) FROM posts),
                (SELECT COUNT(*) FROM interactions),
                (SELECT COUNT(*) FROM posts WHERE ig_post_id IS NOT NULL),
                (SELECT AVG(quality_score) FROM posts WHERE quality_score IS NOT NULL)
            """
        ).fetchone()
    return {
        "agent_count": row[0],
        "post_count": row[1],
        "interaction_count": row[2],
        "ig_published": row[3],
        "avg_quality": round(row[4], 3) if row[4] is not None else None,
    }


def create_app(db_path: str) -> FastAPI:
    app = FastAPI(title="agent-instagram dashboard")

    @app.get("/api/stats")
    def stats():
        return JSONResponse(_get_stats(db_path))

    @app.get("/api/agents")
    def agents():
        return JSONResponse(AgentRepo(db_path).list_with_counts())

    @app.get("/api/posts")
    def posts(limit: int = 50):
        limit = min(limit, 500)
        items = PostRepo(db_path).get_recent(limit)
        return JSONResponse([
            {
                "id": p.id,
                "agent_id": p.agent_id,
                "topic": p.topic,
                "caption": p.caption,
                "quality_score": p.quality_score,
                "ig_post_id": p.ig_post_id,
                "created_at": p.created_at,
            }
            for p in items
        ])

    return app
```

- [ ] **Step 7: 테스트 통과 확인**

```bash
pytest tests/test_web.py -v
```
Expected: 6개 PASS

- [ ] **Step 8: 전체 테스트 확인**

```bash
pytest tests/ -q
```
Expected: 51 + 6 = 57개 통과

- [ ] **Step 9: 커밋**

```bash
git add src/web/__init__.py src/web/app.py tests/test_web.py requirements.txt
git commit -m "feat: FastAPI web app with /api/stats, /api/agents, /api/posts"
```

---

## Task 3: Jinja2 HTML 대시보드

**Files:**
- Create: `src/web/templates/base.html`
- Create: `src/web/templates/index.html`
- Modify: `src/web/app.py` (GET / 라우트 추가, Jinja2 설정)

**Interfaces:**
- Consumes: `GET /api/stats`, `GET /api/agents`, `GET /api/posts` (htmx가 클라이언트에서 호출)
- Produces: `GET /` → HTML 페이지 (htmx로 10초마다 자동 갱신)

- [ ] **Step 1: templates 디렉토리 생성 확인**

```bash
mkdir -p src/web/templates
```

- [ ] **Step 2: base.html 작성**

```html
<!-- src/web/templates/base.html -->
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>agent-instagram dashboard</title>
  <script src="https://unpkg.com/htmx.org@2.0.0"></script>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
    h1 { font-size: 1.5rem; margin-bottom: 1.5rem; }
    h2 { font-size: 1.1rem; margin: 1.5rem 0 0.75rem; border-bottom: 1px solid #e5e5e5; padding-bottom: 0.25rem; }
    .cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
    .card { background: #f5f5f5; border-radius: 8px; padding: 1rem 1.5rem; min-width: 140px; }
    .card .label { font-size: 0.75rem; color: #666; }
    .card .value { font-size: 1.75rem; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th { text-align: left; padding: 0.5rem; background: #f5f5f5; }
    td { padding: 0.5rem; border-bottom: 1px solid #eee; }
    .badge { display: inline-block; padding: 0.1em 0.5em; border-radius: 4px; font-size: 0.75rem; }
    .badge.ig { background: #e040fb22; color: #7b1fa2; }
    .badge.evolved { background: #4caf5022; color: #2e7d32; }
  </style>
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: index.html 작성**

```html
<!-- src/web/templates/index.html -->
{% extends "base.html" %}
{% block content %}
<h1>agent-instagram dashboard</h1>

<div id="stats-section"
     hx-get="/partials/stats"
     hx-trigger="load, every 10s"
     hx-swap="outerHTML">
  <p>로딩 중...</p>
</div>

<div id="agents-section"
     hx-get="/partials/agents"
     hx-trigger="load, every 10s"
     hx-swap="outerHTML">
</div>

<div id="posts-section"
     hx-get="/partials/posts"
     hx-trigger="load, every 10s"
     hx-swap="outerHTML">
</div>
{% endblock %}
```

- [ ] **Step 4: src/web/app.py에 HTML 라우트와 파셜 추가**

`src/web/app.py`를 아래와 같이 교체:

```python
# src/web/app.py
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.db.repository import AgentRepo, PostRepo

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_stats(db_path: str) -> dict:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM agents),
                (SELECT COUNT(*) FROM posts),
                (SELECT COUNT(*) FROM interactions),
                (SELECT COUNT(*) FROM posts WHERE ig_post_id IS NOT NULL),
                (SELECT AVG(quality_score) FROM posts WHERE quality_score IS NOT NULL)
            """
        ).fetchone()
    return {
        "agent_count": row[0],
        "post_count": row[1],
        "interaction_count": row[2],
        "ig_published": row[3],
        "avg_quality": round(row[4], 3) if row[4] is not None else None,
    }


def create_app(db_path: str) -> FastAPI:
    app = FastAPI(title="agent-instagram dashboard")
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/partials/stats", response_class=HTMLResponse)
    def partial_stats(request: Request):
        s = _get_stats(db_path)
        avg = f"{s['avg_quality']:.3f}" if s["avg_quality"] is not None else "—"
        html = f"""
        <div id="stats-section" hx-get="/partials/stats" hx-trigger="every 10s" hx-swap="outerHTML">
          <h2>통계</h2>
          <div class="cards">
            <div class="card"><div class="label">에이전트</div><div class="value">{s['agent_count']}</div></div>
            <div class="card"><div class="label">전체 포스트</div><div class="value">{s['post_count']}</div></div>
            <div class="card"><div class="label">인터랙션</div><div class="value">{s['interaction_count']}</div></div>
            <div class="card"><div class="label">IG 게시</div><div class="value">{s['ig_published']}</div></div>
            <div class="card"><div class="label">평균 품질</div><div class="value">{avg}</div></div>
          </div>
        </div>"""
        return HTMLResponse(html)

    @app.get("/partials/agents", response_class=HTMLResponse)
    def partial_agents(request: Request):
        rows = AgentRepo(db_path).list_with_counts()
        rows_html = "".join(
            f"<tr><td>{r['name']}</td><td>{r['age']}</td>"
            f"<td>{r['post_count']}</td><td>{r['follower_count']}</td>"
            f"<td>{'<span class=\"badge evolved\">진화</span>' if r['evolved'] else '—'}</td></tr>"
            for r in rows
        )
        html = f"""
        <div id="agents-section" hx-get="/partials/agents" hx-trigger="every 10s" hx-swap="outerHTML">
          <h2>에이전트 ({len(rows)})</h2>
          <table>
            <thead><tr><th>이름</th><th>나이</th><th>포스트</th><th>팔로워</th><th>상태</th></tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>"""
        return HTMLResponse(html)

    @app.get("/partials/posts", response_class=HTMLResponse)
    def partial_posts(request: Request):
        items = PostRepo(db_path).get_recent(limit=30)
        rows_html = "".join(
            f"<tr><td>{p.agent_id[:8]}…</td><td>{p.topic}</td>"
            f"<td style='max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{p.caption[:80]}</td>"
            f"<td>{f'{p.quality_score:.2f}' if p.quality_score is not None else '—'}</td>"
            f"<td>{'<span class=\"badge ig\">IG</span>' if p.ig_post_id else '—'}</td>"
            f"<td>{p.created_at[:16]}</td></tr>"
            for p in items
        )
        html = f"""
        <div id="posts-section" hx-get="/partials/posts" hx-trigger="every 10s" hx-swap="outerHTML">
          <h2>최근 포스트 (최대 30)</h2>
          <table>
            <thead><tr><th>에이전트</th><th>토픽</th><th>캡션</th><th>품질</th><th>IG</th><th>시각</th></tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>"""
        return HTMLResponse(html)

    @app.get("/api/stats")
    def stats():
        return JSONResponse(_get_stats(db_path))

    @app.get("/api/agents")
    def agents():
        return JSONResponse(AgentRepo(db_path).list_with_counts())

    @app.get("/api/posts")
    def posts(limit: int = 50):
        limit = min(limit, 500)
        items = PostRepo(db_path).get_recent(limit)
        return JSONResponse([
            {
                "id": p.id,
                "agent_id": p.agent_id,
                "topic": p.topic,
                "caption": p.caption,
                "quality_score": p.quality_score,
                "ig_post_id": p.ig_post_id,
                "created_at": p.created_at,
            }
            for p in items
        ])

    return app
```

- [ ] **Step 5: HTML 라우트 테스트 추가**

`tests/test_web.py` 하단에 추가:

```python
def test_index_returns_html(client):
    c, _ = client
    resp = c.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "agent-instagram" in resp.text


def test_partial_stats_returns_html(client):
    c, _ = client
    resp = c.get("/partials/stats")
    assert resp.status_code == 200
    assert "통계" in resp.text


def test_partial_agents_returns_html(client):
    c, _ = client
    resp = c.get("/partials/agents")
    assert resp.status_code == 200
    assert "에이전트" in resp.text


def test_partial_posts_returns_html(client):
    c, _ = client
    resp = c.get("/partials/posts")
    assert resp.status_code == 200
    assert "포스트" in resp.text
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
pytest tests/test_web.py -v
```
Expected: 10개 PASS

- [ ] **Step 7: 커밋**

```bash
git add src/web/app.py src/web/templates/ tests/test_web.py
git commit -m "feat: Jinja2 HTML dashboard with htmx auto-refresh partials"
```

---

## Task 4: CLI web 서브커맨드

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `create_app(db_path)`, `uvicorn.run`
- Produces:
  - `python main.py simulate --agents 5 --db data/sim.db --interval 300` — 기존 동작
  - `python main.py web --port 8000 --db data/sim.db` — 웹 서버 실행

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_web.py 하단에 추가
import subprocess
import sys


def test_main_web_help():
    result = subprocess.run(
        [sys.executable, "main.py", "web", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--port" in result.stdout


def test_main_simulate_help():
    result = subprocess.run(
        [sys.executable, "main.py", "simulate", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--agents" in result.stdout
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_web.py::test_main_web_help tests/test_web.py::test_main_simulate_help -v
```
Expected: FAIL (서브커맨드 없음)

- [ ] **Step 3: main.py 수정**

기존 `main.py`를 아래로 교체:

```python
# main.py
import argparse
import os

from dotenv import load_dotenv

load_dotenv()


def _simulate(args):
    from src.scheduler import run_simulation
    run_simulation(
        n_agents=args.agents,
        db_path=args.db,
        image_dir=args.images,
        interval_seconds=args.interval,
    )


def _web(args):
    import uvicorn
    from src.web.app import create_app
    app = create_app(args.db)
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def main():
    parser = argparse.ArgumentParser(description="agent-instagram")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sim = subparsers.add_parser("simulate", help="시뮬레이션 실행")
    sim.add_argument("--agents", type=int, default=5)
    sim.add_argument("--db", default=os.environ.get("DB_PATH", "data/simulation.db"))
    sim.add_argument("--images", default=os.environ.get("IMAGE_DIR", "images"))
    sim.add_argument("--interval", type=int, default=300)

    web = subparsers.add_parser("web", help="웹 대시보드 실행")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--db", default=os.environ.get("DB_PATH", "data/simulation.db"))

    args = parser.parse_args()
    if args.command == "simulate":
        _simulate(args)
    else:
        _web(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_web.py -v
```
Expected: 12개 PASS

- [ ] **Step 5: 전체 테스트 확인**

```bash
pytest tests/ -q
```
Expected: 51 + 12 = 63개 통과

- [ ] **Step 6: 커밋**

```bash
git add main.py tests/test_web.py
git commit -m "feat: add simulate/web subcommands to main.py"
```

---

## Task 5: CI/CD + Fly.io

**Files:**
- Create: `Dockerfile`
- Create: `fly.toml`
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/deploy.yml`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: `python main.py web --port 8000`, `python main.py simulate`
- Produces:
  - PR push → GitHub Actions에서 pytest + ruff 자동 실행
  - main push → Fly.io 자동 배포
  - `fly deploy` 성공 시 `https://<app-name>.fly.dev` 에서 대시보드 접근

> **사전 조건 (수동 설정 필요):**
> 1. `fly launch --no-deploy` 또는 `fly apps create agent-instagram`으로 앱 생성
> 2. `fly volumes create agent_instagram_data --size 1 --region nrt`으로 Volume 생성
> 3. `fly secrets set ANTHROPIC_API_KEY=... OPENAI_API_KEY=...` (시뮬레이션 실행 시 필요)
> 4. GitHub repository settings → Secrets → `FLY_API_TOKEN` = `fly tokens create deploy` 결과값

- [ ] **Step 1: .dockerignore 작성**

```
# .dockerignore
.git
.claude
.github
__pycache__
*.pyc
*.pyo
.env
.env.*
data/
images/
*.db
*.db-wal
*.db-shm
tests/
docs/
```

- [ ] **Step 2: Dockerfile 작성**

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY main.py .

RUN mkdir -p data images

ENV PYTHONPATH=/app
ENV DB_PATH=/data/simulation.db

EXPOSE 8000

CMD ["python", "main.py", "web", "--port", "8000", "--db", "/data/simulation.db"]
```

- [ ] **Step 3: fly.toml 작성**

```toml
# fly.toml
app = "agent-instagram"
primary_region = "nrt"

[build]

[env]
  PORT = "8000"
  DB_PATH = "/data/simulation.db"

[mounts]
  source = "agent_instagram_data"
  destination = "/data"

[processes]
  web = "python main.py web --port 8000 --db /data/simulation.db"
  worker = "python main.py simulate --agents 5 --interval 300 --db /data/simulation.db"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ["web"]

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
  processes = ["web", "worker"]
```

- [ ] **Step 4: test.yml 작성**

```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Lint (ruff)
        run: ruff check src/ tests/

      - name: Test (pytest)
        run: pytest tests/ -q
```

- [ ] **Step 5: deploy.yml 작성**

```yaml
# .github/workflows/deploy.yml
name: Deploy to Fly.io

on:
  push:
    branches: [main]

jobs:
  test:
    uses: ./.github/workflows/test.yml

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: superfly/flyctl-actions/setup-flyctl@master

      - name: Deploy
        run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

- [ ] **Step 6: Docker 빌드 로컬 검증**

```bash
docker build -t agent-instagram-test .
docker run --rm -p 8000:8000 agent-instagram-test
# 브라우저에서 http://localhost:8000 확인 후 Ctrl+C
```

Expected: 대시보드 HTML 응답 (DB가 없어도 빈 통계 페이지 표시)

- [ ] **Step 7: ruff 검사 통과**

```bash
ruff check src/ tests/
```
Expected: 오류 없음 (있으면 `ruff check --fix src/ tests/`로 자동 수정)

- [ ] **Step 8: 전체 테스트 확인**

```bash
pytest tests/ -q
```
Expected: 63개 통과

- [ ] **Step 9: 커밋**

```bash
git add Dockerfile fly.toml .dockerignore .github/
git commit -m "feat: add Dockerfile, fly.toml, GitHub Actions CI/CD"
```

---

## Execution Handoff

이 계획은 다음 5개 태스크로 구성된다:

| Task | 산출물 | 테스트 |
|------|--------|--------|
| 1 | DB 확장 + WAL | 3개 추가 (51개) |
| 2 | REST API | 6개 추가 (57개) |
| 3 | HTML 대시보드 | 4개 추가 (61개) |
| 4 | CLI 서브커맨드 | 2개 추가 (63개) |
| 5 | CI/CD + Fly.io | Docker 빌드 검증 |

> **Fly.io 배포 사전 조건 (Task 5 이후 수동 실행):**
>
> ```bash
> fly apps create agent-instagram
> fly volumes create agent_instagram_data --size 1 --region nrt
> fly secrets set ANTHROPIC_API_KEY=<your-key> OPENAI_API_KEY=<your-key>
> # GitHub Secrets에 FLY_API_TOKEN 추가
> fly tokens create deploy
> ```

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
        return templates.TemplateResponse(request=request, name="index.html")

    @app.get("/partials/stats", response_class=HTMLResponse)
    def partial_stats():
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
    def partial_agents():
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
    def partial_posts():
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

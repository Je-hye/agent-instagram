import json
import sqlite3
from datetime import datetime, timezone

from src.models import Aesthetic, Agent, Personality, Post


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

    def get_recent(self, limit: int = 50) -> list[Post]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Post(*r) for r in rows]

    def get_unscored(self) -> list[Post]:
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

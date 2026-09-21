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

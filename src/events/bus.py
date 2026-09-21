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

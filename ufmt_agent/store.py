from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from .models import Delivery


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS deliveries (
                source_id TEXT PRIMARY KEY, course TEXT NOT NULL, title TEXT NOT NULL,
                source_url TEXT NOT NULL, due_at TEXT, all_day INTEGER NOT NULL,
                raw_text TEXT NOT NULL, google_event_id TEXT, status TEXT NOT NULL DEFAULT 'active',
                first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
                reminders TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
                outcome TEXT NOT NULL, detail TEXT
            );
        """)
        # Bancos criados antes dos lembretes continuam compatíveis.
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(deliveries)")}
        if "reminders" not in columns:
            self.conn.execute("ALTER TABLE deliveries ADD COLUMN reminders TEXT NOT NULL DEFAULT ''")
        self.conn.commit()

    def get(self, source_id: str):
        return self.conn.execute("SELECT * FROM deliveries WHERE source_id = ?", (source_id,)).fetchone()

    def save_delivery(self, delivery: Delivery, event_id: str, status: str = "active", reminder_minutes: tuple[int, ...] = ()) -> None:
        due = delivery.due_at.isoformat() if delivery.due_at else None
        reminders = ",".join(map(str, reminder_minutes))
        self.conn.execute("""
            INSERT INTO deliveries(source_id, course, title, source_url, due_at, all_day, raw_text, google_event_id, status, first_seen_at, last_seen_at, reminders)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET course=excluded.course, title=excluded.title,
              source_url=excluded.source_url, due_at=excluded.due_at, all_day=excluded.all_day,
              raw_text=excluded.raw_text, google_event_id=excluded.google_event_id, status=excluded.status,
              last_seen_at=excluded.last_seen_at, reminders=excluded.reminders
        """, (delivery.source_id, delivery.course, delivery.title, delivery.source_url, due, int(delivery.all_day), delivery.raw_text, event_id, status, now(), now(), reminders))
        self.conn.commit()

    @staticmethod
    def matches(row, delivery: Delivery, reminder_minutes: tuple[int, ...] = ()) -> bool:
        """Indica se o evento remoto já representa o prazo coletado."""
        return bool(row) and (
            row["course"], row["title"], row["source_url"], row["due_at"], bool(row["all_day"]), row["raw_text"], row["status"], row["reminders"]
        ) == (
            delivery.course, delivery.title, delivery.source_url,
            delivery.due_at.isoformat() if delivery.due_at else None,
            delivery.all_day, delivery.raw_text, "active", ",".join(map(str, reminder_minutes)),
        )

    def mark_missing(self, seen_ids: set[str]):
        active = self.conn.execute("SELECT * FROM deliveries WHERE status = 'active'").fetchall()
        missing = [row for row in active if row["source_id"] not in seen_ids]
        for row in missing:
            self.conn.execute("UPDATE deliveries SET status = 'missing', last_seen_at = ? WHERE source_id = ?", (now(), row["source_id"]))
        self.conn.commit()
        return missing

    def begin_run(self) -> int:
        cursor = self.conn.execute("INSERT INTO runs(started_at, outcome) VALUES (?, 'running')", (now(),))
        self.conn.commit()
        return cursor.lastrowid

    def finish_run(self, run_id: int, outcome: str, detail: str = "") -> None:
        self.conn.execute("UPDATE runs SET completed_at=?, outcome=?, detail=? WHERE id=?", (now(), outcome, detail, run_id))
        self.conn.commit()

    def ran_successfully_today(self, timezone_name: str) -> bool:
        today = datetime.now(ZoneInfo(timezone_name)).date().isoformat()
        rows = self.conn.execute("SELECT completed_at FROM runs WHERE outcome = 'success' AND completed_at IS NOT NULL").fetchall()
        return any(datetime.fromisoformat(row["completed_at"]).astimezone(ZoneInfo(timezone_name)).date().isoformat() == today for row in rows)

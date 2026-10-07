from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Delivery:
    source_id: str
    course: str
    title: str
    source_url: str
    due_at: datetime | None
    all_day: bool
    raw_text: str

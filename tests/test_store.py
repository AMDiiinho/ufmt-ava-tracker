from datetime import datetime

from ufmt_agent.models import Delivery
from ufmt_agent.store import Store


def test_marks_unseen_delivery_missing(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    delivery = Delivery("moodle:1", "Disciplina", "Entrega", "https://x?id=1", datetime(2026, 10, 4), True, "Prazo")
    store.save_delivery(delivery, "event-1")
    missing = store.mark_missing(set())
    assert [row["source_id"] for row in missing] == ["moodle:1"]
    assert store.get("moodle:1")["status"] == "missing"

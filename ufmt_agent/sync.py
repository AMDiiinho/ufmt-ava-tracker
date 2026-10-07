from __future__ import annotations

from .browser_ava import BrowserAvaClient
from .calendar import CalendarClient
from .config import Settings
from .notify import notify
from .store import Store


def synchronize(settings: Settings) -> dict[str, int]:
    store = Store(settings.database_path)
    run_id = store.begin_run()
    try:
        deliveries = BrowserAvaClient(settings).fetch_deliveries()
        calendar = CalendarClient(settings)
        counts = {"created": 0, "updated": 0, "missing": 0}
        seen = set()
        for delivery in deliveries:
            seen.add(delivery.source_id)
            existing = store.get(delivery.source_id)
            if store.matches(existing, delivery, settings.reminder_minutes):
                continue
            event_id, action = calendar.upsert(delivery, existing["google_event_id"] if existing else None)
            store.save_delivery(delivery, event_id, reminder_minutes=settings.reminder_minutes)
            counts[action] += 1
        missing = store.mark_missing(seen)
        counts["missing"] = len(missing)
        store.finish_run(run_id, "success", str(counts))
        if any(counts.values()):
            notify("UFMT atualizada", f"Novas: {counts['created']}; alteradas: {counts['updated']}; conferir: {counts['missing']}.")
        else:
            notify("UFMT verificada", "Sincronização concluída; nenhuma alteração encontrada.")
        return counts
    except Exception as exc:
        store.finish_run(run_id, "failure", str(exc))
        notify("Falha ao atualizar UFMT", str(exc))
        raise

"""
Google Calendar Sync via Claude Code MCP-Tools.
Wird direkt von Claude Code aufgerufen — nicht standalone ausführbar.
"""
from datetime import datetime, timedelta
from typing import Any

from scraper.parser import Deadline


def build_event_body(deadline: Deadline) -> dict[str, Any]:
    start = deadline.due_date
    end = start + timedelta(hours=1)

    description_parts = [f"Typ: {deadline.type}"]
    if deadline.description:
        description_parts.append(deadline.description)
    if deadline.url:
        description_parts.append(f"LEA: {deadline.url}")

    return {
        "summary": deadline.calendar_title(),
        "description": "\n".join(description_parts),
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": "Europe/Berlin",
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": "Europe/Berlin",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 24 * 60},      # 1 Tag vorher
                {"method": "popup", "minutes": 3 * 24 * 60},  # 3 Tage vorher
            ],
        },
    }


def deadlines_to_sync_instructions(deadlines: list[Deadline]) -> str:
    """Gibt Anweisungen für Claude zurück, welche Events erstellt werden sollen."""
    if not deadlines:
        return "Keine Fristen zum Synchronisieren gefunden."

    lines = ["Folgende Fristen sollen in Google Calendar eingetragen werden:\n"]
    for d in deadlines:
        lines.append(
            f"- {d.calendar_title()}\n"
            f"  Datum: {d.due_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"  Kurs: {d.course}\n"
            f"  URL: {d.url or 'keine'}\n"
        )
    lines.append("\nBitte erstelle für jeden Eintrag ein Google Calendar Event mit:")
    lines.append("- Erinnerung 1 Tag vorher")
    lines.append("- Erinnerung 3 Tage vorher")
    lines.append("- Zeitzone: Europe/Berlin")
    return "\n".join(lines)

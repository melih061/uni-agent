"""Liest den bestehenden Stundenplan und gibt ihn mit aktuellen Fristen zurück."""
from pathlib import Path
from bs4 import BeautifulSoup
from scraper.parser import Deadline

STUNDENPLAN_PATH = Path(__file__).parent / "stundenplan.html"


def get_upcoming_deadlines_html(deadlines: list[Deadline], days: int = 14) -> str:
    upcoming = [d for d in deadlines if d.is_upcoming(days)]
    if not upcoming:
        return "<p>Keine anstehenden Fristen in den nächsten 14 Tagen.</p>"

    items = "".join(
        f"<li><strong>{d.due_date.strftime('%d.%m.%Y')}</strong> — "
        f"[{d.course}] {d.type}: {d.title} "
        f"({d.days_remaining()} Tage)</li>"
        for d in upcoming
    )
    return f"<ul>{items}</ul>"


def inject_deadlines_into_stundenplan(deadlines: list[Deadline]) -> str:
    if not STUNDENPLAN_PATH.exists():
        raise FileNotFoundError(f"Stundenplan nicht gefunden: {STUNDENPLAN_PATH}")

    html = STUNDENPLAN_PATH.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    deadlines_section = soup.find(id="aktuelle-fristen")
    if deadlines_section:
        deadlines_section.clear()
        deadlines_section.append(
            BeautifulSoup(get_upcoming_deadlines_html(deadlines), "lxml").body
        )

    return str(soup)

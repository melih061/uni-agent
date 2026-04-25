import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from scraper.parser import Deadline

ANALYSIS_URL = "https://www2.inf.h-brs.de/~pbecke2m/analysis/"

GERMAN_MONTHS_SHORT = {
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "10": 10, "11": 11, "12": 12,
}


def _parse_short_date(day: str, month: str, year: int, hour: int = 23, minute: int = 59) -> Optional[datetime]:
    try:
        return datetime(year, int(month.rstrip(".")), int(day.rstrip(".")), hour, minute)
    except ValueError:
        return None


def scrape_analysis_deadlines() -> list[Deadline]:
    """Scrapt ACAT-Testfenster von der Analysis-Seite (kein Login nötig)."""
    deadlines: list[Deadline] = []

    response = httpx.get(ANALYSIS_URL, timeout=15, follow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    # Testfenster: "1.5. bis 10.5.2026" in <ol> unter "Termine"
    for li in soup.select("ol li"):
        text = li.get_text(strip=True)
        # Format: "1.5. bis 10.5.2026" oder "1.5. bis 10.5.2026"
        m = re.match(r"(\d{1,2})\.(\d{1,2})\.\s*bis\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if not m:
            continue
        end_day, end_month, year = m.group(3), m.group(4), int(m.group(5))
        due_date = _parse_short_date(end_day, end_month, year, hour=23, minute=59)
        if due_date:
            start_day, start_month = m.group(1), m.group(2)
            deadlines.append(Deadline(
                course="Analysis",
                title=f"ACAT-Testfenster (ab {start_day}.{start_month}.)",
                due_date=due_date,
                type="Abgabe",
                url=ANALYSIS_URL,
            ))

    return deadlines

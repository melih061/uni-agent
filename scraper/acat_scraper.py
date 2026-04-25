import asyncio
import os
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

from scraper.parser import Deadline

load_dotenv()

ACAT_LOGIN_URL = "https://adgt.acat.inf.h-brs.de/exercises"

GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
    "jan": 1, "feb": 2, "mär": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}


def _parse_date(text: str) -> Optional[datetime]:
    import re
    # DD.MM.YYYY HH:MM
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?", text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)),
                            int(m.group(4) or 23), int(m.group(5) or 59))
        except ValueError:
            pass
    # "10. Mai 2026"
    m = re.search(r"(\d{1,2})\.\s*(\w+)\s+(\d{4})(?:\s+(\d{2}):(\d{2}))?", text)
    if m:
        month = GERMAN_MONTHS.get(m.group(2).lower()[:3])
        if month:
            try:
                return datetime(int(m.group(3)), month, int(m.group(1)),
                                int(m.group(4) or 23), int(m.group(5) or 59))
            except ValueError:
                pass
    return None


async def _login(page: Page, email: str, password: str) -> bool:
    await page.goto(ACAT_LOGIN_URL, wait_until="domcontentloaded")
    await asyncio.sleep(1)
    email_input = await page.query_selector('input[type="email"], input[name*="email"], input[name*="user"]')
    pass_input = await page.query_selector('input[type="password"]')
    if not email_input or not pass_input:
        return False
    await email_input.fill(email)
    await pass_input.fill(password)
    await page.click('button[type="submit"], input[type="submit"]')
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(1)
    return "login" not in page.url.lower() or await page.query_selector(".exercise, .assignment, [class*=exercise]") is not None


async def scrape_acat_deadlines(headless: bool = True) -> list[Deadline]:
    """Scrapt Abgabe-Deadlines von ACAT für ADS und Analysis."""
    email = os.getenv("ACAT_EMAIL")
    password = os.getenv("ACAT_PASSWORD")
    if not email or not password or email.startswith("HIER"):
        print("  ACAT: Credentials nicht gesetzt — übersprungen")
        return []

    deadlines: list[Deadline] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()

        logged_in = await _login(page, email, password)
        if not logged_in:
            print("  ACAT: Login fehlgeschlagen — Credentials prüfen")
            await browser.close()
            return []

        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(1)
        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        await browser.close()

    # Exercises mit Deadlines parsen — generisch über alle Textelemente
    for item in soup.select("[class*=exercise], [class*=assignment], li, tr"):
        text = item.get_text(" ", strip=True)
        due_date = _parse_date(text)
        if not due_date:
            continue
        title_el = item.select_one("a, h3, h4, strong, .title, [class*=title]")
        title = title_el.get_text(strip=True) if title_el else text[:60]
        if len(title) < 3 or due_date.year < 2026:
            continue
        deadlines.append(Deadline(
            course="Algorithmen & Datenstrukturen",
            title=title,
            due_date=due_date,
            type="Abgabe",
            url=ACAT_LOGIN_URL,
        ))

    return deadlines

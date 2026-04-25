import asyncio
import os
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, Browser

from scraper.parser import Deadline

load_dotenv()

LEA_LOGIN_URL = "https://lea.hochschule-bonn-rhein-sieg.de/login.php?cmd=force_login"
LEA_BASE_URL = "https://lea.hochschule-bonn-rhein-sieg.de"


async def _login(page: Page, username: str, password: str) -> bool:
    await page.goto(LEA_LOGIN_URL, wait_until="domcontentloaded")
    await page.wait_for_selector('input[type="password"]', timeout=15000)
    await page.fill('input[name*="input_4"]', username)
    await page.fill('input[type="password"]', password)
    # Login-Formular hat Button ohne type — via action-URL des Formulars identifizieren
    await page.click('form[action*="doStandardAuthentication"] button')
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(1)
    return "ilDashboardGUI" in page.url or "logout" in page.url or await page.query_selector("#il_mhead_t_focus") is not None


async def _get_course_links(page: Page) -> list[dict]:
    await page.goto(f"{LEA_BASE_URL}/ilias.php?baseClass=ilmembershipoverviewgui", wait_until="domcontentloaded")
    await asyncio.sleep(2)
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")

    courses = []
    seen: set[str] = set()
    for link in soup.select("a[href*='goto.php/crs/'], a[href*='goto.php?target=crs']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or len(title) < 4:
            continue
        # Nur aktuelles Semester
        if "2026 SS" not in title and "2026 ss" not in title.lower():
            continue
        url = href if href.startswith("http") else f"{LEA_BASE_URL}/{href.lstrip('/')}"
        if url not in seen:
            seen.add(url)
            # Titelbereinigung: "2026 SS - Datenbanken" → "Datenbanken"
            clean_title = title.split(" - ", 1)[-1].strip() if " - " in title else title
            courses.append({"title": clean_title, "url": url})

    return courses


GERMAN_MONTHS = {
    "jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "mai": 5,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}


def _extract_end_date(text: str) -> Optional[datetime]:
    """Parst das Enddatum aus 'Verfügbarkeit: DD. Mon YYYY, HH:MM - DD. Mon YYYY, HH:MM'."""
    import re
    # Nur wenn ein echtes Enddatum vorhanden ist (kein 'Kein Datum')
    if "Kein Datum" in text or " - " not in text:
        return None
    # Alles nach dem letzten " - " ist das Enddatum
    end_part = text.rsplit(" - ", 1)[-1].strip()
    # Format: "25. Mai 2026, 05:30"
    m = re.search(
        r"(\d{1,2})\.\s*(\w+)\s+(\d{4})(?:,\s*(\d{2}):(\d{2}))?",
        end_part
    )
    if not m:
        return None
    day, month_str, year = int(m.group(1)), m.group(2).lower()[:3], int(m.group(3))
    month = GERMAN_MONTHS.get(month_str)
    if not month:
        return None
    hour = int(m.group(4)) if m.group(4) else 23
    minute = int(m.group(5)) if m.group(5) else 59
    try:
        return datetime(year, month, day, hour, minute)
    except ValueError:
        return None


async def _parse_items(soup: BeautifulSoup, course: dict) -> list[Deadline]:
    deadlines = []
    for item in soup.select(".ilContainerListItemOuter"):
        title_el = item.select_one(".il_ContainerItemTitle a")
        if not title_el:
            continue
        item_title = title_el.get_text(strip=True)
        item_url = title_el.get("href", "")
        if item_url and not item_url.startswith("http"):
            item_url = f"{LEA_BASE_URL}/{item_url.lstrip('/')}"

        # Verfügbarkeit-Property nach Enddatum durchsuchen
        for prop in item.select(".il_ItemProperty"):
            prop_text = prop.get_text(" ", strip=True)
            if "Verfügbarkeit" not in prop_text:
                continue
            due_date = _extract_end_date(prop_text)
            if due_date:
                deadlines.append(Deadline(
                    course=course["title"],
                    title=item_title,
                    due_date=due_date,
                    type=_classify_type(item_title),
                    url=item_url,
                ))
    return deadlines


async def _scrape_course_deadlines(page: Page, course: dict) -> list[Deadline]:
    deadlines: list[Deadline] = []
    try:
        await page.goto(course["url"], wait_until="domcontentloaded")
        await asyncio.sleep(1)
        soup = BeautifulSoup(await page.content(), "lxml")
        deadlines.extend(await _parse_items(soup, course))

        # Eine Ebene tiefer: Ordner-Links auf der Kursseite besuchen
        folder_links: list[str] = []
        for a in soup.select("a[href*='/fold/']"):
            href = a.get("href", "")
            url = href if href.startswith("http") else f"{LEA_BASE_URL}/{href.lstrip('/')}"
            if url not in folder_links:
                folder_links.append(url)

        for folder_url in folder_links[:8]:  # max 8 Unterordner pro Kurs
            try:
                await page.goto(folder_url, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                sub_soup = BeautifulSoup(await page.content(), "lxml")
                deadlines.extend(await _parse_items(sub_soup, course))
            except Exception:
                continue

    except Exception:
        pass

    return deadlines


def _extract_date(text: str) -> Optional[datetime]:
    import re
    patterns = [
        r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})",
        r"(\d{2})\.(\d{2})\.(\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 5:
                    return datetime(int(groups[2]), int(groups[1]), int(groups[0]),
                                    int(groups[3]), int(groups[4]))
                else:
                    return datetime(int(groups[2]), int(groups[1]), int(groups[0]))
            except ValueError:
                continue
    return None


def _classify_type(title: str) -> str:
    title_lower = title.lower()
    if any(w in title_lower for w in ["klausur", "prüfung", "exam"]):
        return "Klausur"
    if any(w in title_lower for w in ["quiz", "test"]):
        return "Quiz"
    if any(w in title_lower for w in ["abgabe", "aufgabe", "hausaufgabe", "übung", "assignment"]):
        return "Abgabe"
    return "Übung"


async def scrape_all_deadlines(headless: bool = True) -> list[Deadline]:
    username = os.getenv("LEA_USERNAME")
    password = os.getenv("LEA_PASSWORD")

    if not username or not password:
        raise EnvironmentError("LEA_USERNAME und LEA_PASSWORD müssen in .env gesetzt sein")

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()

        logged_in = await _login(page, username, password)
        if not logged_in:
            await browser.close()
            raise RuntimeError("LEA Login fehlgeschlagen — Credentials prüfen")

        courses = await _get_course_links(page)
        print(f"  {len(courses)} Kurse gefunden")

        all_deadlines: list[Deadline] = []
        for course in courses:
            course_deadlines = await _scrape_course_deadlines(page, course)
            all_deadlines.extend(course_deadlines)
            if course_deadlines:
                print(f"  {course['title']}: {len(course_deadlines)} Frist(en)")

        await browser.close()

    return sorted(all_deadlines, key=lambda d: d.due_date)


if __name__ == "__main__":
    deadlines = asyncio.run(scrape_all_deadlines(headless=False))
    for d in deadlines:
        print(d)

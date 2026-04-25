"""
Scrapt vollständigen LEA-Kontext pro Kurs:
- Ankündigungen (Nachrichtenforums-Posts)
- Neue Materialien / Uploads
- Übungsblätter mit Verfügbarkeit
"""
import asyncio
import os
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

load_dotenv()

LEA_LOGIN_URL = "https://lea.hochschule-bonn-rhein-sieg.de/login.php?cmd=force_login"
LEA_BASE_URL  = "https://lea.hochschule-bonn-rhein-sieg.de"

IGNORED_COURSES = {
    "WI-Modellierung", "Modellierung betrieblicher Informationssysteme",
    "Programmierung 2", "Programmierung, Algorithmen und Datenstrukturen",
    "Einführung in das IT-Recht",
}

FORUM_KEYWORDS  = {"nachricht", "neuigkeit", "ankündigung", "news", "forum"}
MATERIAL_TYPES  = {"pdf", "zip", "pptx", "docx", "xlsx", "mp4", "py", "ipynb"}


@dataclass
class CourseContext:
    course: str
    announcements: list[str] = field(default_factory=list)   # letzte Forenbeiträge
    materials: list[str]     = field(default_factory=list)   # neue Dateien
    exercises: list[str]     = field(default_factory=list)   # Aufgaben mit Verfügbarkeit

    def to_text(self) -> str:
        parts = [f"=== {self.course} ==="]
        if self.announcements:
            parts.append("Ankündigungen:")
            parts.extend(f"  • {a}" for a in self.announcements[:5])
        if self.exercises:
            parts.append("Aufgaben / Verfügbarkeit:")
            parts.extend(f"  • {e}" for e in self.exercises[:8])
        if self.materials:
            parts.append("Neue Materialien:")
            parts.extend(f"  • {m}" for m in self.materials[:6])
        return "\n".join(parts)


async def _login(page: Page, username: str, password: str) -> bool:
    await page.goto(LEA_LOGIN_URL, wait_until="domcontentloaded")
    await page.wait_for_selector('input[type="password"]', timeout=15000)
    await page.fill('input[name*="input_4"]', username)
    await page.fill('input[type="password"]', password)
    await page.click('form[action*="doStandardAuthentication"] button')
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(1)
    return "ilDashboardGUI" in page.url


async def _scrape_forum(page: Page, url: str) -> list[str]:
    """Holt die letzten Beiträge aus einem ILIAS-Forum."""
    posts: list[str] = []
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(1)
        soup = BeautifulSoup(await page.content(), "lxml")
        for row in soup.select(".ilForum .ilListItem, .ilForumPost, tr.ilObjForumPostRow")[:5]:
            text = row.get_text(" ", strip=True)
            if len(text) > 20:
                posts.append(text[:200])
        if not posts:
            # Fallback: Tabellenzeilen
            for row in soup.select("table tr")[1:6]:
                text = row.get_text(" ", strip=True)
                if len(text) > 20:
                    posts.append(text[:200])
    except Exception:
        pass
    return posts


async def _scrape_course(page: Page, course: dict) -> CourseContext:
    ctx = CourseContext(course=course["title"])
    try:
        await page.goto(course["url"], wait_until="domcontentloaded")
        await asyncio.sleep(1)
        soup = BeautifulSoup(await page.content(), "lxml")
        items = soup.select(".ilContainerListItemOuter")

        forum_urls: list[str] = []

        for item in items:
            title_el = item.select_one(".il_ContainerItemTitle a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href  = title_el.get("href", "")
            url   = href if href.startswith("http") else f"{LEA_BASE_URL}/{href.lstrip('/')}"
            props = [p.get_text(strip=True) for p in item.select(".il_ItemProperty")]

            # Foren sammeln
            if any(kw in title.lower() for kw in FORUM_KEYWORDS) or "/frm/" in href:
                forum_urls.append(url)
                continue

            # Materialien (Dateien)
            for prop in props:
                ext = prop.lower().strip(".")
                if ext in MATERIAL_TYPES:
                    date_prop = next((p for p in props if any(c.isdigit() for c in p)), "")
                    ctx.materials.append(f"{title} [{ext}]{' — ' + date_prop if date_prop else ''}")
                    break

            # Aufgaben mit Verfügbarkeit
            for prop in props:
                if "Verfügbarkeit" in prop and "Kein Datum" not in prop:
                    ctx.exercises.append(f"{title}: {prop}")
                    break

        # Unterordner eine Ebene tief durchsuchen
        folder_links = list({
            (f"{LEA_BASE_URL}/{a.get('href','').lstrip('/')}" if not a.get('href','').startswith('http') else a.get('href',''))
            for a in soup.select("a[href*='/fold/']")
        })[:6]

        for folder_url in folder_links:
            try:
                await page.goto(folder_url, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                sub = BeautifulSoup(await page.content(), "lxml")
                for item in sub.select(".ilContainerListItemOuter"):
                    title_el = item.select_one(".il_ContainerItemTitle a")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    props  = [p.get_text(strip=True) for p in item.select(".il_ItemProperty")]
                    href   = title_el.get("href", "")

                    # Foren in Unterordnern
                    if any(kw in title.lower() for kw in FORUM_KEYWORDS) or "/frm/" in href:
                        url = href if href.startswith("http") else f"{LEA_BASE_URL}/{href.lstrip('/')}"
                        forum_urls.append(url)
                        continue

                    for prop in props:
                        ext = prop.lower().strip(".")
                        if ext in MATERIAL_TYPES:
                            date_prop = next((p for p in props if any(c.isdigit() for c in p)), "")
                            ctx.materials.append(f"{title} [{ext}]{' — ' + date_prop if date_prop else ''}")
                            break
                    for prop in props:
                        if "Verfügbarkeit" in prop and "Kein Datum" not in prop:
                            ctx.exercises.append(f"{title}: {prop}")
                            break
            except Exception:
                continue

        # Foren scrapen (max 2 pro Kurs)
        for furl in forum_urls[:2]:
            posts = await _scrape_forum(page, furl)
            ctx.announcements.extend(posts)

    except Exception:
        pass

    return ctx


async def scrape_lea_full_context(headless: bool = True) -> list[CourseContext]:
    username = os.getenv("LEA_USERNAME")
    password = os.getenv("LEA_PASSWORD")
    if not username or not password:
        return []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page    = await browser.new_page()

        if not await _login(page, username, password):
            await browser.close()
            return []

        # Kursliste laden
        from scraper.lea_scraper import _get_course_links
        courses = await _get_course_links(page)
        courses = [c for c in courses if c["title"] not in IGNORED_COURSES]

        results: list[CourseContext] = []
        for course in courses:
            ctx = await _scrape_course(page, course)
            results.append(ctx)
            print(f"  {course['title']}: {len(ctx.announcements)} Ankündigungen, "
                  f"{len(ctx.exercises)} Aufgaben, {len(ctx.materials)} Materialien")

        await browser.close()
    return results

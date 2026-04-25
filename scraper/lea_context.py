"""
Scrapt vollständigen LEA-Kontext pro Kurs:
- Ankündigungen (Forumsbeiträge)
- Materialien (rekursiv bis 3 Ebenen, mit Ordner-Hierarchie)
- Übungsblätter mit Verfügbarkeit
- PDF-Inhalt (authentifizierter Download + Textextraktion, gecacht)
"""
import asyncio
import os
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

load_dotenv()

LEA_BASE_URL = "https://lea.hochschule-bonn-rhein-sieg.de"
LEA_LOGIN_URL = f"{LEA_BASE_URL}/login.php?cmd=force_login"

IGNORED_COURSES = {
    "WI-Modellierung", "Modellierung betrieblicher Informationssysteme",
    "Programmierung 2", "Programmierung, Algorithmen und Datenstrukturen",
    "Einführung in das IT-Recht",
}

FORUM_KEYWORDS = {"nachricht", "neuigkeit", "ankündigung", "news", "forum"}
MATERIAL_TYPES = {"pdf", "zip", "pptx", "docx", "xlsx", "mp4", "py", "ipynb", "ppt", "xls"}

MAX_FILES_PER_COURSE = 10
MAX_CHARS_PER_FILE   = 6000
EXTRACTABLE = {"pdf", "zip"}


@dataclass
class CourseContext:
    course: str
    announcements: list[str]       = field(default_factory=list)
    materials: list[str]           = field(default_factory=list)
    exercises: list[str]           = field(default_factory=list)
    file_contents: list[tuple[str, str]] = field(default_factory=list)  # (title, text)

    def to_text(self) -> str:
        parts = [f"=== {self.course} ==="]
        if self.announcements:
            parts.append("Ankündigungen / Forum:")
            parts.extend(f"  • {a}" for a in self.announcements[:8])
        if self.exercises:
            parts.append("Aufgaben / Übungen:")
            parts.extend(f"  • {e}" for e in self.exercises[:10])
        if self.materials:
            parts.append("Materialien (Dateiliste):")
            parts.extend(f"  • {m}" for m in self.materials[:20])
        if self.file_contents:
            parts.append("Datei-Inhalte (PDFs & ZIPs):")
            for title, text in self.file_contents:
                parts.append(f"\n--- {title} ---")
                parts.append(text[:MAX_CHARS_PER_FILE])
        return "\n".join(parts)


def _abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return f"{LEA_BASE_URL}/{href.lstrip('/')}"


async def _login(page: Page, username: str, password: str) -> bool:
    await page.goto(LEA_LOGIN_URL, wait_until="domcontentloaded")
    await page.wait_for_selector('input[type="password"]', timeout=15000)
    await page.fill('input[name*="input_4"]', username)
    await page.fill('input[type="password"]', password)
    await page.click('form[action*="doStandardAuthentication"] button')
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(1)
    return "ilDashboardGUI" in page.url



async def _fetch_file_text_cached(page: Page, url: str, title: str, ext: str) -> str:
    from scraper.pdf_extractor import fetch_and_extract
    return await fetch_and_extract(page, url, title, ext=ext)


async def _scrape_forum_posts(page: Page, url: str) -> list[str]:
    posts: list[str] = []
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(1)
        soup = BeautifulSoup(await page.content(), "lxml")
        for row in soup.select("table tr")[1:8]:
            cells = row.find_all("td")
            if len(cells) >= 2:
                subject = cells[0].get_text(" ", strip=True)
                meta = cells[-1].get_text(" ", strip=True) if len(cells) > 1 else ""
                if len(subject) > 5:
                    posts.append(f"{subject[:150]} ({meta[:50]})" if meta else subject[:150])
        if not posts:
            for block in soup.select(".ilForumPost, .ilForum .ilListItem")[:6]:
                text = block.get_text(" ", strip=True)
                if len(text) > 10:
                    posts.append(text[:200])
    except Exception:
        pass
    return posts


async def _scrape_folder(
    page: Page,
    url: str,
    ctx: CourseContext,
    file_queue: list[tuple[str, str, str]],
    prefix: str = "",
    depth: int = 0,
    max_depth: int = 2,
) -> None:
    if depth > max_depth:
        return
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(0.8)
        soup = BeautifulSoup(await page.content(), "lxml")

        sub_folders: list[tuple[str, str]] = []
        forum_urls: list[str] = []

        for item in soup.select(".ilContainerListItemOuter"):
            title_el = item.select_one(".il_ContainerItemTitle a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href  = title_el.get("href", "")
            item_url = _abs_url(href)
            props = [p.get_text(strip=True) for p in item.select(".il_ItemProperty")]
            label = f"{prefix}{title}" if prefix else title

            if "/frm/" in href or any(kw in title.lower() for kw in FORUM_KEYWORDS):
                forum_urls.append(item_url)
                continue

            if "/fold/" in href:
                sub_folders.append((label, item_url))
                continue

            if "/exc/" in href:
                avail = next((p for p in props if "Verfügbarkeit" in p), "")
                ctx.exercises.append(f"{label}{' | ' + avail if avail else ''}")
                continue

            for prop in props:
                ext = prop.lower().strip(".")
                if ext in MATERIAL_TYPES:
                    date_prop = next((p for p in props if any(c.isdigit() for c in p) and p != prop), "")
                    ctx.materials.append(f"{label} [{ext}]{' — ' + date_prop if date_prop else ''}")
                    if ext in EXTRACTABLE and len(file_queue) < MAX_FILES_PER_COURSE:
                        file_queue.append((label, item_url, ext))
                    break
            else:
                avail = next((p for p in props if "Verfügbarkeit" in p and "Kein Datum" not in p), "")
                if avail:
                    ctx.exercises.append(f"{label}: {avail}")

        for furl in forum_urls[:2]:
            posts = await _scrape_forum_posts(page, furl)
            ctx.announcements.extend(posts)

        for sub_label, sub_url in sub_folders[:8]:
            await _scrape_folder(page, sub_url, ctx, file_queue,
                                 prefix=f"{sub_label} / ", depth=depth + 1)

    except Exception:
        pass


async def _scrape_course(page: Page, course: dict) -> CourseContext:
    ctx = CourseContext(course=course["title"])
    file_queue: list[tuple[str, str, str]] = []  # (title, url, ext)

    try:
        await page.goto(course["url"], wait_until="domcontentloaded")
        await asyncio.sleep(1)
        soup = BeautifulSoup(await page.content(), "lxml")

        forum_urls: list[str] = []
        folder_items: list[tuple[str, str]] = []

        for item in soup.select(".ilContainerListItemOuter"):
            title_el = item.select_one(".il_ContainerItemTitle a")
            if not title_el:
                continue
            title    = title_el.get_text(strip=True)
            href     = title_el.get("href", "")
            item_url = _abs_url(href)
            props    = [p.get_text(strip=True) for p in item.select(".il_ItemProperty")]

            if "/frm/" in href or any(kw in title.lower() for kw in FORUM_KEYWORDS):
                forum_urls.append(item_url)
            elif "/fold/" in href:
                folder_items.append((title, item_url))
            elif "/exc/" in href:
                avail = next((p for p in props if "Verfügbarkeit" in p and "Kein Datum" not in p), "")
                ctx.exercises.append(f"{title}{': ' + avail if avail else ''}")
            else:
                for prop in props:
                    ext = prop.lower().strip(".")
                    if ext in MATERIAL_TYPES:
                        date_prop = next((p for p in props if any(c.isdigit() for c in p) and p != prop), "")
                        ctx.materials.append(f"{title} [{ext}]{' — ' + date_prop if date_prop else ''}")
                        if ext in EXTRACTABLE and len(file_queue) < MAX_FILES_PER_COURSE:
                            file_queue.append((title, item_url, ext))
                        break

        for furl in forum_urls[:3]:
            posts = await _scrape_forum_posts(page, furl)
            ctx.announcements.extend(posts)

        for folder_title, folder_url in folder_items[:6]:
            await _scrape_folder(page, folder_url, ctx, file_queue, prefix="", depth=0)

    except Exception:
        pass

    # Dateien herunterladen und Text extrahieren
    for f_title, f_url, f_ext in file_queue[:MAX_FILES_PER_COURSE]:
        text = await _fetch_file_text_cached(page, f_url, f_title, f_ext)
        if text.strip():
            ctx.file_contents.append((f_title, text))
        print(f"    [{f_ext.upper()}] {f_title[:50]} — {len(text)} Zeichen")

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

        from scraper.lea_scraper import _get_course_links
        courses = await _get_course_links(page)
        courses = [c for c in courses if c["title"] not in IGNORED_COURSES]

        results: list[CourseContext] = []
        for course in courses:
            ctx = await _scrape_course(page, course)
            results.append(ctx)
            print(f"  {course['title']}: {len(ctx.announcements)} Ankündigungen, "
                  f"{len(ctx.exercises)} Aufgaben, {len(ctx.materials)} Materialien, "
                  f"{len(ctx.file_contents)} Dateien (PDF/ZIP)")

        await browser.close()
    return results

import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HTML_PATH = Path(__file__).parent / "lernplan-v2.html"

IGNORED_COURSES = {
    "WI-Modellierung",
    "Modellierung betrieblicher Informationssysteme",
    "Programmierung 2",
    "Programmierung, Algorithmen und Datenstrukturen",
    "Einführung in das IT-Recht",
}

# ── Caches ────────────────────────────────────────────────
_deadline_cache: list[dict] = []
_deadline_cache_ts: float = 0

_lea_ctx_cache: str = ""
_lea_ctx_cache_ts: float = 0

_CACHE_TTL = 1800  # 30 Minuten


async def _fetch_deadlines() -> list[dict]:
    from scraper.lea_scraper import scrape_all_deadlines
    from scraper.analysis_scraper import scrape_analysis_deadlines
    from scraper.acat_scraper import scrape_acat_deadlines

    lea, analysis, acat = await asyncio.gather(
        scrape_all_deadlines(headless=True),
        asyncio.to_thread(scrape_analysis_deadlines),
        scrape_acat_deadlines(headless=True),
    )
    all_d = sorted(
        [d for d in lea if d.course not in IGNORED_COURSES] + analysis + acat,
        key=lambda d: d.due_date,
    )
    return [
        {"course": d.course, "title": d.title,
         "due_date": d.due_date.isoformat(), "type": d.type, "url": d.url}
        for d in all_d
    ]


async def get_deadlines_cached(force: bool = False) -> list[dict]:
    global _deadline_cache, _deadline_cache_ts
    if force or not _deadline_cache or time.time() - _deadline_cache_ts > _CACHE_TTL:
        _deadline_cache = await _fetch_deadlines()
        _deadline_cache_ts = time.time()
    return _deadline_cache


async def get_lea_context_cached(force: bool = False) -> str:
    global _lea_ctx_cache, _lea_ctx_cache_ts
    if force or not _lea_ctx_cache or time.time() - _lea_ctx_cache_ts > _CACHE_TTL:
        from scraper.lea_context import scrape_lea_full_context
        contexts = await scrape_lea_full_context(headless=True)
        _lea_ctx_cache = "\n\n".join(c.to_text() for c in contexts if c.announcements or c.exercises or c.materials)
        _lea_ctx_cache_ts = time.time()
    return _lea_ctx_cache


def _build_system_prompt(deadlines: list[dict], lea_context: str = "") -> str:
    from datetime import datetime
    today = datetime.now()

    if deadlines:
        lines = []
        for d in deadlines:
            due = datetime.fromisoformat(d["due_date"])
            days = (due - today).days
            days_str = "HEUTE" if days == 0 else f"in {days}d" if days > 0 else "ABGELAUFEN"
            lines.append(f"  • [{d['course']}] {d['title']} — {due.strftime('%d.%m.%Y')} ({days_str})")
        deadlines_text = "\n".join(lines)
    else:
        deadlines_text = "  (Keine Fristen geladen — Server neu starten)"

    return f"""Du bist Melihs persönlicher Lern-Assistent. Melih studiert Wirtschaftsinformatik im 4. Semester an der H-BRS (SoSe 2026).

AKTUELLE FRISTEN (live aus LEA, Analysis & ACAT):
{deadlines_text}

KURSE & ABGABE-REGELN:
  • Analysis — ACAT-Tests in 10-tägigen Fenstern (Termine oben), Übungsblätter alle 2–3 Wochen
  • Datenbanken — WÖCHENTLICHE Abgabe via LEA (immer nach der Donnerstags-Übung einreichen, nie aufschieben)
  • Algorithmen & Datenstrukturen (ADS) — Abgaben via ACAT (https://adgt.acat.inf.h-brs.de/exercises)
  • Mathe für Data Science — Quelle noch unklar, Melih klärt noch
  • Künstliche Intelligenz — optionale Jupyter-Notebooks via https://notebooks.inf.h-brs.de — Deadlines werden in der Vorlesung kommuniziert, also in LEA nachschauen; Melih will sie trotzdem machen
  • Datenanalyse & Visualisierung — optionale Jupyter-Notebooks via https://notebooks.inf.h-brs.de — gleiche Regelung wie KI
  • Planspiel (Topsim) — Deadlines kommen in der Online-Vorlesung, auf https://frontend.topsim.com nachschauen

WOCHENSTRUKTUR:
  • Mo + Do: Uni vor Ort
  • Di + Mi: Arbeit (8h, Vorlesungen als Aufzeichnung nachholen)
  • Fr–So: Lernen, Startup, Gym
  • Do nach der DB-Übung: sofort DB-Abgabe in LEA hochladen

LEA-INHALTE (Ankündigungen, Aufgaben, Materialien — automatisch gescrapt):
{lea_context if lea_context else "  (Noch nicht geladen — /api/lea-refresh aufrufen)"}

Antworte auf Deutsch, casual (du), kurz und konkret. Nutze Markdown für Listen und Code.
Wenn du nach Fristen gefragt wirst, beziehe dich auf die obige Liste und weise auf wöchentliche DB-Abgaben hin."""


# ── Endpoints ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


@app.get("/api/deadlines")
async def get_deadlines(refresh: bool = False) -> list[dict]:
    return await get_deadlines_cached(force=refresh)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    from agent.llm_client import get_client

    deadlines, lea_context = await asyncio.gather(
        get_deadlines_cached(),
        get_lea_context_cached(),
    )
    system = _build_system_prompt(deadlines, lea_context)

    client = get_client()
    messages = req.history + [{"role": "user", "content": req.message}]
    response = await asyncio.to_thread(client.chat, system=system, messages=messages, max_tokens=4096)
    return {"response": response}


@app.post("/api/lea-refresh")
async def lea_refresh() -> dict:
    """Erzwingt einen vollständigen LEA-Neu-Scrape (dauert ~2 Min)."""
    deadlines, lea_context = await asyncio.gather(
        get_deadlines_cached(force=True),
        get_lea_context_cached(force=True),
    )
    return {"deadlines": len(deadlines), "lea_context_chars": len(lea_context)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

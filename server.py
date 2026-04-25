import asyncio
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

SYSTEM_PROMPT = """Du bist ein persönlicher Lern-Assistent für einen Wirtschaftsinformatik-Studenten
im 4. Semester an der H-BRS (SoSe 2026).
Kurse: Analysis, Datenbanken, Algorithmen & Datenstrukturen, Mathe für Data Science,
Künstliche Intelligenz, Datenanalyse & Visualisierung, Planspiel.
Antworte auf Deutsch, casual (du), kurz und konkret. Nutze Markdown für Listen und Code."""


@app.get("/", response_class=HTMLResponse)
async def serve_html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


@app.get("/api/deadlines")
async def get_deadlines() -> list[dict]:
    from scraper.lea_scraper import scrape_all_deadlines
    from scraper.analysis_scraper import scrape_analysis_deadlines
    from scraper.acat_scraper import scrape_acat_deadlines

    lea, analysis, acat = await asyncio.gather(
        scrape_all_deadlines(headless=True),
        asyncio.to_thread(scrape_analysis_deadlines),
        scrape_acat_deadlines(headless=True),
    )

    all_deadlines = sorted(
        [d for d in lea if d.course not in IGNORED_COURSES] + analysis + acat,
        key=lambda d: d.due_date,
    )

    return [
        {
            "course": d.course,
            "title": d.title,
            "due_date": d.due_date.isoformat(),
            "type": d.type,
            "url": d.url,
        }
        for d in all_deadlines
    ]


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    from agent.llm_client import get_client

    client = get_client()
    messages = req.history + [{"role": "user", "content": req.message}]
    response = await asyncio.to_thread(client.chat, system=SYSTEM_PROMPT, messages=messages)
    return {"response": response}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

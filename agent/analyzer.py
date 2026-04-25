import os
from pathlib import Path

from dotenv import load_dotenv

from scraper.parser import Deadline
from agent.llm_client import get_client

load_dotenv()

STUNDENPLAN_PATH = Path(__file__).parent.parent / "stundenplan" / "stundenplan.html"

SYSTEM_PROMPT = """Du bist ein persönlicher Studienassistent für einen Wirtschaftsinformatik-Studenten
im 4. Semester an der H-BRS (SoSe 2026).

Du kennst seinen Lernplan und seine Wochenstruktur. Deine Aufgaben:
- Fristen und Abgaben analysieren und priorisieren
- Realistische Lernblöcke vorschlagen (passend zur vorhandenen Wochenstruktur)
- Klare, kurze Empfehlungen geben
- Auf Deutsch antworten, casual (du)

Kurse dieses Semesters:
- Analysis
- Datenbanken
- Algorithmen & Datenstrukturen
- Mathe für Data Science
- Künstliche Intelligenz
- Datenanalyse & Visualisierung
- WI-Modellierung
- Programmierung 2
- Planspiel"""


def _load_stundenplan() -> str:
    if STUNDENPLAN_PATH.exists():
        return STUNDENPLAN_PATH.read_text(encoding="utf-8")[:3000]
    return "(Stundenplan nicht gefunden)"


def analyze_deadlines(deadlines: list[Deadline]) -> str:
    client = get_client()
    deadline_text = "\n".join(str(d) for d in deadlines) if deadlines else "Keine Fristen gefunden."
    stundenplan = _load_stundenplan()

    messages = [{
        "role": "user",
        "content": (
            f"Aktuelle Fristen aus LEA:\n{deadline_text}\n\n"
            f"Mein Wochenplan (Auszug):\n{stundenplan[:1500]}\n\n"
            "Analysiere die Fristen: Was ist dringend? "
            "Wann sollte ich mit der Vorbereitung starten? "
            "Gib konkrete Lernblöcke für diese Woche vor."
        )
    }]

    return client.chat(system=SYSTEM_PROMPT, messages=messages)

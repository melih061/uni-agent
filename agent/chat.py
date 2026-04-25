import os
from pathlib import Path

from dotenv import load_dotenv

from agent.llm_client import get_client

load_dotenv()

STUNDENPLAN_PATH = Path(__file__).parent.parent / "stundenplan" / "stundenplan.html"

SYSTEM_PROMPT = """Du bist ein persönlicher Lern-Assistent für einen Wirtschaftsinformatik-Studenten
im 4. Semester an der H-BRS (SoSe 2026).

Kurse: Analysis, Datenbanken, Algorithmen & Datenstrukturen, Mathe für Data Science,
Künstliche Intelligenz, Datenanalyse & Visualisierung, WI-Modellierung, Programmierung 2, Planspiel.

Du kannst helfen mit:
- Erklärungen zu Vorlesungsinhalten
- Übungsaufgaben erstellen und durchgehen
- Lernstrategien und Zeitplanung
- Code-Fragen (Python, SQL, Java)
- Prüfungsvorbereitung

Antworte auf Deutsch, casual (du), kurz und konkret."""


def chat() -> None:
    client = get_client()

    system = SYSTEM_PROMPT
    if STUNDENPLAN_PATH.exists():
        system += (
            f"\n\nLernplan des Studenten (Auszug):\n"
            f"{STUNDENPLAN_PATH.read_text(encoding='utf-8')[:2000]}"
        )

    history: list[dict] = []
    provider = os.getenv("LLM_PROVIDER", "openai").upper()
    print(f"Lern-Assistent gestartet [{provider}]. 'exit' zum Beenden.\n")

    while True:
        try:
            user_input = input("Du: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nTschüss!")
            break

        if user_input.lower() in ("exit", "quit", "bye"):
            print("Tschüss!")
            break
        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})
        response = client.chat(system=system, messages=history)
        history.append({"role": "assistant", "content": response})
        print(f"\nAssistent: {response}\n")


if __name__ == "__main__":
    chat()

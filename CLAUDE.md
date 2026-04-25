# LEA Assistant — Uni Agent

## Projekt
Automatischer Agent für die H-BRS: scrapt Abgaben und Fristen aus LEA (ILIAS), trägt sie in Google Calendar ein und bietet einen Lern-Assistenten auf Basis der Claude API.

- Hochschule: H-BRS (Hochschule Bonn-Rhein-Sieg)
- LEA-System: ILIAS unter https://lea.hochschule-bonn-rhein-sieg.de
- Semester: SoSe 2026 (4. Semester Wirtschaftsinformatik)
- Kurse: Analysis, Datenbanken, Algorithmen & Datenstrukturen, Mathe für Data Science, KI, Datenanalyse & Visualisierung, WI-Modellierung, Programmierung 2, Planspiel

## Tech-Stack
- Python 3.11+
- Playwright (async, headless) — LEA-Scraping
- Anthropic SDK (claude-sonnet-4-6) — Analyse + Chat
- python-dotenv — Credentials aus .env
- BeautifulSoup4 + lxml — HTML-Parsing
- Google Calendar via Claude Code MCP-Tools

## Kommunikation
- Sprache: Deutsch
- Stil: casual (du), kurz und direkt
- Keine Emojis
- Vor großen Änderungen fragen

## Python-Regeln
- Type hints überall
- Dataclasses für Datenmodelle
- async/await für Playwright und HTTP-Calls
- Keine hardcodierten Credentials — immer via `os.getenv()`
- `.env` wird nie committed

## Verbotenes
- Keine Magic Numbers ohne Erklärung
- Keine unnötigen Kommentare (was der Code tut, nicht warum)
- Keine synchronen Playwright-Calls
- `print()` nur für User-Output, nicht für Debugging

## Ordnerstruktur
```
Uni Agent/
├── CLAUDE.md
├── .env                  # nie committen!
├── .env.example
├── .gitignore
├── requirements.txt
├── main.py               # Entry Point
├── scraper/
│   ├── lea_scraper.py    # Playwright Login + Navigation
│   └── parser.py        # Deadline-Dataclasses
├── calendar/
│   └── gcal_sync.py     # Google Calendar Sync
├── agent/
│   ├── analyzer.py      # Claude API Analyse
│   └── chat.py          # Interaktiver Lern-Assistent
├── stundenplan/
│   ├── stundenplan.html  # Bestehender Lernplan (Read-Only)
│   └── updater.py       # HTML mit Fristen ergänzen
└── setup/
    ├── install.sh        # Abhängigkeiten installieren
    └── schedule_daily.sh # macOS LaunchAgent einrichten
```

## Ausführung
```bash
python main.py --dry-run   # Nur scrapen, kein Calendar-Sync
python main.py             # Voller Durchlauf
python agent/chat.py       # Lern-Assistent starten
```

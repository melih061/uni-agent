import asyncio
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Kurse die nicht automatisch getrackt werden sollen
IGNORED_COURSES = {"WI-Modellierung", "Modellierung betrieblicher Informationssysteme",
                   "Programmierung 2", "Programmierung, Algorithmen und Datenstrukturen"}


def print_banner() -> None:
    print("=" * 50)
    print("  LEA Assistant — H-BRS Uni Agent")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 50)


async def run(dry_run: bool = False) -> None:
    from scraper.lea_scraper import scrape_all_deadlines
    from scraper.analysis_scraper import scrape_analysis_deadlines
    from scraper.acat_scraper import scrape_acat_deadlines
    from agent.analyzer import analyze_deadlines
    from gcal.gcal_sync import deadlines_to_sync_instructions

    print_banner()

    print("\n[1/4] LEA wird gescrapt...")
    lea_deadlines = await scrape_all_deadlines(headless=True)
    lea_deadlines = [d for d in lea_deadlines if d.course not in IGNORED_COURSES]

    print("\n[2/4] Analysis-Seite wird gescrapt...")
    try:
        analysis_deadlines = scrape_analysis_deadlines()
        print(f"  {len(analysis_deadlines)} ACAT-Testfenster gefunden")
    except Exception as e:
        print(f"  Fehler: {e}")
        analysis_deadlines = []

    print("\n[3/4] ACAT wird gescrapt...")
    acat_deadlines = await scrape_acat_deadlines(headless=True)
    if acat_deadlines:
        print(f"  {len(acat_deadlines)} ADS-Abgabe(n) gefunden")

    all_deadlines = sorted(
        lea_deadlines + analysis_deadlines + acat_deadlines,
        key=lambda d: d.due_date,
    )

    if not all_deadlines:
        print("\nKeine Fristen gefunden.")
        return

    print(f"\n  {len(all_deadlines)} Frist(en) insgesamt:")
    for d in all_deadlines:
        print(f"  • {d}")

    print("\n[4/4] Analyse mit Gemini...")
    analysis = analyze_deadlines(all_deadlines)
    print(f"\n{analysis}")

    if dry_run:
        print("\nDry-Run: Google Calendar wird nicht aktualisiert.")
        print("\nCalendar-Sync würde folgendes eintragen:")
        print(deadlines_to_sync_instructions(all_deadlines))
        return

    print("\nGoogle Calendar Sync...")
    print(deadlines_to_sync_instructions(all_deadlines))
    print("\nHinweis: Öffne Claude Code und führe den Sync manuell aus,")
    print("oder nutze die MCP-Tools direkt in einem Claude-Gespräch.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run(dry_run=dry_run))

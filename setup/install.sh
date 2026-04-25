#!/bin/bash
set -e

echo "LEA Assistant — Installation"
echo "============================"

# Python-Pakete installieren
echo "Installiere Python-Abhängigkeiten..."
pip install -r requirements.txt

# Playwright-Browser herunterladen
echo "Installiere Playwright-Browser (Chromium)..."
playwright install chromium

# .env erstellen falls nicht vorhanden
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "WICHTIG: Trage deine Credentials in .env ein:"
    echo "  LEA_USERNAME=..."
    echo "  LEA_PASSWORD=..."
    echo "  ANTHROPIC_API_KEY=..."
fi

echo ""
echo "Installation abgeschlossen!"
echo "Starten mit: python main.py --dry-run"

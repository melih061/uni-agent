"""
Lädt PDFs aus LEA (authenticated) herunter und extrahiert Text.
Cacht Ergebnisse in ~/.cache/uni-agent/pdfs/ um Re-Downloads zu vermeiden.
"""
import hashlib
import os
from pathlib import Path

import pymupdf

CACHE_DIR = Path.home() / ".cache" / "uni-agent" / "pdfs"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_PAGES = 60
MAX_CHARS_PER_PDF = 12000


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _load_cached_text(url: str) -> str | None:
    path = CACHE_DIR / f"{_cache_key(url)}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _save_cached_text(url: str, text: str) -> None:
    path = CACHE_DIR / f"{_cache_key(url)}.txt"
    path.write_text(text, encoding="utf-8")


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """Extrahiert Text aus PDF-Bytes, max MAX_PAGES Seiten."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pages_text: list[str] = []
        total = 0
        for i, page in enumerate(doc):
            if i >= MAX_PAGES:
                break
            text = page.get_text("text").strip()
            if text:
                pages_text.append(f"[Seite {i+1}]\n{text}")
                total += len(text)
                if total >= MAX_CHARS_PER_PDF:
                    break
        doc.close()
        full = "\n\n".join(pages_text)
        return full[:MAX_CHARS_PER_PDF]
    except Exception:
        return ""


async def download_and_extract(page, url: str, title: str) -> str:
    """
    Lädt eine PDF-Datei aus LEA herunter (Playwright-Session) und extrahiert Text.
    Nutzt Cache wenn verfügbar.
    """
    cached = _load_cached_text(url)
    if cached is not None:
        return cached

    try:
        # Download via Playwright (authenticated)
        response = await page.request.get(url, timeout=30000)
        if response.status != 200:
            return ""
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            # Evtl. Redirect-Seite statt direkte PDF
            return ""
        pdf_bytes = await response.body()
        text = extract_text_from_bytes(pdf_bytes)
        _save_cached_text(url, text)
        return text
    except Exception:
        return ""

"""
Lädt PDFs und ZIPs aus LEA (authenticated) herunter und extrahiert Text.
Cacht Ergebnisse in ~/.cache/uni-agent/pdfs/ um Re-Downloads zu vermeiden.
"""
import hashlib
import io
import zipfile
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "uni-agent" / "pdfs"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_PAGES         = 60
MAX_CHARS_PER_PDF = 12000
MAX_CHARS_PER_ZIP = 16000

TEXT_EXTENSIONS = {".sql", ".py", ".txt", ".md", ".java", ".js", ".ts",
                   ".html", ".xml", ".json", ".csv", ".r", ".cpp", ".c", ".h"}


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


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extrahiert Text aus PDF-Bytes via pymupdf."""
    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        parts: list[str] = []
        total = 0
        for i, page in enumerate(doc):
            if i >= MAX_PAGES or total >= MAX_CHARS_PER_PDF:
                break
            text = page.get_text("text").strip()
            if text:
                parts.append(f"[Seite {i+1}]\n{text}")
                total += len(text)
        doc.close()
        return "\n\n".join(parts)[:MAX_CHARS_PER_PDF]
    except Exception:
        return ""


def extract_zip_text(zip_bytes: bytes, zip_name: str = "") -> str:
    """Extrahiert Text aus ZIP-Archiv: PDFs + Textdateien."""
    parts: list[str] = []
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = sorted(zf.namelist())
            for name in names:
                if total >= MAX_CHARS_PER_ZIP:
                    break
                # Verzeichnisse überspringen
                if name.endswith("/"):
                    continue
                ext = Path(name).suffix.lower()
                try:
                    data = zf.read(name)
                except Exception:
                    continue

                if ext == ".pdf":
                    text = extract_pdf_text(data)
                    if text:
                        parts.append(f"[{name}]\n{text[:4000]}")
                        total += len(text)
                elif ext in TEXT_EXTENSIONS:
                    try:
                        text = data.decode("utf-8", errors="replace").strip()
                        if text:
                            parts.append(f"[{name}]\n{text[:3000]}")
                            total += len(text)
                    except Exception:
                        pass
    except Exception:
        return ""
    return "\n\n".join(parts)[:MAX_CHARS_PER_ZIP]


async def _download(page, url: str) -> tuple[bytes, str]:
    """Gibt (bytes, content_type) zurück."""
    try:
        resp = await page.request.get(url, timeout=30000)
        if resp.status != 200:
            return b"", ""
        ct = resp.headers.get("content-type", "")
        return await resp.body(), ct
    except Exception:
        return b"", ""


async def fetch_and_extract(page, url: str, title: str, ext: str = "pdf") -> str:
    """
    Lädt PDF oder ZIP aus LEA und extrahiert Text (mit Disk-Cache).
    ext: 'pdf' oder 'zip'
    """
    cached = _load_cached_text(url)
    if cached is not None:
        return cached

    data, content_type = await _download(page, url)
    if not data:
        return ""

    if ext == "zip" or "zip" in content_type:
        text = extract_zip_text(data, title)
    else:
        text = extract_pdf_text(data)

    _save_cached_text(url, text)
    return text

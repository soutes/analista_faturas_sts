import hashlib
import io
from pathlib import Path

import pdfplumber


def extract_text(pdf_bytes: bytes) -> tuple[str, str]:
    """Extract text from a PDF byte stream and return (text, sha256_hash)."""
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            parts.append(txt)
    return "\n".join(parts).strip(), file_hash


def archive_pdf(pdf_bytes: bytes, file_hash: str, original_name: str, archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_name).stem.replace(" ", "_")[:60]
    target = archive_dir / f"{file_hash[:12]}_{safe_name}.pdf"
    if not target.exists():
        target.write_bytes(pdf_bytes)
    return target

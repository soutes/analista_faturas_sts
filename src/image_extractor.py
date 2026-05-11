"""OCR de prints do app do banco usando Tesseract."""

import io
import os
from pathlib import Path

import pytesseract
from PIL import Image

# Caminho do binário Tesseract no Windows
TESSERACT_BIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(TESSERACT_BIN).exists():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_BIN

# Diretório com os language packs (eng + por)
USER_TESSDATA = Path(os.environ.get("LOCALAPPDATA", "")) / "tessdata"


def extract_text_from_image(image_bytes: bytes) -> str:
    """OCR pt-BR + en de um print de banco. Usa pré-processamento simples
    para melhorar leitura de fundo claro/escuro."""
    img = Image.open(io.BytesIO(image_bytes))

    # Converte para RGB para garantir compatibilidade
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Upscale 2x se imagem muito pequena (Tesseract gosta de >300dpi)
    if img.width < 1000:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)

    config = ""
    if USER_TESSDATA.exists():
        config = f'--tessdata-dir "{USER_TESSDATA}"'

    try:
        text = pytesseract.image_to_string(img, lang="por+eng", config=config)
    except pytesseract.TesseractError:
        # fallback: só inglês
        text = pytesseract.image_to_string(img, lang="eng", config=config)

    return text.strip()


def extract_text_from_multiple(images_bytes: list[bytes]) -> str:
    """Concatena OCR de múltiplos prints (útil pra extrato com várias páginas)."""
    parts = []
    for i, b in enumerate(images_bytes, 1):
        txt = extract_text_from_image(b)
        if txt:
            parts.append(f"--- Print {i} ---\n{txt}")
    return "\n\n".join(parts)

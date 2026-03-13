"""Self-hosted Tesseract OCR client implementation."""

from __future__ import annotations

import io
import logging
import re

from PIL import Image, ImageFilter, ImageOps
import pytesseract

logger = logging.getLogger(__name__)

MIN_LINE_LENGTH = 3
MIN_ALPHA_RATIO = 0.4
NOISE_PATTERNS = re.compile(
    r"^[\s\-=_~|:.*#><^]+$"
    r"|^[^a-zA-Z0-9]*$"
)

TARGET_MIN_WIDTH = 2000


def _clean_ocr_text(raw: str) -> str:
    """Remove noisy lines from OCR output (stamps, postmarks, barcodes, artifacts)."""
    cleaned: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if len(line) < MIN_LINE_LENGTH:
            continue
        if NOISE_PATTERNS.match(line):
            continue
        alpha_count = sum(1 for c in line if c.isalpha())
        if len(line) > 0 and alpha_count / len(line) < MIN_ALPHA_RATIO:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


class TesseractClient:
    """Self-hosted Tesseract OCR provider. No external API calls required."""

    @property
    def provider_name(self) -> str:
        return "tesseract"

    def extract_text(self, image_bytes: bytes, content_type: str) -> str:
        image = Image.open(io.BytesIO(image_bytes))

        if image.width < TARGET_MIN_WIDTH:
            scale = TARGET_MIN_WIDTH / image.width
            image = image.resize(
                (int(image.width * scale), int(image.height * scale)),
                Image.LANCZOS,
            )

        image = ImageOps.grayscale(image)
        image = ImageOps.autocontrast(image, cutoff=1)
        image = image.filter(ImageFilter.SHARPEN)

        custom_config = r"--oem 3 --psm 3"
        raw: str = pytesseract.image_to_string(image, lang="eng", config=custom_config)

        cleaned = _clean_ocr_text(raw)
        logger.debug("tesseract raw=%d chars, cleaned=%d chars", len(raw), len(cleaned))
        return cleaned

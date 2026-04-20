"""EasyOCR client implementation — deep-learning OCR, self-hosted."""

from __future__ import annotations

import io
import logging
import re
import threading

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

MIN_LINE_LENGTH = 3
MIN_ALPHA_RATIO = 0.4
NOISE_PATTERNS = re.compile(
    r"^[\s\-=_~|:.*#><^]+$"
    r"|^[^a-zA-Z0-9]*$"
)

MAX_WIDTH = 1600

_reader_lock = threading.Lock()
_reader_instance = None


def _get_reader():
    """Lazily initialise and cache the EasyOCR Reader (model load is expensive)."""
    global _reader_instance
    if _reader_instance is None:
        with _reader_lock:
            if _reader_instance is None:
                import easyocr
                logger.info("easyocr: loading Reader model (first call, may take a few seconds)")
                _reader_instance = easyocr.Reader(["en"], gpu=False)
    return _reader_instance


def _clean_ocr_text(raw: str) -> str:
    """Remove noisy lines from OCR output."""
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


class EasyOCRClient:
    """Self-hosted EasyOCR provider. No external API calls required."""

    @property
    def provider_name(self) -> str:
        return "easyocr"

    def extract_text(self, image_bytes: bytes, content_type: str) -> str:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / image.width
            image = image.resize(
                (MAX_WIDTH, int(image.height * ratio)),
                Image.LANCZOS,
            )

        img_array = np.array(image)
        reader = _get_reader()
        results = reader.readtext(img_array, detail=1, paragraph=False, decoder="greedy")

        img_h = img_array.shape[0]
        line_threshold = max(img_h * 0.02, 10)

        results.sort(key=lambda r: (r[0][0][1], r[0][0][0]))

        lines: list[str] = []
        current_line_parts: list[str] = []
        prev_y: float | None = None

        for bbox, text, conf in results:
            if conf < 0.15:
                continue
            top_y = bbox[0][1]
            if prev_y is not None and abs(top_y - prev_y) > line_threshold:
                if current_line_parts:
                    lines.append(" ".join(current_line_parts))
                    current_line_parts = []
            current_line_parts.append(text)
            prev_y = top_y

        if current_line_parts:
            lines.append(" ".join(current_line_parts))

        raw = "\n".join(lines)
        cleaned = _clean_ocr_text(raw)
        logger.info(
            "easyocr: %d detections, raw=%d chars, cleaned=%d chars",
            len(results), len(raw), len(cleaned),
        )
        return cleaned

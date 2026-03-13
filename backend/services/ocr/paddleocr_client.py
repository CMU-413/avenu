"""PaddleOCR client implementation — deep-learning OCR, self-hosted."""

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

_ocr_lock = threading.Lock()
_ocr_instance = None


def _get_ocr():
    """Lazily initialise and cache the PaddleOCR instance (model load is expensive)."""
    global _ocr_instance
    if _ocr_instance is None:
        with _ocr_lock:
            if _ocr_instance is None:
                import os
                os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"  # skip startup connectivity check
                from paddleocr import PaddleOCR
                logger.info("paddleocr: loading model (first call, may take a few seconds)")
                # enable_mkldnn=False avoids PaddlePaddle 3.3 oneDNN/PIR crash (ConvertPirAttribute2RuntimeAttribute)
                _ocr_instance = PaddleOCR(lang="en", enable_mkldnn=False)
    return _ocr_instance


def _clean_ocr_text(raw: str) -> str:
    """Remove noisy lines and duplicate lines from OCR output."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        line = line.strip()
        if len(line) < MIN_LINE_LENGTH:
            continue
        if NOISE_PATTERNS.match(line):
            continue
        alpha_count = sum(1 for c in line if c.isalpha())
        if len(line) > 0 and alpha_count / len(line) < MIN_ALPHA_RATIO:
            continue
        key = line.upper() if len(line) <= 10 else line  # dedupe "USA", "UNITED STATES" case-insensitively
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)
    return "\n".join(cleaned)


class PaddleOCRClient:
    """Self-hosted PaddleOCR provider. No external API calls required."""

    @property
    def provider_name(self) -> str:
        return "paddleocr"

    def extract_text(self, image_bytes: bytes, content_type: str) -> str:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(image)

        ocr = _get_ocr()
        results = ocr.ocr(img_array)

        lines: list[str] = []
        if not results:
            raw = ""
        else:
            res = results[0]
            # PaddleOCR 3.4 (PaddleX): result has .json["res"] or dict-like rec_texts, rec_scores, rec_polys
            data = None
            if hasattr(res, "json") and isinstance(getattr(res, "json", None), dict):
                data = res.json.get("res", res.json)
            if data is None and hasattr(res, "__getitem__"):
                try:
                    if "rec_texts" in res or res.get("rec_texts") is not None:
                        data = res
                except (TypeError, KeyError):
                    pass

            if data is not None and (
                isinstance(data, dict) or hasattr(data, "get")
            ):
                get_ = getattr(data, "get", lambda k, d=None: d)
                rec_texts = list(get_("rec_texts", []) or [])
                rec_scores = list(get_("rec_scores", []) or [1.0] * len(rec_texts))
                rec_polys = list(get_("rec_polys", []) or get_("dt_polys", []) or [])
                detections = list(
                    zip(rec_polys, rec_texts, rec_scores)
                )[: len(rec_texts)]
            else:
                # PaddleOCR 2.x: list of (box, (text, conf)) or (box, text, conf)
                detections = []
                for item in (res if isinstance(res, (list, tuple)) else [res]):
                    if isinstance(item, dict):
                        detections.append((
                            item.get("dt_polys") or item.get("box") or [],
                            item.get("rec_text") or item.get("text") or "",
                            item.get("rec_score") or item.get("score", 1.0),
                        ))
                    elif len(item) == 3:
                        detections.append(item)
                    elif len(item) == 2:
                        box, (text, conf) = item
                        detections.append((box, text, conf))

            if detections:
                detections.sort(key=lambda d: (float(d[0][0][1]), float(d[0][0][0])))

                img_h = img_array.shape[0]
                line_threshold = max(img_h * 0.02, 10)

                current_line_parts: list[str] = []
                prev_y: float | None = None

                for box, text, conf in detections:
                    if isinstance(text, tuple):
                        text = text[0] if text else ""
                    conf_f = float(conf) if conf is not None else 1.0
                    if conf_f < 0.3:
                        continue
                    top_y = float(box[0][1]) if box and len(box) > 0 else 0
                    if prev_y is not None and abs(top_y - prev_y) > line_threshold:
                        if current_line_parts:
                            lines.append(" ".join(current_line_parts))
                            current_line_parts = []
                    current_line_parts.append(str(text) if text else "")
                    prev_y = top_y

                if current_line_parts:
                    lines.append(" ".join(current_line_parts))

        raw = "\n".join(lines)
        cleaned = _clean_ocr_text(raw)
        logger.info("paddleocr: raw=%d chars, cleaned=%d chars", len(raw), len(cleaned))
        return cleaned

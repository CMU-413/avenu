"""OCR endpoint for extracting text from mail/package images."""

from __future__ import annotations

import logging
import time

from flask import Blueprint, jsonify, request

from config import OCR_MAX_FILE_BYTES, OCR_PROVIDER, OCR_SPACE_API_KEY
from controllers.auth_guard import require_admin_session
from errors import APIError
from services.ocr import EasyOCRClient, OCRSpaceClient, PaddleOCRClient, TesseractClient

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = frozenset({
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/tiff",
    "image/bmp",
})

ocr_bp = Blueprint("ocr", __name__)


def _get_ocr_client():
    """Return configured OCR client. Defaults to self-hosted PaddleOCR."""
    if OCR_PROVIDER == "ocrspace" and OCR_SPACE_API_KEY:
        return OCRSpaceClient(api_key=OCR_SPACE_API_KEY)
    if OCR_PROVIDER == "tesseract":
        return TesseractClient()
    if OCR_PROVIDER == "easyocr":
        return EasyOCRClient()
    return PaddleOCRClient()


@ocr_bp.route("/api/ocr", methods=["OPTIONS"])
def ocr_options():
    return "", 204


@ocr_bp.route("/api/ocr", methods=["POST"])
@require_admin_session
def ocr_extract():
    """
    Accept image upload, run OCR, return extracted text.
    Fails gracefully: returns empty text on OCR failure without blocking the workflow.
    """
    try:
        return _ocr_extract_impl()
    except APIError:
        raise
    except Exception as e:
        logger.exception("ocr_extract: unhandled error: %s", e)
        return jsonify({
            "text": "",
            "provider": "unknown",
            "error": "OCR failed unexpectedly",
        }), 200


def _ocr_extract_impl():
    if "file" not in request.files and "image" not in request.files:
        raise APIError(400, "no file provided; use 'file' or 'image' form key")

    file = request.files.get("file") or request.files.get("image")
    if not file or not file.filename:
        raise APIError(400, "no file selected")

    content_type = file.content_type or ""
    if content_type.split(";")[0].strip().lower() not in ALLOWED_CONTENT_TYPES:
        raise APIError(
            422,
            f"invalid file type; allowed: png, jpeg, jpg, gif, tiff, bmp",
        )

    try:
        image_bytes = file.read()
    except OSError as e:
        logger.warning("ocr_extract: failed to read file: %s", e)
        raise APIError(400, "failed to read file") from e

    if len(image_bytes) > OCR_MAX_FILE_BYTES:
        raise APIError(
            422,
            f"file too large; max {OCR_MAX_FILE_BYTES // (1024 * 1024)}MB",
        )

    client = _get_ocr_client()

    start = time.perf_counter()
    try:
        text = client.extract_text(image_bytes, content_type)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "ocr_extract: success provider=%s latency_ms=%.1f text_len=%d",
            client.provider_name,
            elapsed_ms,
            len(text),
        )
        return jsonify({
            "text": text,
            "provider": client.provider_name,
        }), 200
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "ocr_extract: failure provider=%s latency_ms=%.1f error=%s",
            client.provider_name,
            elapsed_ms,
            str(e),
        )
        return jsonify({
            "text": "",
            "provider": client.provider_name,
        }), 200

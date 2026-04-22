"""OCR endpoint for extracting text from mail/package images."""

from __future__ import annotations

import logging
import time

from flask import Blueprint, jsonify, request

from config import (
    FEATURE_ADMIN_OCR,
    FEATURE_OCR_SHADOW_LAUNCH,
    OCR_MAX_FILE_BYTES,
    OCR_PROVIDER,
    OCR_SHADOW_PROVIDER,
    OCR_SPACE_API_KEY,
)
from controllers.auth_guard import require_admin_session
from errors import APIError
from metrics.metrics_ocr import mail_image_ocr_metrics
from services.ocr import EasyOCRClient, OCRSpaceClient, PaddleOCRClient, TesseractClient
from services.ocr.ocr_parser import has_identified_receiver, parse_ocr_text_with_metadata

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


@ocr_bp.before_request
def _require_admin_ocr_enabled():
    if request.method == "OPTIONS":
        return None
    if not FEATURE_ADMIN_OCR:
        return jsonify({"error": "admin OCR is disabled"}), 404
    return None


def _get_ocr_client_for(provider: str | None):
    """Return OCR client for a specific provider. Defaults to self-hosted PaddleOCR."""
    if provider == "ocrspace" and OCR_SPACE_API_KEY:
        return OCRSpaceClient(api_key=OCR_SPACE_API_KEY)
    if provider == "tesseract":
        return TesseractClient()
    if provider == "easyocr":
        return EasyOCRClient()
    return PaddleOCRClient()


def _get_ocr_client():
    return _get_ocr_client_for(OCR_PROVIDER)


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

    text = ""
    extract_succeeded = False
    with mail_image_ocr_metrics() as outcome:
        extract_start = time.perf_counter()
        try:
            text = client.extract_text(image_bytes, content_type)
            extract_succeeded = True
            elapsed_ms = (time.perf_counter() - extract_start) * 1000
            logger.info(
                "ocr_extract: success provider=%s latency_ms=%.1f text_len=%d",
                client.provider_name,
                elapsed_ms,
                len(text),
            )
            if text:
                receiver, sender, used_fallback = parse_ocr_text_with_metadata(text)
                if has_identified_receiver(receiver, used_fallback=used_fallback):
                    outcome.mark_success()
        except Exception as e:
            elapsed_ms = (time.perf_counter() - extract_start) * 1000
            logger.warning(
                "ocr_extract: failure provider=%s latency_ms=%.1f error=%s",
                client.provider_name,
                elapsed_ms,
                str(e),
            )
            text = ""

    if extract_succeeded and FEATURE_OCR_SHADOW_LAUNCH and OCR_SHADOW_PROVIDER:
        _run_shadow_ocr(image_bytes, content_type, active_provider=client.provider_name)

    return jsonify({
        "text": text,
        "provider": client.provider_name,
    }), 200


def _run_shadow_ocr(image_bytes: bytes, content_type: str, *, active_provider: str) -> None:
    if OCR_SHADOW_PROVIDER == active_provider:
        return
    try:
        shadow_client = _get_ocr_client_for(OCR_SHADOW_PROVIDER)
    except Exception as exc:
        logger.warning("ocr_shadow: failed to init provider=%s error=%s", OCR_SHADOW_PROVIDER, exc)
        return

    start = time.perf_counter()
    try:
        shadow_text = shadow_client.extract_text(image_bytes, content_type)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "ocr_shadow: success provider=%s latency_ms=%.1f text_len=%d",
            shadow_client.provider_name,
            elapsed_ms,
            len(shadow_text),
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "ocr_shadow: failure provider=%s latency_ms=%.1f error=%s",
            shadow_client.provider_name,
            elapsed_ms,
            str(exc),
        )

"""OCR.space API client implementation."""

from __future__ import annotations

import logging
import base64
from typing import Any

import requests

logger = logging.getLogger(__name__)

OCR_SPACE_URL = "https://api.ocr.space/parse/image"
DEFAULT_TIMEOUT = 15
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/tiff", "image/bmp"}


class OCRSpaceClient:
    """OCR.space provider implementation. Sends POST to API with timeout and single retry."""

    def __init__(self, *, api_key: str, timeout: int = DEFAULT_TIMEOUT):
        self._api_key = api_key
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "ocr.space"

    def _content_type_to_filetype(self, content_type: str) -> str:
        mapping = {
            "image/png": "PNG",
            "image/jpeg": "JPG",
            "image/jpg": "JPG",
            "image/gif": "GIF",
            "image/tiff": "TIF",
            "image/bmp": "BMP",
        }
        return mapping.get(content_type.lower().split(";")[0].strip(), "PNG")

    def extract_text(self, image_bytes: bytes, content_type: str) -> str:
        try:
            return self._extract_impl(image_bytes, content_type)
        except Exception as e:
            logger.warning("OCRSpaceClient extract_text first attempt failed: %s", e)
            try:
                return self._extract_impl(image_bytes, content_type)
            except Exception as retry_e:
                logger.warning("OCRSpaceClient extract_text retry failed: %s", retry_e)
                raise

    def _extract_impl(self, image_bytes: bytes, content_type: str) -> str:
        filetype = self._content_type_to_filetype(content_type)
        base64_data = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:{content_type};base64,{base64_data}"

        payload: dict[str, Any] = {
            "base64Image": data_uri,
            "language": "eng",
            "filetype": filetype,
            "isOverlayRequired": "false",
        }
        headers = {"apikey": self._api_key}

        response = requests.post(
            OCR_SPACE_URL,
            data=payload,
            headers=headers,
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()

        exit_code = data.get("OCRExitCode")
        if exit_code != 1:
            # 1 = success; other codes indicate error or no text
            error_msg = data.get("ErrorMessage", f"OCR exit code {exit_code}")
            raise ValueError(f"OCR.space returned error: {error_msg}")

        parsed_results = data.get("ParsedResults") or []
        if not parsed_results:
            return ""

        text_parts = []
        for result in parsed_results:
            raw = result.get("ParsedText", "")
            if isinstance(raw, str) and raw.strip():
                text_parts.append(raw.strip())

        return "\n".join(text_parts).strip() if text_parts else ""

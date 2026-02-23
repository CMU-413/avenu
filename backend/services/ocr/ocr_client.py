"""OCR client interface for swappable provider implementations."""

from __future__ import annotations

from typing import Protocol


class OCRClient(Protocol):
    """Abstract interface for OCR providers. Implementations must be swappable."""

    @property
    def provider_name(self) -> str:
        """Name of the OCR provider for telemetry and API response metadata."""
        ...

    def extract_text(self, image_bytes: bytes, content_type: str) -> str:
        """
        Process an image and return extracted raw text.

        Args:
            image_bytes: Raw image file bytes.
            content_type: MIME type (e.g. image/png, image/jpeg).

        Returns:
            Extracted text as a single string. Empty string if no text found.

        Raises:
            May raise provider-specific errors; callers should handle gracefully.
        """
        ...

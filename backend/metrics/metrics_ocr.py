from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from prometheus_client import Counter, Histogram

ocr_requests_total = Counter(
    "ocr_requests_total",
    "Total number of OCR processing attempts on uploaded mail images",
)

ocr_success_total = Counter(
    "ocr_success_total",
    "Total number of OCR attempts where a recipient (receiver) was identified from parsed text",
)

ocr_failure_total = Counter(
    "ocr_failure_total",
    "Total number of OCR attempts that failed or had insufficient confidence",
)

ocr_processing_duration_seconds = Histogram(
    "ocr_processing_duration_seconds",
    "Time taken to process OCR on an image in seconds",
)


def record_mail_image_ocr_attempt(*, duration_seconds: float, success: bool) -> None:
    """Record one completed OCR attempt (success or failure) after processing finishes."""
    ocr_requests_total.inc()
    ocr_processing_duration_seconds.observe(duration_seconds)
    if success:
        ocr_success_total.inc()
    else:
        ocr_failure_total.inc()


@contextmanager
def mail_image_ocr_metrics() -> Generator["OcrMetricsOutcome", None, None]:
    """
    Time an OCR attempt and emit Prometheus metrics on exit.

    Call ``outcome.mark_success()`` before leaving the block when a recipient
    (receiver) was identified from the OCR parse with sufficient confidence; otherwise
    the attempt is counted as a failure (including exceptions).
    """
    start = time.perf_counter()
    outcome = OcrMetricsOutcome()
    try:
        yield outcome
    finally:
        record_mail_image_ocr_attempt(
            duration_seconds=time.perf_counter() - start,
            success=outcome._success,
        )


class OcrMetricsOutcome:
    __slots__ = ("_success",)

    def __init__(self) -> None:
        self._success = False

    def mark_success(self) -> None:
        self._success = True

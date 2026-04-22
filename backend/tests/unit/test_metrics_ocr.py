from __future__ import annotations

import unittest

from prometheus_client import REGISTRY

from metrics.metrics_ocr import mail_image_ocr_metrics, record_mail_image_ocr_attempt


class MetricsOcrTests(unittest.TestCase):
    def _sample(self, name: str) -> float:
        v = REGISTRY.get_sample_value(name)
        return 0.0 if v is None else v

    def test_record_mail_image_ocr_attempt_success(self):
        before_req = self._sample("ocr_requests_total")
        before_ok = self._sample("ocr_success_total")
        before_fail = self._sample("ocr_failure_total")
        before_hist_count = self._sample("ocr_processing_duration_seconds_count")

        record_mail_image_ocr_attempt(duration_seconds=0.05, success=True)

        self.assertEqual(self._sample("ocr_requests_total"), before_req + 1.0)
        self.assertEqual(self._sample("ocr_success_total"), before_ok + 1.0)
        self.assertEqual(self._sample("ocr_failure_total"), before_fail)
        self.assertEqual(self._sample("ocr_processing_duration_seconds_count"), before_hist_count + 1.0)

    def test_record_mail_image_ocr_attempt_failure(self):
        before_req = self._sample("ocr_requests_total")
        before_ok = self._sample("ocr_success_total")
        before_fail = self._sample("ocr_failure_total")

        record_mail_image_ocr_attempt(duration_seconds=0.02, success=False)

        self.assertEqual(self._sample("ocr_requests_total"), before_req + 1.0)
        self.assertEqual(self._sample("ocr_success_total"), before_ok)
        self.assertEqual(self._sample("ocr_failure_total"), before_fail + 1.0)

    def test_mail_image_ocr_metrics_context_success(self):
        before_req = self._sample("ocr_requests_total")
        before_ok = self._sample("ocr_success_total")

        with mail_image_ocr_metrics() as outcome:
            outcome.mark_success()

        self.assertEqual(self._sample("ocr_requests_total"), before_req + 1.0)
        self.assertEqual(self._sample("ocr_success_total"), before_ok + 1.0)

    def test_mail_image_ocr_metrics_context_failure_on_exception(self):
        before_fail = self._sample("ocr_failure_total")

        with self.assertRaises(RuntimeError):
            with mail_image_ocr_metrics():
                raise RuntimeError("ocr provider down")

        self.assertEqual(self._sample("ocr_failure_total"), before_fail + 1.0)


if __name__ == "__main__":
    unittest.main()

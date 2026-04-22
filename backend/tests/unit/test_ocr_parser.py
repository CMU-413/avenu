from __future__ import annotations

import unittest

from services.ocr.ocr_parser import has_identified_receiver, parse_ocr_text_with_metadata


class OcrParserTests(unittest.TestCase):
    def test_has_identified_receiver_false_when_empty(self):
        self.assertFalse(has_identified_receiver(""))
        self.assertFalse(has_identified_receiver("  \n"))

    def test_has_identified_receiver_true_when_recipient_present(self):
        self.assertTrue(has_identified_receiver("Jane Doe"))

    def test_has_identified_receiver_false_when_result_is_fallback(self):
        self.assertFalse(has_identified_receiver("Jane Doe", used_fallback=True))

    def test_parse_ocr_text_with_metadata_marks_raw_fallback(self):
        receiver, sender, used_fallback = parse_ocr_text_with_metadata("Unstructured OCR text only")
        self.assertTrue(receiver)
        self.assertEqual(sender, "")
        self.assertTrue(used_fallback)


if __name__ == "__main__":
    unittest.main()

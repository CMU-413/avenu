from __future__ import annotations

import unittest

from services.ocr.ocr_parser import has_identified_receiver


class OcrParserTests(unittest.TestCase):
    def test_has_identified_receiver_false_when_empty(self):
        self.assertFalse(has_identified_receiver(""))
        self.assertFalse(has_identified_receiver("  \n"))

    def test_has_identified_receiver_true_when_recipient_present(self):
        self.assertTrue(has_identified_receiver("Jane Doe"))


if __name__ == "__main__":
    unittest.main()

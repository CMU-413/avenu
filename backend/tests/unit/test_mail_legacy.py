import os
import unittest

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.mail_legacy import legacy_mail_piece_count


class MailLegacyTests(unittest.TestCase):
    def test_defaults_to_one(self):
        self.assertEqual(legacy_mail_piece_count({"mailboxId": ObjectId()}), 1)
        self.assertEqual(legacy_mail_piece_count({"count": 0}), 1)
        self.assertEqual(legacy_mail_piece_count({"count": "2"}), 1)

    def test_positive_int(self):
        self.assertEqual(legacy_mail_piece_count({"count": 3}), 3)

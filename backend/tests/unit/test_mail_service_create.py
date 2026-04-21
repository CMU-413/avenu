"""Unit tests for services.mail_service.create_mail transition behavior.

Ensures ``create_mail`` stops writing legacy ``count`` docs and instead
expands ``count: N`` into N single-piece inserts, preserving the
one-doc-per-piece invariant for new writes.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.mail_service import create_mail


class CreateMailExpansionTests(unittest.TestCase):
    def setUp(self):
        self.mailbox_id = str(ObjectId())
        self.base_payload = {
            "mailboxId": self.mailbox_id,
            "date": "2025-01-01T10:00:00Z",
            "type": "letter",
        }

    def _run(self, payload, *, insert_ids):
        inserted_docs: list[dict] = []

        def fake_insert(doc):
            inserted_docs.append(doc)
            return insert_ids[len(inserted_docs) - 1]

        def fake_find(oid):
            return {"_id": oid, **self.base_payload}

        with patch("services.mail_service.mailbox_exists", return_value=True), \
             patch("services.mail_service.insert_mail", side_effect=fake_insert), \
             patch("services.mail_service.repo_find_mail", side_effect=fake_find):
            result = create_mail(payload)
        return result, inserted_docs

    def test_single_piece_default_is_one_insert_no_count_field(self):
        ids = [ObjectId()]
        result, inserted = self._run(self.base_payload, insert_ids=ids)
        self.assertEqual(len(inserted), 1)
        self.assertNotIn("count", inserted[0])
        self.assertEqual(result["_id"], ids[0])

    def test_count_one_expands_to_one_insert_no_count_field(self):
        ids = [ObjectId()]
        payload = {**self.base_payload, "count": 1}
        _result, inserted = self._run(payload, insert_ids=ids)
        self.assertEqual(len(inserted), 1)
        self.assertNotIn("count", inserted[0])

    def test_count_n_expands_to_n_inserts_each_without_count(self):
        n = 5
        ids = [ObjectId() for _ in range(n)]
        payload = {**self.base_payload, "type": "package", "count": n}
        result, inserted = self._run(payload, insert_ids=ids)
        self.assertEqual(len(inserted), n)
        for d in inserted:
            self.assertNotIn("count", d)
            self.assertEqual(d["type"], "package")
        self.assertEqual(result["_id"], ids[0])

    def test_is_promotional_true_persists_on_each_insert(self):
        n = 3
        ids = [ObjectId() for _ in range(n)]
        payload = {**self.base_payload, "count": n, "isPromotional": True}
        _result, inserted = self._run(payload, insert_ids=ids)
        self.assertEqual(len(inserted), n)
        for d in inserted:
            self.assertIs(d["isPromotional"], True)

    def test_is_promotional_omitted_when_absent(self):
        ids = [ObjectId()]
        _result, inserted = self._run(self.base_payload, insert_ids=ids)
        self.assertNotIn("isPromotional", inserted[0])

    def test_is_promotional_false_is_omitted(self):
        ids = [ObjectId()]
        payload = {**self.base_payload, "isPromotional": False}
        _result, inserted = self._run(payload, insert_ids=ids)
        self.assertNotIn("isPromotional", inserted[0])

    def test_invalid_count_raises(self):
        from errors import APIError
        with patch("services.mail_service.mailbox_exists", return_value=True), \
             patch("services.mail_service.insert_mail", return_value=ObjectId()), \
             patch("services.mail_service.repo_find_mail", return_value={"_id": ObjectId()}):
            with self.assertRaises(APIError):
                create_mail({**self.base_payload, "count": 0})
            with self.assertRaises(APIError):
                create_mail({**self.base_payload, "count": 1000})


if __name__ == "__main__":
    unittest.main()

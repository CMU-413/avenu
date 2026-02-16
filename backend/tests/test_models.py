import unittest

from bson import ObjectId

from errors import APIError
from models import build_mail_create, build_user_create


class ModelBuilderTests(unittest.TestCase):
    def test_build_user_create_sets_defaults(self):
        payload = {
            "optixId": 10,
            "fullname": "Jane Doe",
            "email": "Jane@Example.com",
        }
        doc = build_user_create(payload)
        self.assertEqual(doc["email"], "jane@example.com")
        self.assertFalse(doc["isAdmin"])
        self.assertEqual(doc["teamIds"], [])

    def test_build_user_create_requires_fullname(self):
        with self.assertRaises(APIError):
            build_user_create({"optixId": 1, "email": "a@b.com"})

    def test_build_mail_create_validates(self):
        payload = {
            "mailboxId": str(ObjectId()),
            "date": "2025-01-01T10:00:00Z",
            "type": "letter",
            "count": 2,
        }
        doc = build_mail_create(payload)
        self.assertEqual(doc["type"], "letter")
        self.assertEqual(doc["count"], 2)

    def test_build_mail_create_rejects_bad_count(self):
        with self.assertRaises(APIError):
            build_mail_create(
                {
                    "mailboxId": str(ObjectId()),
                    "date": "2025-01-01T10:00:00Z",
                    "type": "letter",
                    "count": 0,
                }
            )


if __name__ == "__main__":
    unittest.main()

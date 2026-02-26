import unittest

from bson import ObjectId

from errors import APIError
from validators import normalize_email, parse_distinct_object_ids, parse_enum_set


class ValidatorTests(unittest.TestCase):
    def test_normalize_email_lowercases(self):
        self.assertEqual(normalize_email("  USER@Example.COM "), "user@example.com")

    def test_normalize_email_rejects_invalid(self):
        with self.assertRaises(APIError):
            normalize_email("invalid")

    def test_parse_distinct_object_ids_dedupes(self):
        oid = str(ObjectId())
        parsed = parse_distinct_object_ids([oid, oid], "teamIds")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(str(parsed[0]), oid)

    def test_parse_enum_set_rejects_invalid(self):
        with self.assertRaises(APIError):
            parse_enum_set(["email", "push"], field_name="notifPrefs", allowed={"email", "text"})


if __name__ == "__main__":
    unittest.main()

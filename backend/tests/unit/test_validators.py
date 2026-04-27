import unittest

from bson import ObjectId

from errors import APIError
from validators import is_e164_phone, normalize_email, parse_distinct_object_ids, parse_enum_set


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

    def test_parse_distinct_object_ids_accepts_object_id_instances(self):
        oid = ObjectId()
        parsed = parse_distinct_object_ids([oid, oid], "teamIds")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0], oid)

    def test_parse_enum_set_rejects_invalid(self):
        with self.assertRaises(APIError):
            parse_enum_set(["email", "push"], field_name="notifPrefs", allowed={"email", "text"})

    def test_is_e164_phone_accepts_plus_and_digits(self):
        self.assertTrue(is_e164_phone("+15550001111"))
        self.assertTrue(is_e164_phone("  +441234567890  "))

    def test_is_e164_phone_rejects_naive_or_invalid(self):
        self.assertFalse(is_e164_phone("4125551234"))
        self.assertFalse(is_e164_phone("+0123456789"))
        self.assertFalse(is_e164_phone("+1"))
        self.assertFalse(is_e164_phone("+1abc"))
        self.assertFalse(is_e164_phone(""))
        self.assertFalse(is_e164_phone("+1" + "0" * 15))


if __name__ == "__main__":
    unittest.main()

import unittest
from copy import deepcopy

from pymongo.errors import DuplicateKeyError

from errors import APIError
from idempotency import payload_hash, reserve_or_replay, store_idempotent_response


class _FakeCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        for existing in self.docs:
            if (
                existing["key"] == doc["key"]
                and existing["route"] == doc["route"]
                and existing["method"] == doc["method"]
            ):
                raise DuplicateKeyError("duplicate")
        self.docs.append(deepcopy(doc))
        return object()

    def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return deepcopy(doc)
        return None

    def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                for k, v in update.get("$set", {}).items():
                    doc[k] = deepcopy(v)
                return object()
        return object()


class IdempotencyTests(unittest.TestCase):
    def test_payload_hash_stable(self):
        a = {"a": 1, "b": 2}
        b = {"b": 2, "a": 1}
        self.assertEqual(payload_hash(a), payload_hash(b))

    def test_reserve_then_replay(self):
        c = _FakeCollection()
        req_hash = payload_hash({"x": 1})

        replay = reserve_or_replay(c, key="k", route="/users", method="POST", request_hash=req_hash)
        self.assertIsNone(replay)

        store_idempotent_response(c, key="k", route="/users", method="POST", status=201, body={"id": "1"})

        replay = reserve_or_replay(c, key="k", route="/users", method="POST", request_hash=req_hash)
        self.assertEqual(replay["status"], 201)
        self.assertEqual(replay["body"], {"id": "1"})

    def test_reuse_key_with_different_payload_fails(self):
        c = _FakeCollection()
        reserve_or_replay(c, key="k", route="/users", method="POST", request_hash=payload_hash({"x": 1}))
        with self.assertRaises(APIError):
            reserve_or_replay(c, key="k", route="/users", method="POST", request_hash=payload_hash({"x": 2}))


if __name__ == "__main__":
    unittest.main()

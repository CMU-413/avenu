import os
import unittest
from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from errors import APIError
from services.auth_magic_link_service import AuthMagicLinkService


class _FakeHaze:
    def __init__(self):
        self.use_calls = []
        self.storage_handler = None
        self.generate_calls = []
        self.verify_calls = []
        self.verify_result = {
            "user_id": str(ObjectId()),
            "token_id": "token-123",
            "metadata": {"email": "admin@example.com"},
            "exp": 1234,
            "iat": 1200,
        }

    def use(self, **kwargs):
        self.use_calls.append(kwargs)

    def storage(self, handler):
        self.storage_handler = handler
        return handler

    def generate(self, *, user_id, metadata, expiry):
        self.generate_calls.append({"user_id": user_id, "metadata": metadata, "expiry": expiry})
        return f"https://hub.avenuworkspaces.com/mail/?token_id=token-123&signature=signed-{user_id}"

    def verify(self, token_id, signature):
        self.verify_calls.append({"token_id": token_id, "signature": signature})
        return self.verify_result


class AuthMagicLinkServiceTests(unittest.TestCase):
    def test_init_configures_haze_with_expected_settings(self):
        fake_haze = _FakeHaze()
        store = {}

        def storage_handler(token_id, data=None):
            if data is None:
                return store.get(token_id)
            store[token_id] = data
            return data

        AuthMagicLinkService(
            base_url="https://hub.avenuworkspaces.com/mail/",
            magic_link_path="/",
            link_expiry_seconds=900,
            secret_key="secret-key",
            haze_module=fake_haze,
            storage_handler=storage_handler,
        )

        self.assertEqual(len(fake_haze.use_calls), 1)
        self.assertEqual(
            fake_haze.use_calls[0],
            {
                "base_url": "https://hub.avenuworkspaces.com/mail",
                "magic_link_path": "/",
                "link_expiry": 900,
                "allow_reuse": False,
                "secret_key": "secret-key",
                "token_provider": "jwt",
            },
        )
        self.assertIs(fake_haze.storage_handler, storage_handler)

    def test_storage_handler_round_trips_haze_shape(self):
        fake_haze = _FakeHaze()
        store = {}

        def storage_handler(token_id, data=None):
            if data is None:
                return store.get(token_id)
            store[token_id] = data
            return data

        AuthMagicLinkService(
            base_url="https://hub.avenuworkspaces.com/mail",
            magic_link_path="/",
            link_expiry_seconds=900,
            secret_key="secret-key",
            haze_module=fake_haze,
            storage_handler=storage_handler,
        )

        written = fake_haze.storage_handler(
            "token-123",
            {
                "user_id": str(ObjectId()),
                "exp": 2000,
                "metadata": {"email": "admin@example.com"},
                "consumed": False,
                "created_at": 1500,
            },
        )
        read_back = fake_haze.storage_handler("token-123")

        self.assertEqual(written, read_back)
        self.assertEqual(read_back["metadata"]["email"], "admin@example.com")
        self.assertFalse(read_back["consumed"])

    def test_generate_admin_login_link_rejects_non_admin_user(self):
        fake_haze = _FakeHaze()
        service = AuthMagicLinkService(
            base_url="https://hub.avenuworkspaces.com/mail",
            magic_link_path="/",
            link_expiry_seconds=900,
            secret_key="secret-key",
            haze_module=fake_haze,
            storage_handler=lambda token_id, data=None: None,
        )

        with self.assertRaises(APIError) as ctx:
            service.generate_admin_login_link(
                user={"_id": ObjectId(), "isAdmin": False, "email": "member@example.com"}
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(fake_haze.generate_calls, [])

    def test_generate_admin_login_link_uses_admin_id_and_default_metadata(self):
        fake_haze = _FakeHaze()
        service = AuthMagicLinkService(
            base_url="https://hub.avenuworkspaces.com/mail",
            magic_link_path="/",
            link_expiry_seconds=900,
            secret_key="secret-key",
            haze_module=fake_haze,
            storage_handler=lambda token_id, data=None: None,
        )
        user_id = ObjectId()

        link = service.generate_admin_login_link(
            user={
                "_id": user_id,
                "isAdmin": True,
                "email": "admin@example.com",
                "fullname": "Admin User",
            },
            metadata={"source": "login-form"},
            expiry_seconds=600,
        )

        self.assertEqual(
            fake_haze.generate_calls,
            [
                {
                    "user_id": str(user_id),
                    "metadata": {
                        "email": "admin@example.com",
                        "fullname": "Admin User",
                        "source": "login-form",
                    },
                    "expiry": 600,
                }
            ],
        )
        self.assertIn("/mail/?token_id=", link)

    def test_verify_login_link_returns_object_id_payload(self):
        fake_haze = _FakeHaze()
        user_id = ObjectId()
        fake_haze.verify_result = {
            "user_id": str(user_id),
            "token_id": "token-123",
            "metadata": {"email": "admin@example.com"},
            "exp": 2000,
            "iat": 1500,
        }
        service = AuthMagicLinkService(
            base_url="https://hub.avenuworkspaces.com/mail",
            magic_link_path="/",
            link_expiry_seconds=900,
            secret_key="secret-key",
            haze_module=fake_haze,
            storage_handler=lambda token_id, data=None: None,
        )

        result = service.verify_login_link(token_id="token-123", signature="signed")

        self.assertEqual(fake_haze.verify_calls, [{"token_id": "token-123", "signature": "signed"}])
        self.assertEqual(
            result,
            {
                "userId": user_id,
                "tokenId": "token-123",
                "metadata": {"email": "admin@example.com"},
                "exp": 2000,
                "iat": 1500,
            },
        )

    def test_verify_login_link_rejects_non_objectid_subject(self):
        fake_haze = _FakeHaze()
        fake_haze.verify_result = {
            "user_id": "not-an-object-id",
            "token_id": "token-123",
            "metadata": {},
            "exp": 2000,
            "iat": 1500,
        }
        service = AuthMagicLinkService(
            base_url="https://hub.avenuworkspaces.com/mail",
            magic_link_path="/",
            link_expiry_seconds=900,
            secret_key="secret-key",
            haze_module=fake_haze,
            storage_handler=lambda token_id, data=None: None,
        )

        with self.assertRaises(APIError) as ctx:
            service.verify_login_link(token_id="token-123", signature="signed")

        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()

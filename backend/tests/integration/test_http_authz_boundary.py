from __future__ import annotations

from bson import ObjectId

from .support import HttpIntegrationTestCase


class HttpAuthzBoundaryIntegrationTests(HttpIntegrationTestCase):
    def test_protected_endpoint_requires_authentication(self) -> None:
        member_response = self.client.get("/api/member/mail?start=2026-02-16&end=2026-02-22")
        admin_response = self.client.get("/api/users")

        self.assertEqual(member_response.status_code, 401)
        self.assertEqual(admin_response.status_code, 401)

    def test_member_cross_mailbox_mutation_is_forbidden_and_no_write_occurs(self) -> None:
        from config import mail_requests_collection

        requester = self.insert_user(
            email="member-a@example.com",
            is_admin=False,
            fullname="Member A",
        )
        target = self.insert_user(
            email="member-b@example.com",
            is_admin=False,
            fullname="Member B",
        )
        unauthorized_mailbox_id = self.insert_mailbox(
            owner_type="user",
            ref_id=target["_id"],
            display_name="Member B Mailbox",
        )

        login_response = self.login(email=requester["email"])
        self.assertEqual(login_response.status_code, 204)

        response = self.client.post(
            "/api/mail-requests",
            json={
                "mailboxId": str(unauthorized_mailbox_id),
                "expectedSender": "Acme Shipping",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            mail_requests_collection.count_documents(
                {
                    "memberId": requester["_id"],
                    "mailboxId": unauthorized_mailbox_id,
                }
            ),
            0,
        )

    def test_member_route_rejects_admin_session(self) -> None:
        admin = self.insert_user(
            email="admin@example.com",
            is_admin=True,
            fullname="Admin User",
            user_id=ObjectId(),
        )

        login_response = self.login(email=admin["email"])
        self.assertEqual(login_response.status_code, 204)

        response = self.client.get("/api/member/mail?start=2026-02-16&end=2026-02-22")
        self.assertEqual(response.status_code, 403)

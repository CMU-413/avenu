from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from support import MongoIntegrationTestCase


class MailPersistenceIntegrationTests(MongoIntegrationTestCase):
    def test_insert_and_retrieve_mail_entries(self) -> None:
        from repositories.mail_repository import find_mail, insert_mail, list_mail
        from repositories.mailboxes_repository import insert_mailbox

        now = datetime.now(tz=timezone.utc)
        owner_id = ObjectId()
        mailbox_id = insert_mailbox(
            {
                "type": "user",
                "refId": owner_id,
                "displayName": "Integration User",
                "createdAt": now,
                "updatedAt": now,
            }
        )

        first_id = insert_mail(
            {
                "mailboxId": mailbox_id,
                "date": datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc),
                "type": "letter",
                "count": 1,
                "createdAt": now,
                "updatedAt": now,
            }
        )

        first_doc = find_mail(first_id)
        self.assertIsNotNone(first_doc)
        self.assertEqual(first_doc["mailboxId"], mailbox_id)
        self.assertEqual(first_doc["type"], "letter")
        self.assertEqual(first_doc["count"], 1)

        by_mailbox = list_mail(mailbox_id=mailbox_id)
        self.assertEqual(len(by_mailbox), 1)
        self.assertEqual(by_mailbox[0]["_id"], first_id)

        second_id = insert_mail(
            {
                "mailboxId": mailbox_id,
                "date": datetime(2026, 2, 16, 11, 0, tzinfo=timezone.utc),
                "type": "letter",
                "count": 1,
                "createdAt": now,
                "updatedAt": now,
            }
        )

        all_rows = list_mail(mailbox_id=mailbox_id)
        self.assertEqual(len(all_rows), 2)
        self.assertNotEqual(first_id, second_id)

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId

from config import mail_collection


def list_mail(
    *,
    day_start: datetime | None = None,
    day_end: datetime | None = None,
    mailbox_id: ObjectId | None = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if day_start is not None and day_end is not None:
        query["date"] = {"$gte": day_start, "$lt": day_end}
    if mailbox_id is not None:
        query["mailboxId"] = mailbox_id
    return list(mail_collection.find(query).sort([("mailboxId", 1), ("date", 1), ("type", 1)]))


def find_mail(mail_id: ObjectId) -> dict[str, Any] | None:
    return mail_collection.find_one({"_id": mail_id})


def insert_mail(doc: dict[str, Any], *, session: Any | None = None) -> ObjectId:
    inserted = mail_collection.insert_one(doc, session=session)
    return inserted.inserted_id


def update_mail(mail_id: ObjectId, patch: dict[str, Any], *, session: Any | None = None) -> int:
    result = mail_collection.update_one({"_id": mail_id}, {"$set": patch}, session=session)
    return result.matched_count


def delete_mail(mail_id: ObjectId, *, session: Any | None = None) -> None:
    mail_collection.delete_one({"_id": mail_id}, session=session)


def delete_by_mailbox(mailbox_id: ObjectId, *, session: Any | None = None) -> None:
    mail_collection.delete_many({"mailboxId": mailbox_id}, session=session)


def find_mail_for_mailboxes(
    *,
    mailbox_ids: list[ObjectId],
    day_start: datetime,
    day_end: datetime,
) -> list[dict[str, Any]]:
    if not mailbox_ids:
        return []
    return list(
        mail_collection.find(
            {"mailboxId": {"$in": mailbox_ids}, "date": {"$gte": day_start, "$lt": day_end}},
            {"mailboxId": 1, "date": 1, "type": 1},
        )
    )

"""OCR queue job and item persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId

from config import ocr_jobs_collection, ocr_queue_items_collection


def create_ocr_job(*, created_by: ObjectId, date: str, item_count: int) -> ObjectId:
    doc = {
        "createdBy": created_by,
        "date": date,
        "status": "processing",
        "totalCount": item_count,
        "completedCount": 0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    r = ocr_jobs_collection.insert_one(doc)
    return r.inserted_id


def create_ocr_queue_items(
    job_id: ObjectId,
    count: int,
    *,
    file_ids: list[ObjectId] | None = None,
    image_paths: list[str] | None = None,
) -> list[ObjectId]:
    now = datetime.utcnow()
    # Note: queue items store `isPromotional: False` explicitly while MAIL
    # docs omit the field when false (see `build_mail_create`). The asymmetry
    # is intentional: the review UI reads queue rows directly and benefits
    # from the field always being present, whereas MAIL is the source of
    # truth for downstream consumers and stays sparse.
    docs = [
        {
            "jobId": job_id,
            "index": i,
            "status": "pending",
            "receiverName": None,
            "senderInfo": None,
            "type": "letter",
            "rawText": None,
            "error": None,
            "mailboxId": None,
            "fileId": file_ids[i] if file_ids and i < len(file_ids) else None,
            "imagePath": image_paths[i] if image_paths and i < len(image_paths) else None,
            "isPromotional": False,
            "confirmedAt": None,
            "createdAt": now,
            "updatedAt": now,
        }
        for i in range(count)
    ]
    r = ocr_queue_items_collection.insert_many(docs)
    return list(r.inserted_ids)


def get_ocr_job(job_id: ObjectId) -> dict[str, Any] | None:
    doc = ocr_jobs_collection.find_one({"_id": job_id})
    return doc


def update_ocr_job_status(job_id: ObjectId, status: str, completed_count: int | None = None) -> bool:
    update: dict[str, Any] = {"status": status, "updatedAt": datetime.utcnow()}
    if completed_count is not None:
        update["completedCount"] = completed_count
    r = ocr_jobs_collection.update_one({"_id": job_id}, {"$set": update})
    return r.modified_count > 0


def get_ocr_queue_items_for_job(job_id: ObjectId) -> list[dict[str, Any]]:
    return list(ocr_queue_items_collection.find({"jobId": job_id, "status": {"$ne": "deleted"}}).sort("index", 1))


def delete_ocr_queue_item(item_id: ObjectId) -> bool:
    """Soft delete a queue item."""
    r = ocr_queue_items_collection.update_one(
        {"_id": item_id},
        {"$set": {"status": "deleted", "updatedAt": datetime.utcnow()}}
    )
    return r.modified_count > 0



def get_ocr_queue_item(item_id: ObjectId) -> dict[str, Any] | None:
    return ocr_queue_items_collection.find_one({"_id": item_id})


_SENTINEL = object()


def update_ocr_queue_item(
    item_id: ObjectId,
    *,
    status: str | None = None,
    receiver_name: str | object = _SENTINEL,
    sender_info: str | object = _SENTINEL,
    mail_type: str | None = None,
    raw_text: str | None = None,
    error: str | None = None,
    mailbox_id: ObjectId | None | object = _SENTINEL,
    is_promotional: bool | object = _SENTINEL,
    confirmed_at: datetime | None = None,
) -> bool:
    updates: dict[str, Any] = {"updatedAt": datetime.utcnow()}
    if status is not None:
        updates["status"] = status
    if receiver_name is not _SENTINEL:
        updates["receiverName"] = receiver_name
    if sender_info is not _SENTINEL:
        updates["senderInfo"] = sender_info
    if mail_type is not None:
        updates["type"] = mail_type
    if raw_text is not None:
        updates["rawText"] = raw_text
    if error is not None:
        updates["error"] = error
    if mailbox_id is not _SENTINEL:
        updates["mailboxId"] = mailbox_id
    if is_promotional is not _SENTINEL:
        updates["isPromotional"] = bool(is_promotional)
    if confirmed_at is not None:
        updates["confirmedAt"] = confirmed_at
    r = ocr_queue_items_collection.update_one({"_id": item_id}, {"$set": updates})
    return r.modified_count > 0


def list_ocr_jobs_for_admin(admin_id: ObjectId, limit: int = 50) -> list[dict[str, Any]]:
    return list(
        ocr_jobs_collection.find({"createdBy": admin_id})
        .sort("createdAt", -1)
        .limit(limit)
    )

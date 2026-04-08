"""OCR queue: bulk upload, async processing, verify and assign mail."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from bson import ObjectId
from flask import Blueprint, jsonify, request, send_file

from config import FEATURE_OCR_QUEUE_V2, OCR_MAX_FILE_BYTES, ocr_queue_items_collection, fs
from controllers.auth_guard import require_admin_session
from errors import APIError
from idempotency import payload_hash
from repositories.idempotency_repository import delete_reservation, reserve_or_replay_request, store_response
from repositories.ocr_queue_repository import (
    create_ocr_job,
    create_ocr_queue_items,
    delete_ocr_queue_item,
    get_ocr_job,
    get_ocr_queue_item,
    get_ocr_queue_items_for_job,
    list_ocr_jobs_for_admin,
    update_ocr_job_status,
    update_ocr_queue_item,
)
from repositories import to_api_doc
from services.mail_service import create_mail
from services.ocr.ocr_parser import parse_ocr_text

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = frozenset({
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/tiff",
    "image/bmp",
})

ocr_queue_bp = Blueprint("ocr_queue", __name__)


@ocr_queue_bp.before_request
def _require_ocr_queue_v2_enabled():
    if request.method == "OPTIONS":
        return None
    if not FEATURE_OCR_QUEUE_V2:
        return jsonify({"error": "ocr queue feature is disabled"}), 404
    return None


def _get_ocr_client():
    from controllers.ocr_controller import _get_ocr_client
    return _get_ocr_client()


def _process_ocr_job(app, job_id: ObjectId, image_payloads: list[tuple[bytes, str]]) -> None:
    """Background worker: run OCR on each image and update queue items.

    Needs the Flask ``app`` so we can push an application context — the
    background thread has no request/app context by default and MongoDB
    collection references live in ``config`` which is loaded at import time,
    but pymongo operations themselves are fine without Flask context.
    """
    with app.app_context():
        try:
            client = _get_ocr_client()
            items = list(ocr_queue_items_collection.find({"jobId": job_id}).sort("index", 1))
            completed = 0
            for i, (image_bytes, content_type) in enumerate(image_payloads):
                if i >= len(items):
                    break
                item_id = items[i]["_id"]
                try:
                    text = client.extract_text(image_bytes, content_type)
                    receiver, sender = parse_ocr_text(text)
                    update_ocr_queue_item(
                        item_id,
                        status="completed",
                        raw_text=text,
                        receiver_name=receiver or None,
                        sender_info=sender or None,
                    )
                    logger.info("ocr_queue: processed item %s for job %s", item_id, job_id)
                except Exception as e:
                    logger.warning("ocr_queue: item %s failed: %s", item_id, e)
                    update_ocr_queue_item(item_id, status="failed", error=str(e))
                completed += 1
                update_ocr_job_status(job_id, "processing", completed_count=completed)

            update_ocr_job_status(job_id, "processed", completed_count=completed)
            logger.info("ocr_queue: job %s processed, %d/%d items", job_id, completed, len(image_payloads))
        except Exception as e:
            logger.exception("ocr_queue: job %s failed: %s", job_id, e)
            update_ocr_job_status(job_id, "failed")


def _serialize_job(doc: dict[str, Any]) -> dict:
    return {
        "id": str(doc["_id"]),
        "createdBy": str(doc["createdBy"]),
        "date": doc["date"],
        "status": doc["status"],
        "totalCount": doc["totalCount"],
        "completedCount": doc["completedCount"],
        "createdAt": doc["createdAt"].isoformat() if doc.get("createdAt") else None,
        "updatedAt": doc["updatedAt"].isoformat() if doc.get("updatedAt") else None,
    }


def _serialize_item(doc: dict[str, Any]) -> dict:
    return {
        "id": str(doc["_id"]),
        "jobId": str(doc["jobId"]),
        "index": doc["index"],
        "status": doc["status"],
        "receiverName": doc.get("receiverName"),
        "senderInfo": doc.get("senderInfo"),
        "type": doc.get("type", "letter"),
        "rawText": doc.get("rawText"),
        "error": doc.get("error"),
        "mailboxId": str(doc["mailboxId"]) if doc.get("mailboxId") else None,
        "fileId": str(doc["fileId"]) if doc.get("fileId") else None,
        "confirmedAt": doc["confirmedAt"].isoformat() if doc.get("confirmedAt") else None,
    }


@ocr_queue_bp.route("/api/ocr/jobs", methods=["POST"])
@require_admin_session
def create_job():
    """Bulk upload images, create job, start async OCR processing."""
    from flask import session
    user_id = session.get("user_id")
    if not user_id or not ObjectId.is_valid(user_id):
        return jsonify({"error": "unauthorized"}), 401
    admin_id = ObjectId(user_id)

    files = request.files.getlist("files") or request.files.getlist("images")
    if not files or not any(f and f.filename for f in files):
        raise APIError(400, "no files provided; use 'files' or 'images' form key")

    image_payloads: list[tuple[bytes, str]] = []
    for f in files:
        if not f or not f.filename:
            continue
        ct = (f.content_type or "").split(";")[0].strip().lower()
        if ct not in ALLOWED_CONTENT_TYPES:
            continue
        try:
            data = f.read()
        except OSError:
            continue
        if len(data) > OCR_MAX_FILE_BYTES:
            continue
        image_payloads.append((data, f.content_type or "image/jpeg"))

    if not image_payloads:
        raise APIError(422, "no valid images to process")

    # Store images in GridFS
    file_ids: list[ObjectId] = []
    for img_data, content_type in image_payloads:
        fid = fs.put(img_data, content_type=content_type, filename="ocr_upload")
        file_ids.append(fid)

    date = request.form.get("date") or datetime.utcnow().strftime("%Y-%m-%d")

    job_id = create_ocr_job(created_by=admin_id, date=date, item_count=len(image_payloads))
    create_ocr_queue_items(job_id, len(image_payloads), file_ids=file_ids)

    from flask import current_app
    app = current_app._get_current_object()
    thread = threading.Thread(target=_process_ocr_job, args=(app, job_id, image_payloads), daemon=True)
    thread.start()

    return jsonify({
        "id": str(job_id),
        "status": "processing",
        "totalCount": len(image_payloads),
        "completedCount": 0,
        "date": date,
    }), 201


@ocr_queue_bp.route("/api/ocr/jobs", methods=["GET"])
@require_admin_session
def list_jobs():
    """List OCR jobs for the current admin."""
    from flask import session
    user_id = session.get("user_id")
    if not user_id or not ObjectId.is_valid(user_id):
        return jsonify({"error": "unauthorized"}), 401
    try:
        limit = min(int(request.args.get("limit", 50)), 100)
    except (TypeError, ValueError):
        limit = 50
    jobs = list_ocr_jobs_for_admin(ObjectId(user_id), limit=limit)
    return jsonify({"jobs": [_serialize_job(j) for j in jobs]}), 200


@ocr_queue_bp.route("/api/ocr/jobs/<job_id>", methods=["GET"])
@require_admin_session
def get_job(job_id: str):
    """Get job status and its queue items."""
    if not ObjectId.is_valid(job_id):
        raise APIError(404, "job not found")
    oid = ObjectId(job_id)
    job = get_ocr_job(oid)
    if not job:
        raise APIError(404, "job not found")
    items = get_ocr_queue_items_for_job(oid)
    return jsonify({
        "job": _serialize_job(job),
        "items": [_serialize_item(i) for i in items],
    }), 200


@ocr_queue_bp.route("/api/ocr/queue/<item_id>", methods=["PATCH"])
@require_admin_session
def update_queue_item(item_id: str):
    """Update queue item (receiver, sender, type, mailbox assignment)."""
    if not ObjectId.is_valid(item_id):
        raise APIError(404, "item not found")
    oid = ObjectId(item_id)
    item = get_ocr_queue_item(oid)
    if not item:
        raise APIError(404, "item not found")
    if item.get("confirmedAt"):
        raise APIError(400, "item already confirmed")

    data = request.get_json() or {}
    repo_kwargs: dict[str, Any] = {}
    if "receiverName" in data:
        repo_kwargs["receiver_name"] = data["receiverName"]
    if "senderInfo" in data:
        repo_kwargs["sender_info"] = data["senderInfo"]
    if "type" in data and data["type"] in ("letter", "package"):
        repo_kwargs["mail_type"] = data["type"]
    if "mailboxId" in data:
        mb = data["mailboxId"]
        repo_kwargs["mailbox_id"] = ObjectId(mb) if mb and ObjectId.is_valid(mb) else None

    if repo_kwargs:
        update_ocr_queue_item(oid, **repo_kwargs)

    updated = get_ocr_queue_item(oid)
    return jsonify({"item": _serialize_item(updated)}), 200


@ocr_queue_bp.route("/api/ocr/queue/<item_id>/confirm", methods=["POST"])
@require_admin_session
def confirm_queue_item(item_id: str):
    """Confirm item: create mail entry and mark item confirmed."""
    if not ObjectId.is_valid(item_id):
        raise APIError(404, "item not found")
    oid = ObjectId(item_id)
    item = get_ocr_queue_item(oid)
    if not item:
        raise APIError(404, "item not found")
    if item.get("confirmedAt"):
        raise APIError(400, "item already confirmed")

    job = get_ocr_job(item["jobId"])
    if not job:
        raise APIError(404, "job not found")

    mailbox_id = item.get("mailboxId")
    if not mailbox_id:
        raise APIError(400, "mailboxId required; assign a mailbox before confirming")

    idempotency_key = f"ocr-confirm-{item_id}"
    route = "/api/ocr/queue/confirm"
    request_hash = payload_hash({"itemId": item_id})

    replay = reserve_or_replay_request(
        key=idempotency_key,
        route=route,
        method="POST",
        request_hash=request_hash,
    )
    if replay is not None:
        return jsonify(replay["body"]), replay["status"]

    try:
        payload = {
            "mailboxId": str(mailbox_id),
            "date": job["date"],
            "type": item.get("type", "letter"),
            "receiverName": item.get("receiverName"),
            "senderInfo": item.get("senderInfo"),
        }
        created_mail = create_mail(payload)

        now = datetime.utcnow()
        update_ocr_queue_item(oid, status="confirmed", confirmed_at=now)

        updated = get_ocr_queue_item(oid)
        body = {"item": _serialize_item(updated), "mail": to_api_doc(created_mail)}
        store_response(key=idempotency_key, route=route, method="POST", status=200, body=body)
        return jsonify(body), 200
    except Exception:
        delete_reservation(key=idempotency_key, route=route, method="POST")
        raise


@ocr_queue_bp.route("/api/ocr/queue/<item_id>", methods=["DELETE"])
@require_admin_session
def delete_queue_item(item_id: str):
    """Delete item (soft delete)."""
    if not ObjectId.is_valid(item_id):
        raise APIError(404, "item not found")
    
    success = delete_ocr_queue_item(ObjectId(item_id))
    if not success:
        raise APIError(404, "item not found or already deleted")
        
    return jsonify({"success": True}), 200


@ocr_queue_bp.route("/api/ocr/jobs/<job_id>/stage", methods=["POST"])
@require_admin_session
def update_job_stage(job_id: str):
    """Update job stage (processing -> processed -> audited)."""
    if not ObjectId.is_valid(job_id):
        raise APIError(404, "job not found")
    
    stage = request.json.get("stage")
    if stage not in ("processed", "audited"):
        raise APIError(400, "invalid stage")

    oid = ObjectId(job_id)
    success = update_ocr_job_status(oid, stage)
    if not success:
        raise APIError(404, "job not found")

    updated = get_ocr_job(oid)
    return jsonify({"job": _serialize_job(updated)}), 200


@ocr_queue_bp.route("/api/ocr/queue/<item_id>/image", methods=["GET"])
@require_admin_session
def get_item_image(item_id: str):
    """Get the image for a queue item."""
    if not ObjectId.is_valid(item_id):
        raise APIError(404, "item not found")
    
    item = get_ocr_queue_item(ObjectId(item_id))
    if not item or not item.get("fileId"):
        raise APIError(404, "image not found")

    try:
        grid_out = fs.get(item["fileId"])
        return send_file(grid_out, mimetype=grid_out.content_type)
    except Exception:
        raise APIError(404, "image file missing")


@ocr_queue_bp.route("/api/ocr/jobs", methods=["OPTIONS"], endpoint="ocr_jobs_options")
def _jobs_options():
    return "", 204


@ocr_queue_bp.route("/api/ocr/jobs/<job_id>", methods=["OPTIONS"], endpoint="ocr_job_options")
def _job_options(job_id: str):
    return "", 204


@ocr_queue_bp.route("/api/ocr/queue/<item_id>", methods=["OPTIONS"], endpoint="ocr_queue_item_options")
def _queue_item_options(item_id: str):
    return "", 204


@ocr_queue_bp.route("/api/ocr/queue/<item_id>/confirm", methods=["OPTIONS"], endpoint="ocr_queue_confirm_options")
def _queue_confirm_options(item_id: str):
    return "", 204

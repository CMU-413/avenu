"""End-to-end smoke test for the admin OCR flow.

Drives a real OCR job through the real WSGI app against a real MongoDB
using the real Tesseract provider and the real background worker thread.
No HTTP hops required: uses ``Flask.test_client`` so everything runs
in-process.

Usage (from repo root, with the backend venv active)::

    # Point at a running mongod (one-liner below starts a throwaway one):
    #   mkdir -p /tmp/mongo-smoke && \\
    #   mongod --dbpath /tmp/mongo-smoke --bind_ip 127.0.0.1 --port 27017 --fork \\
    #          --logpath /tmp/mongo-smoke/mongod.log
    MONGO_URI=mongodb://127.0.0.1:27017 DB_NAME=optix_smoke \\
        python backend/scripts/smoke_ocr_flow.py

Requirements: the ``tesseract`` binary must be installed (``apt install
tesseract-ocr``). Sets the feature flags ``FEATURE_ADMIN_OCR`` and
``FEATURE_OCR_QUEUE_V2`` unconditionally (they gate the routes).

Asserts every state transition along the way and exits non-zero on any
regression. Safe to re-run: drops and re-creates the configured DB.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path


DEFAULT_MONGO_URI = "mongodb://127.0.0.1:27017"
DEFAULT_DB_NAME = "optix_smoke"


def _bootstrap_env() -> None:
    """Seed feature flags and test defaults before importing the app."""
    os.environ.setdefault("MONGO_URI", DEFAULT_MONGO_URI)
    os.environ.setdefault("DB_NAME", DEFAULT_DB_NAME)
    os.environ["FEATURE_ADMIN_OCR"] = "true"
    os.environ["FEATURE_OCR_QUEUE_V2"] = "true"
    os.environ.setdefault("OCR_PROVIDER", "tesseract")
    os.environ["FLASK_TESTING"] = "1"
    os.environ.setdefault("SECRET_KEY", "smoke-secret-key")
    os.environ.setdefault("FRONTEND_ORIGINS", "http://localhost:5173")
    os.environ.setdefault("SCHEDULER_INTERNAL_TOKEN", "smoke-token")

    backend_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(backend_dir))


_bootstrap_env()

from bson import ObjectId  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from app import create_app  # noqa: E402
from config import ensure_indexes  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smoke")


_failures = 0


def step(msg: str) -> None:
    log.info("=" * 10 + f" {msg} " + "=" * 10)


def _expect(cond: bool, label: str, detail: object = "") -> None:
    global _failures
    if cond:
        log.info(f"  OK  {label}{': ' + repr(detail) if detail != '' else ''}")
    else:
        _failures += 1
        log.error(f"  FAIL  {label}: {detail!r}")


def _make_mail_image(receiver: str, sender: str) -> bytes:
    """Render a synthetic mail piece large enough for Tesseract to read."""
    img = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(img)
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
    except OSError:
        font_big = ImageFont.load_default()
        font = ImageFont.load_default()
    draw.text((60, 80), f"FROM: {sender}", font=font, fill="black")
    draw.text((60, 150), "123 Sender Ave", font=font, fill="black")
    draw.text((60, 210), "Chicago IL 60601", font=font, fill="black")
    draw.text((280, 420), f"TO: {receiver}", font=font_big, fill="black")
    draw.text((280, 500), "Avenu Workspaces", font=font, fill="black")
    draw.text((280, 560), "1 Market St", font=font, fill="black")
    draw.text((280, 620), "Chicago IL 60606", font=font, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main() -> int:
    mongo_uri = os.environ["MONGO_URI"]
    db_name = os.environ["DB_NAME"]

    step(f"1. Reset '{db_name}' + ensure indexes")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    client.drop_database(db_name)
    ensure_indexes()
    db = client[db_name]
    log.info(f"  dropped + reseeded db '{db_name}'")

    step("2. Seed admin + mailbox")
    admin_id = ObjectId()
    mailbox_id = ObjectId()
    now = datetime.utcnow()
    db.users.insert_one({
        "_id": admin_id, "optixId": 999001, "isAdmin": True,
        "fullname": "Admin Smoke", "email": "admin@smoke.local",
        "phone": None, "teamIds": [], "notifPrefs": [],
        "createdAt": now, "updatedAt": now,
    })
    db.mailboxes.insert_one({
        "_id": mailbox_id, "type": "user", "refId": admin_id,
        "displayName": "John Smith", "createdAt": now, "updatedAt": now,
    })

    step("3. Build WSGI app + authenticated test client")
    app = create_app(testing=True, ensure_db_indexes_on_startup=False,
                    secret_key=os.environ["SECRET_KEY"])
    tc = app.test_client()
    with tc.session_transaction() as sess:
        sess["user_id"] = str(admin_id)

    step("4. Upload 3 synthetic mail images")
    files = [
        (io.BytesIO(_make_mail_image("John Smith", "Acme Supplies Inc")), "p1.png", "image/png"),
        (io.BytesIO(_make_mail_image("Jane Doe", "Chase Bank")), "p2.png", "image/png"),
        (io.BytesIO(_make_mail_image("John Smith", "Amazon")), "p3.png", "image/png"),
    ]
    resp = tc.post("/api/ocr/jobs", data={"files": files, "date": "2026-04-19"},
                   content_type="multipart/form-data")
    _expect(resp.status_code == 201, "upload status", resp.status_code)
    job_id = resp.get_json()["id"]
    _expect(resp.get_json()["status"] == "processing", "initial job status", resp.get_json()["status"])
    _expect(resp.get_json()["totalCount"] == 3, "totalCount", resp.get_json()["totalCount"])

    step("5. Poll until worker reaches terminal state")
    observed: list[str] = []
    final = None
    deadline = time.time() + 90
    while time.time() < deadline:
        d = tc.get(f"/api/ocr/jobs/{job_id}").get_json()
        status = d["job"]["status"]
        if not observed or observed[-1] != status:
            log.info(f"  status={status} completed={d['job']['completedCount']}/{d['job']['totalCount']}")
            observed.append(status)
        if status in ("processed", "failed"):
            final = d
            break
        time.sleep(0.5)
    _expect(final is not None, "worker reached terminal state")
    if final is None:
        return 1
    _expect(final["job"]["status"] == "processed", "final job status", final["job"]["status"])
    _expect(final["job"]["completedCount"] == 3, "completedCount", final["job"]["completedCount"])
    log.info(f"  status transitions: {observed}")

    step("6. Inspect parsed queue items")
    items = final["items"]
    _expect(len(items) == 3, "queue item count", len(items))
    for i, it in enumerate(items):
        log.info(f"  item[{i}] status={it['status']} receiver={it.get('receiverName')!r}")
    _expect(sum(1 for it in items if it["status"] == "completed") >= 1, "\u22651 item OCR'd ok")

    step("7. PATCH: correct receiver + assign mailbox")
    target = next(it for it in items if it["status"] == "completed")
    r = tc.patch(f"/api/ocr/queue/{target['id']}", json={
        "receiverName": "John Smith", "senderInfo": "Acme Supplies Inc",
        "type": "letter", "mailboxId": str(mailbox_id),
    })
    _expect(r.status_code == 200, "patch status", r.status_code)
    patched = r.get_json()["item"]
    _expect(patched["mailboxId"] == str(mailbox_id), "assigned mailboxId")
    _expect(patched["receiverName"] == "John Smith", "corrected receiver")

    step("8. Confirm item -> mail doc created")
    r = tc.post(f"/api/ocr/queue/{target['id']}/confirm")
    _expect(r.status_code == 200, "confirm status", r.status_code)
    cbody = r.get_json()
    _expect(cbody["item"]["status"] == "confirmed", "item marked confirmed")
    _expect(bool(cbody["item"].get("confirmedAt")), "confirmedAt set")
    _expect("mail" in cbody and "id" in cbody["mail"], "mail doc created")
    mail_id = cbody["mail"]["id"]

    step("9. Confirm is idempotent (no duplicate mail)")
    before = db.mail.count_documents({})
    r2 = tc.post(f"/api/ocr/queue/{target['id']}/confirm")
    after = db.mail.count_documents({})
    _expect(r2.status_code == 200, "replay status", r2.status_code)
    _expect(after == before, "no duplicate mail on replay", (before, after))
    _expect(r2.get_json() == cbody, "replay body matches original")

    step("10. GET /api/mail includes the new piece, with no legacy count")
    listed = tc.get("/api/mail?date=2026-04-19").get_json()
    _expect(any(m.get("id") == mail_id for m in listed), "mail appears in GET /api/mail")
    created_doc = db.mail.find_one({"_id": ObjectId(mail_id)})
    _expect("count" not in created_doc, "one-doc-per-piece: no legacy count on new write")
    _expect(created_doc["mailboxId"] == mailbox_id, "mailbox fk")
    _expect(created_doc["receiverName"] == "John Smith", "mail receiverName")

    step("11. Soft-delete a queue item")
    bad = next((it for it in items if it["id"] != target["id"]), None)
    if bad:
        r = tc.delete(f"/api/ocr/queue/{bad['id']}")
        _expect(r.status_code == 200, "soft-delete status", r.status_code)
        doc = db.ocr_queue_items.find_one({"_id": ObjectId(bad["id"])})
        _expect(doc["status"] == "deleted", "item soft-deleted", doc["status"])

    step("12. Job stage: processed -> audited")
    r = tc.post(f"/api/ocr/jobs/{job_id}/stage", json={"stage": "audited"})
    _expect(r.status_code == 200, "stage status", r.status_code)
    _expect(r.get_json()["job"]["status"] == "audited", "job now audited")

    step("13. POST /api/mail with count=4 expands to 4 single-piece docs")
    before = db.mail.count_documents({})
    r = tc.post("/api/mail", json={
        "mailboxId": str(mailbox_id), "date": "2026-04-19T10:00:00Z",
        "type": "package", "count": 4,
    }, headers={"Idempotency-Key": "smoke-expand-1"})
    after = db.mail.count_documents({})
    _expect(r.status_code == 201, "create mail status", r.status_code)
    _expect(after - before == 4, "4 new single-piece docs inserted", after - before)
    _expect(db.mail.count_documents({"count": {"$exists": True}}) == 0, "no new legacy count docs")

    step("DONE")
    if _failures:
        log.error(f"SMOKE FAILED: {_failures} assertion(s)")
        return 1
    log.info(f"SMOKE PASSED  job={job_id}  item={target['id']}  mail={mail_id}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)

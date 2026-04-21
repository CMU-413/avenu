"""Unit tests for the OCR queue HTTP controller.

Covers:
  * upload validation (no files; invalid content types; oversized files)
  * queue item PATCH (invalid id, confirmed, allowed fields)
  * confirm flow (missing mailbox, happy path creates mail, idempotency replay)
  * job stage transitions (invalid / valid)

All Mongo and OCR side-effects are mocked so tests are hermetic.
"""

from __future__ import annotations

import io
import os
import unittest
from datetime import datetime
from unittest.mock import patch

from bson import ObjectId

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app


ADMIN_USER_ID = ObjectId()


def _admin_user_doc():
    return {"_id": ADMIN_USER_ID, "isAdmin": True, "email": "a@example.com"}


class _OcrQueueControllerTestBase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            testing=True,
            ensure_db_indexes_on_startup=False,
            secret_key="test-secret",
        )
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = str(ADMIN_USER_ID)

        # Enable feature flags + admin auth for the duration of each test.
        patches = [
            patch("controllers.ocr_queue_controller.FEATURE_ADMIN_OCR", True),
            patch("controllers.ocr_queue_controller.FEATURE_OCR_QUEUE_V2", True),
            patch("controllers.auth_guard.find_user", return_value=_admin_user_doc()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


class UploadValidationTests(_OcrQueueControllerTestBase):
    def test_post_with_no_files_returns_400(self):
        resp = self.client.post("/api/ocr/jobs", data={}, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("no files", resp.get_json()["error"])

    def test_post_with_only_invalid_content_type_returns_422(self):
        data = {"files": (io.BytesIO(b"not-an-image"), "a.txt", "text/plain")}
        resp = self.client.post("/api/ocr/jobs", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 422)

    def test_post_with_oversized_file_returns_422(self):
        from controllers import ocr_queue_controller as ctrl
        with patch.object(ctrl, "OCR_MAX_FILE_BYTES", 10):
            data = {"files": (io.BytesIO(b"x" * 100), "big.jpg", "image/jpeg")}
            resp = self.client.post("/api/ocr/jobs", data=data, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 422)

    def test_post_happy_path_with_auto_extract_off_writes_paths_and_skips_thread(self):
        job_id = ObjectId()

        data = {
            "files": [
                (io.BytesIO(b"img1"), "a.jpg", "image/jpeg"),
                (io.BytesIO(b"img2"), "b.png", "image/png"),
            ],
            "date": "2025-01-01",
        }

        saved_paths = ["abc.jpg", "def.png"]
        with patch("controllers.ocr_queue_controller.FEATURE_OCR_AUTO_EXTRACT", False), \
             patch("controllers.ocr_queue_controller.image_store.save_bytes", side_effect=saved_paths) as save_mock, \
             patch("controllers.ocr_queue_controller.create_ocr_job", return_value=job_id) as create_job, \
             patch("controllers.ocr_queue_controller.create_ocr_queue_items", return_value=[ObjectId(), ObjectId()]) as create_items, \
             patch("controllers.ocr_queue_controller.update_ocr_job_status") as status_mock, \
             patch("controllers.ocr_queue_controller.threading.Thread") as thread_mock:
            resp = self.client.post("/api/ocr/jobs", data=data, content_type="multipart/form-data")

        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertEqual(body["id"], str(job_id))
        self.assertEqual(body["status"], "processed")
        self.assertEqual(body["totalCount"], 2)
        self.assertEqual(body["completedCount"], 2)
        self.assertEqual(body["date"], "2025-01-01")
        create_job.assert_called_once()
        create_items.assert_called_once()
        self.assertEqual(create_items.call_args.kwargs["image_paths"], saved_paths)
        self.assertEqual(save_mock.call_count, 2)
        status_mock.assert_called_once_with(job_id, "processed", completed_count=2)
        thread_mock.assert_not_called()

    def test_post_happy_path_with_auto_extract_on_starts_thread(self):
        job_id = ObjectId()
        data = {
            "files": [(io.BytesIO(b"img"), "a.jpg", "image/jpeg")],
            "date": "2025-01-01",
        }
        with patch("controllers.ocr_queue_controller.FEATURE_OCR_AUTO_EXTRACT", True), \
             patch("controllers.ocr_queue_controller.image_store.save_bytes", return_value="xyz.jpg"), \
             patch("controllers.ocr_queue_controller.create_ocr_job", return_value=job_id), \
             patch("controllers.ocr_queue_controller.create_ocr_queue_items", return_value=[ObjectId()]), \
             patch("controllers.ocr_queue_controller.update_ocr_job_status") as status_mock, \
             patch("controllers.ocr_queue_controller.threading.Thread") as thread_mock:
            resp = self.client.post("/api/ocr/jobs", data=data, content_type="multipart/form-data")

        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertEqual(body["status"], "processing")
        self.assertEqual(body["completedCount"], 0)
        thread_mock.return_value.start.assert_called_once()
        status_mock.assert_not_called()


class QueueItemPatchTests(_OcrQueueControllerTestBase):
    def test_patch_invalid_id_returns_404(self):
        resp = self.client.patch("/api/ocr/queue/not-an-id", json={"receiverName": "x"})
        self.assertEqual(resp.status_code, 404)

    def test_patch_nonexistent_returns_404(self):
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=None):
            resp = self.client.patch(f"/api/ocr/queue/{ObjectId()}", json={"receiverName": "x"})
        self.assertEqual(resp.status_code, 404)

    def test_patch_confirmed_item_returns_400(self):
        item = {"_id": ObjectId(), "confirmedAt": datetime.utcnow(), "status": "confirmed"}
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item):
            resp = self.client.patch(f"/api/ocr/queue/{item['_id']}", json={"receiverName": "x"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already confirmed", resp.get_json()["error"])

    def test_patch_updates_allowed_fields_and_returns_item(self):
        item_id = ObjectId()
        mailbox_id = ObjectId()
        initial = {"_id": item_id, "confirmedAt": None, "status": "completed",
                   "jobId": ObjectId(), "index": 0, "type": "letter"}
        updated = {**initial, "receiverName": "Jane", "senderInfo": "Acme",
                   "type": "package", "mailboxId": mailbox_id}

        with patch("controllers.ocr_queue_controller.get_ocr_queue_item",
                   side_effect=[initial, updated]) as get_item, \
             patch("controllers.ocr_queue_controller.update_ocr_queue_item", return_value=True) as upd:
            resp = self.client.patch(
                f"/api/ocr/queue/{item_id}",
                json={
                    "receiverName": "Jane",
                    "senderInfo": "Acme",
                    "type": "package",
                    "mailboxId": str(mailbox_id),
                },
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["item"]["receiverName"], "Jane")
        self.assertEqual(body["item"]["type"], "package")
        self.assertEqual(body["item"]["mailboxId"], str(mailbox_id))
        self.assertEqual(get_item.call_count, 2)
        kwargs = upd.call_args.kwargs
        self.assertEqual(kwargs["receiver_name"], "Jane")
        self.assertEqual(kwargs["sender_info"], "Acme")
        self.assertEqual(kwargs["mail_type"], "package")
        self.assertEqual(kwargs["mailbox_id"], mailbox_id)

    def test_patch_ignores_unknown_type_value(self):
        item_id = ObjectId()
        initial = {"_id": item_id, "confirmedAt": None, "status": "completed",
                   "jobId": ObjectId(), "index": 0, "type": "letter"}
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=initial), \
             patch("controllers.ocr_queue_controller.update_ocr_queue_item") as upd:
            resp = self.client.patch(f"/api/ocr/queue/{item_id}", json={"type": "postcard"})
        self.assertEqual(resp.status_code, 200)
        upd.assert_not_called()


class ConfirmFlowTests(_OcrQueueControllerTestBase):
    def _item(self, **over):
        base = {
            "_id": ObjectId(),
            "jobId": ObjectId(),
            "index": 0,
            "status": "completed",
            "type": "letter",
            "receiverName": "Jane",
            "senderInfo": "Acme",
            "mailboxId": ObjectId(),
            "confirmedAt": None,
        }
        base.update(over)
        return base

    def _job(self, jid=None):
        return {"_id": jid or ObjectId(), "date": "2025-01-01"}

    def test_confirm_without_mailbox_returns_400(self):
        item = self._item(mailboxId=None)
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item), \
             patch("controllers.ocr_queue_controller.get_ocr_job", return_value=self._job(item["jobId"])), \
             patch("controllers.ocr_queue_controller.reserve_or_replay_request", return_value=None), \
             patch("controllers.ocr_queue_controller.delete_reservation") as release:
            resp = self.client.post(f"/api/ocr/queue/{item['_id']}/confirm")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("mailboxId required", resp.get_json()["error"])
        release.assert_called_once()

    def test_confirm_already_confirmed_with_expired_idempotency_returns_400(self):
        """If the idempotency cache entry has TTL'd out, the terminal-state guard fires."""
        item = self._item(confirmedAt=datetime.utcnow(), status="confirmed")
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item), \
             patch("controllers.ocr_queue_controller.reserve_or_replay_request", return_value=None), \
             patch("controllers.ocr_queue_controller.delete_reservation") as release:
            resp = self.client.post(f"/api/ocr/queue/{item['_id']}/confirm")
        self.assertEqual(resp.status_code, 400)
        release.assert_called_once()

    def test_confirm_happy_path_creates_mail_and_marks_confirmed(self):
        item = self._item()
        job = self._job(item["jobId"])
        created_mail = {"_id": ObjectId(), "mailboxId": item["mailboxId"],
                        "type": "letter", "date": datetime(2025, 1, 1)}
        confirmed_item = {**item, "status": "confirmed", "confirmedAt": datetime.utcnow()}

        with patch("controllers.ocr_queue_controller.get_ocr_queue_item",
                   side_effect=[item, confirmed_item]), \
             patch("controllers.ocr_queue_controller.get_ocr_job", return_value=job), \
             patch("controllers.ocr_queue_controller.reserve_or_replay_request", return_value=None), \
             patch("controllers.ocr_queue_controller.store_response") as store, \
             patch("controllers.ocr_queue_controller.create_mail", return_value=created_mail) as cm, \
             patch("controllers.ocr_queue_controller.update_ocr_queue_item") as upd:
            resp = self.client.post(f"/api/ocr/queue/{item['_id']}/confirm")

        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["item"]["status"], "confirmed")
        self.assertIn("mail", body)
        cm.assert_called_once()
        payload = cm.call_args.args[0]
        self.assertEqual(payload["mailboxId"], str(item["mailboxId"]))
        self.assertEqual(payload["date"], "2025-01-01")
        self.assertEqual(payload["type"], "letter")
        upd.assert_called_once()
        self.assertEqual(upd.call_args.kwargs["status"], "confirmed")
        store.assert_called_once()

    def test_confirm_is_idempotent_replays_previous_response(self):
        item = self._item()
        replay_body = {"item": {"id": str(item["_id"]), "status": "confirmed"},
                       "mail": {"id": str(ObjectId())}}

        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item), \
             patch("controllers.ocr_queue_controller.get_ocr_job", return_value=self._job(item["jobId"])), \
             patch("controllers.ocr_queue_controller.reserve_or_replay_request",
                   return_value={"status": 200, "body": replay_body}), \
             patch("controllers.ocr_queue_controller.create_mail") as cm, \
             patch("controllers.ocr_queue_controller.update_ocr_queue_item") as upd:
            resp = self.client.post(f"/api/ocr/queue/{item['_id']}/confirm")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), replay_body)
        cm.assert_not_called()
        upd.assert_not_called()

    def test_confirm_releases_reservation_on_error(self):
        item = self._item()
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item), \
             patch("controllers.ocr_queue_controller.get_ocr_job", return_value=self._job(item["jobId"])), \
             patch("controllers.ocr_queue_controller.reserve_or_replay_request", return_value=None), \
             patch("controllers.ocr_queue_controller.create_mail", side_effect=RuntimeError("boom")), \
             patch("controllers.ocr_queue_controller.delete_reservation") as release, \
             patch("controllers.ocr_queue_controller.update_ocr_queue_item"):
            # Flask testing mode propagates unhandled exceptions.
            with self.assertRaises(RuntimeError):
                self.client.post(f"/api/ocr/queue/{item['_id']}/confirm")
        release.assert_called_once()


class GetItemImageTests(_OcrQueueControllerTestBase):
    def test_get_image_prefers_filesystem_when_path_present(self):
        item_id = ObjectId()
        item = {"_id": item_id, "imagePath": "abc.jpg", "fileId": None}
        stream = io.BytesIO(b"pixels")
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item), \
             patch("controllers.ocr_queue_controller.image_store.open_path",
                   return_value=(stream, "image/jpeg")) as open_mock, \
             patch("controllers.ocr_queue_controller.fs") as fs_mock:
            resp = self.client.get(f"/api/ocr/queue/{item_id}/image")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"pixels")
        self.assertEqual(resp.mimetype, "image/jpeg")
        open_mock.assert_called_once_with("abc.jpg")
        fs_mock.get.assert_not_called()

    def test_get_image_falls_back_to_gridfs_when_no_path(self):
        item_id = ObjectId()
        file_id = ObjectId()
        item = {"_id": item_id, "imagePath": None, "fileId": file_id}

        class _FakeGrid:
            content_type = "image/png"
            def read(self, n=-1):
                return b"legacy"
            def close(self):
                pass

        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item), \
             patch("controllers.ocr_queue_controller.image_store.open_path") as open_mock, \
             patch("controllers.ocr_queue_controller.fs") as fs_mock:
            fs_mock.get.return_value = _FakeGrid()
            resp = self.client.get(f"/api/ocr/queue/{item_id}/image")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"legacy")
        self.assertEqual(resp.mimetype, "image/png")
        fs_mock.get.assert_called_once_with(file_id)
        open_mock.assert_not_called()

    def test_get_image_returns_404_when_filesystem_path_missing(self):
        item_id = ObjectId()
        item = {"_id": item_id, "imagePath": "gone.jpg", "fileId": None}
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item), \
             patch("controllers.ocr_queue_controller.image_store.open_path",
                   side_effect=FileNotFoundError("gone.jpg")):
            resp = self.client.get(f"/api/ocr/queue/{item_id}/image")
        self.assertEqual(resp.status_code, 404)

    def test_get_image_returns_404_when_neither_path_nor_fileid(self):
        item_id = ObjectId()
        item = {"_id": item_id, "imagePath": None, "fileId": None}
        with patch("controllers.ocr_queue_controller.get_ocr_queue_item", return_value=item):
            resp = self.client.get(f"/api/ocr/queue/{item_id}/image")
        self.assertEqual(resp.status_code, 404)


class JobStageTests(_OcrQueueControllerTestBase):
    def test_stage_invalid_returns_400(self):
        resp = self.client.post(f"/api/ocr/jobs/{ObjectId()}/stage", json={"stage": "bogus"})
        self.assertEqual(resp.status_code, 400)

    def test_stage_valid_updates_and_returns_job(self):
        job_id = ObjectId()
        updated = {"_id": job_id, "createdBy": ADMIN_USER_ID, "date": "2025-01-01",
                   "status": "audited", "totalCount": 3, "completedCount": 3,
                   "createdAt": datetime.utcnow(), "updatedAt": datetime.utcnow()}
        with patch("controllers.ocr_queue_controller.update_ocr_job_status", return_value=True) as upd, \
             patch("controllers.ocr_queue_controller.get_ocr_job", return_value=updated):
            resp = self.client.post(f"/api/ocr/jobs/{job_id}/stage", json={"stage": "audited"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["job"]["status"], "audited")
        upd.assert_called_once()

    def test_stage_nonexistent_returns_404(self):
        with patch("controllers.ocr_queue_controller.update_ocr_job_status", return_value=False):
            resp = self.client.post(f"/api/ocr/jobs/{ObjectId()}/stage", json={"stage": "processed"})
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()

"""API contract, upload validation, persistence errors, and file isolation."""
import base64
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import api  # noqa: E402


def _result(email_id="email_001", status="OK"):
    return {"email_id": email_id, "from": "ops@example.com", "subject": "Check BL",
            "body": "", "attachments": [], "category": "BL_COMPARISON", "status": status,
            "decided_by": "rule", "class_confidence": 1.0, "review_reason": None,
            "defect_fields": [], "has_defect": False, "comparison": [], "ai_used": [], "trace": []}


class MemoryStore:
    kind = "test"

    def __init__(self):
        self.saved_reviews = {}
        self.saved_results = {}

    def reviews(self):
        return dict(self.saved_reviews)

    def save_review(self, email_id, review):
        self.saved_reviews[email_id] = review

    def extra_results(self):
        return dict(self.saved_results)

    def save_result(self, email_id, result):
        self.saved_results[email_id] = result


@pytest.fixture
def client(monkeypatch, tmp_path):
    data = tmp_path / "data"
    uploads = tmp_path / "runtime-uploads"
    (data / "attachments").mkdir(parents=True)
    uploads.mkdir()
    store = MemoryStore()
    monkeypatch.setattr(api, "DATA", data)
    monkeypatch.setattr(api, "UPLOADS", uploads)
    monkeypatch.setattr(api, "RESULTS", {"email_001": _result()})
    monkeypatch.setattr(api, "store", store)
    monkeypatch.setattr(api, "BOOT_PROBLEMS", [])
    monkeypatch.setattr(api, "_sync", lambda: None)
    return TestClient(api.app), data, uploads, store


def test_health_and_email_listing_contract(client):
    web, _, _, _ = client
    assert web.get("/health").json() == {"ok": True, "emails": 1, "problems": None}
    rows = web.get("/api/emails", params={"status": "OK", "q": "check"}).json()
    assert len(rows) == 1 and rows[0]["email_id"] == "email_001"
    assert web.get("/api/emails/missing").status_code == 404


def test_valid_attachment_can_be_downloaded_on_windows(client):
    web, data, _, _ = client
    expected = b"shipping instruction"
    (data / "attachments" / "sample.txt").write_bytes(expected)
    response = web.get("/api/files/attachments/sample.txt")
    assert response.status_code == 200 and response.content == expected


@pytest.mark.parametrize("path", ["../.env", "../../README.md", r"..\..\.env", "C:/Windows/win.ini"])
def test_file_reader_rejects_path_traversal(client, path):
    with pytest.raises(HTTPException) as exc:
        api._read_bytes(path)
    assert exc.value.status_code == 400


def test_file_route_does_not_serve_files_outside_allowed_folders(client):
    _, data, _, _ = client
    secret = data / "secret.txt"
    secret.write_text("secret")
    with pytest.raises(HTTPException) as exc:
        api.get_file("secret.txt")
    assert exc.value.status_code == 404


def test_review_is_saved_and_changes_the_effective_result(client):
    web, _, _, store = client
    response = web.post("/api/emails/email_001/review", json={
        "action": "correct", "status": "MISMATCH", "defect_fields": ["consignee"],
        "reviewer": "tester",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "MISMATCH"
    assert store.saved_reviews["email_001"]["defect_fields"] == ["consignee"]


@pytest.mark.parametrize("payload", [
    {"action": "delete"},
    {"action": "correct", "status": "BROKEN"},
    {"action": "correct", "category": "UNKNOWN"},
])
def test_review_rejects_unknown_enums(client, payload):
    web, _, _, _ = client
    assert web.post("/api/emails/email_001/review", json=payload).status_code == 422


def test_review_rejects_unknown_defect_field(client):
    web, _, _, _ = client
    response = web.post("/api/emails/email_001/review", json={
        "action": "correct", "defect_fields": ["vessel_name"]})
    assert response.status_code == 400


def test_review_store_failure_returns_service_unavailable(client, monkeypatch):
    web, _, _, store = client
    monkeypatch.setattr(store, "save_review", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    response = web.post("/api/emails/email_001/review", json={"action": "confirm"})
    assert response.status_code == 503 and "Could not save" in response.json()["detail"]


def test_upload_rejects_invalid_base64_without_creating_a_folder(client):
    web, _, uploads, _ = client
    response = web.post("/api/process", json={
        "subject": "Check BL", "files": [{"name": "si.txt", "content_b64": "%%%"}]})
    assert response.status_code == 400
    assert list(uploads.iterdir()) == []


def test_upload_rejects_more_than_five_attachments(client):
    web, _, _, _ = client
    files = [{"name": f"{n}.txt", "content_b64": ""} for n in range(6)]
    assert web.post("/api/process", json={"subject": "x", "files": files}).status_code == 400


def test_upload_rejects_names_that_collide_after_sanitising(client):
    web, _, _, _ = client
    encoded = base64.b64encode(b"x").decode()
    response = web.post("/api/process", json={"subject": "x", "files": [
        {"name": "SI?.txt", "content_b64": encoded},
        {"name": "SI*.txt", "content_b64": encoded},
    ]})
    assert response.status_code == 400


def test_upload_sanitises_a_traversal_filename_and_stays_inside_uploads(client, monkeypatch):
    web, _, uploads, _ = client

    def fake_process(email, read_bytes, use_llm=True):
        result = _result(email["email_id"])
        result.update(email)
        return result

    monkeypatch.setattr(api, "process_email", fake_process)
    encoded = base64.b64encode(b"safe").decode()
    response = web.post("/api/process", json={"subject": "x", "files": [
        {"name": "../../SI?.txt", "content_b64": encoded}]})
    assert response.status_code == 200
    saved = list(uploads.rglob("*"))
    assert any(p.name == "SI_.txt" and p.read_bytes() == b"safe" for p in saved if p.is_file())
    attachment_path = response.json()["attachments"][0]
    download = web.get(f"/api/files/{attachment_path}")
    assert download.status_code == 200 and download.content == b"safe"


def test_upload_size_limit_returns_413(client, monkeypatch):
    web, _, _, _ = client
    monkeypatch.setattr(api, "MAX_FILE_BYTES", 2)
    encoded = base64.b64encode(b"123").decode()
    response = web.post("/api/process", json={"subject": "x", "files": [
        {"name": "large.txt", "content_b64": encoded}]})
    assert response.status_code == 413


def test_submission_excludes_dashboard_uploads(client):
    web, _, _, _ = client
    api.RESULTS["new_abc"] = _result("new_abc")
    body = web.get("/api/submission").json()
    assert set(body) == {"email_001"}

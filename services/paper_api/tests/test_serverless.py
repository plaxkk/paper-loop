import hashlib
import json
import pytest
from services.paper_api.tests.test_service import settings, client, paper_bytes, fake_model
from services.paper_api.db import connection
from services.paper_api.worker import run_once, claim, execute
from services.paper_api.storage import Storage, StorageError
from services.paper_api.analytics import drain_files
from services.paper_api import llm


@pytest.fixture
def cloud(settings, client, monkeypatch):
    objects = {}
    settings.serverless = True
    settings.supabase_url = "https://storage.example.test"
    settings.storage_key = "test-server-only-key"
    settings.worker_secret = "a" * 64
    monkeypatch.setattr(Storage, "exists", lambda self, key: key in objects)
    monkeypatch.setattr(Storage, "signed_upload", lambda self, key: "https://storage.example.test/upload/" + key)
    monkeypatch.setattr(Storage, "signed_download", lambda self, key: "https://storage.example.test/download/" + key)
    monkeypatch.setattr(Storage, "download", lambda self, key, target: target.write_bytes(objects[key]))
    monkeypatch.setattr(Storage, "upload", lambda self, key, source: objects.update({key: source.read_bytes()}))
    monkeypatch.setattr(Storage, "remove", lambda self, key: objects.pop(key, None))
    return objects


def ticket(client, data):
    response = client.post("/api/uploads", json={"filename": "study.pdf", "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "consent": True})
    assert response.status_code == 200, response.text
    return response.json()


def test_direct_upload_is_private_immutable_and_resumable(client, settings, paper_bytes, cloud):
    value = ticket(client, paper_bytes)
    key = value["workspace_id"]
    assert value["upload_url"].endswith(key)
    # Browser uploads to Storage; a lost completion request can be retried without overwrite.
    cloud[key] = paper_bytes
    assert ticket(client, paper_bytes)["upload_url"] is None
    first = client.post(f"/api/uploads/{key}/complete").json()
    assert client.post(f"/api/uploads/{key}/complete").json() == first
    assert run_once(settings)
    assert client.get(f"/api/workspaces/{key}").json()["status"] == "ready"
    assert client.get(f"/api/workspaces/{key}/pdf", follow_redirects=False).headers["location"].endswith(key)
    from fastapi.testclient import TestClient
    from services.paper_api.app import create_app
    settings.serverless = False  # The test database is SQLite, not a cloud configuration.
    with TestClient(create_app(settings)) as stranger:
        assert stranger.post(f"/api/uploads/{key}/complete").status_code == 404
        assert stranger.get(f"/api/workspaces/{key}/pdf", follow_redirects=False).status_code == 404
    assert client.delete(f"/api/workspaces/{key}").status_code == 200
    assert key not in cloud


def test_uploaded_bytes_are_verified_before_parsing(client, settings, paper_bytes, cloud):
    key = ticket(client, paper_bytes)["workspace_id"]
    cloud[key] = b"%PDF-replaced-content"
    client.post(f"/api/uploads/{key}/complete")
    run_once(settings)
    value = client.get(f"/api/workspaces/{key}").json()
    assert value["status"] == "failed"
    assert "校验失败" in value["error"]


def test_private_file_deletion_outbox_survives_storage_failure(client, settings, paper_bytes, cloud, monkeypatch):
    key = ticket(client, paper_bytes)["workspace_id"]
    cloud[key] = paper_bytes
    client.post(f"/api/uploads/{key}/complete")
    remove = Storage.remove
    def unavailable(*_):
        raise StorageError("offline")
    monkeypatch.setattr(Storage, "remove", unavailable)
    assert client.delete(f"/api/workspaces/{key}").status_code == 200
    assert client.get(f"/api/workspaces/{key}").status_code == 404
    with connection(settings) as db:
        assert db.execute("SELECT id FROM file_deletions").fetchone()[0] == key
    monkeypatch.setattr(Storage, "remove", remove)
    drain_files(settings)
    assert key not in cloud
    with connection(settings) as db:
        assert not db.execute("SELECT id FROM file_deletions").fetchone()


def test_translation_steps_keep_checkpoint_and_fence_stale_workers(client, settings, paper_bytes, cloud, fake_model, monkeypatch):
    key = ticket(client, paper_bytes)["workspace_id"]
    cloud[key] = paper_bytes
    client.post(f"/api/uploads/{key}/complete")
    run_once(settings)
    # Clear automatically queued analysis so this test isolates a translation task.
    with connection(settings, True) as db:
        db.execute("DELETE FROM jobs WHERE kind='analyze'")
    original = llm.batches
    monkeypatch.setattr(llm, "batches", lambda blocks, limit=18000: original(blocks, 150))
    job_id = client.post(f"/api/workspaces/{key}/actions/translate", json={"page": 1}).json()["job_id"]
    old = claim(settings)
    execute(settings, old)
    with connection(settings) as db:
        current = dict(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
    assert current["status"] == "queued" and json.loads(current["checkpoint"])["offset"] == 1
    execute(settings, old)  # A late invocation cannot advance a checkpoint twice.
    for _ in range(30):
        if not run_once(settings):
            break
    value = client.get("/api/jobs/" + job_id).json()
    assert value["status"] == "completed"
    assert all(t["text"].strip() for t in value["result"]["translations"])


def test_worker_tick_rejects_public_requests(client, settings, cloud):
    assert client.post("/api/internal/tick").status_code == 404
    assert client.post("/api/internal/tick", headers={"Authorization": "Bearer wrong"}).status_code == 404
    assert client.post("/api/internal/tick", headers={"Authorization": "Bearer " + settings.worker_secret}).status_code == 200


def test_storage_paths_reject_arbitrary_objects(settings):
    with pytest.raises(StorageError):
        Storage(settings).path("../../other-paper")

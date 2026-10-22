import asyncio
import importlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from conftest import ISSUER, PARTY
from fastapi.testclient import TestClient
from starlette.responses import FileResponse, StreamingResponse
from test_jobs import _fake_transcript

from diarist.auth import get_verifier
from diarist.jobs import JobManager


@pytest.fixture
def api_client(tmp_path, monkeypatch, trusted_jwks):
    monkeypatch.setenv("JOB_DATA_DIR", str(tmp_path / "unused"))
    monkeypatch.setenv("CLERK_ISSUER_URL", ISSUER)
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", PARTY)
    get_verifier.cache_clear()
    api = importlib.import_module("diarist.api")
    engine = MagicMock()
    engine.transcribe.return_value = _fake_transcript()
    manager = JobManager(tmp_path / "jobs", engine=engine)
    api.app.dependency_overrides[api.get_job_manager] = lambda: manager
    with TestClient(api.app) as client:
        yield client, manager
    api.app.dependency_overrides.clear()
    get_verifier.cache_clear()


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/jobs"),
        ("POST", "/api/jobs"),
        ("GET", "/api/jobs/20260101T000000Z-12345678"),
        ("DELETE", "/api/jobs/20260101T000000Z-12345678"),
        ("GET", "/api/jobs/20260101T000000Z-12345678/download/json"),
        ("GET", "/api/jobs/20260101T000000Z-12345678/download/docx"),
    ],
)
def test_all_job_endpoints_require_auth(api_client, method, path):
    client, _ = api_client
    response = client.request(method, path, headers={"X-User-Id": "user_a"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_two_user_isolation_for_every_endpoint(api_client, tokens):
    client, manager = api_client
    ids = {}
    headers = {
        name: {"Authorization": "Bearer " + tokens({"sub": name})} for name in ("user_a", "user_b")
    }
    for name, auth in headers.items():
        response = client.post(
            "/api/jobs",
            headers={**auth, "X-User-Id": "forged", "X-Owner-Id": "forged"},
            files={"file": ("test.wav", b"audio", "audio/wav")},
            data={"owner_id": "forged", "user_id": "forged"},
        )
        assert response.status_code == 201
        assert response.json()["owner_id"] == name
        ids[name] = response.json()["id"]
    manager._queue.join()

    for name, auth in headers.items():
        own, other = ids[name], ids["user_b" if name == "user_a" else "user_a"]
        assert [job["id"] for job in client.get("/api/jobs", headers=auth).json()] == [own]
        assert client.get(f"/api/jobs/{own}", headers=auth).json()["status"] == "completed"
        for kind in ("json", "docx"):
            response = client.get(f"/api/jobs/{own}/download/{kind}", headers=auth)
            assert response.status_code == 200 and response.content
        for method, suffix in [
            ("GET", ""),
            ("DELETE", ""),
            ("GET", "/download/json"),
            ("GET", "/download/docx"),
        ]:
            denied = client.request(
                method,
                f"/api/jobs/{other}{suffix}",
                headers={
                    **auth,
                    "X-User-Id": "user_b" if name == "user_a" else "user_a",
                },
            )
            missing = client.request(
                method,
                f"/api/jobs/20260101T000000Z-00000000{suffix}",
                headers=auth,
            )
            assert denied.status_code == missing.status_code == 404
            assert denied.json() == missing.json() == {"detail": "Job not found"}
    for name, auth in headers.items():
        assert client.delete(f"/api/jobs/{ids[name]}", headers=auth).status_code == 204
        assert client.get("/api/jobs", headers=auth).json() == []


@pytest.mark.parametrize(
    "changes,missing",
    [
        ({"exp": 1}, ()),
        ({"iat": 4102444800}, ()),
        ({"nbf": 4102444800}, ()),
        ({"iss": "https://evil.example"}, ()),
        ({"sub": ""}, ()),
        ({"sid": ""}, ()),
        ({"azp": "https://evil.example"}, ()),
        ({"sts": "pending"}, ()),
        ({"sts": ""}, ()),
        ({"sts": "inactive"}, ()),
        ({"sts": "ACTIVE"}, ()),
        ({"sts": None}, ()),
        ({"sts": False}, ()),
        ({"sts": 1}, ()),
        ({"sts": []}, ()),
        ({"sts": {}}, ()),
        ({}, ("sid",)),
        ({}, ("azp",)),
    ],
)
def test_invalid_signed_sessions_return_generic_401(api_client, tokens, changes, missing):
    client, manager = api_client
    response = client.get(
        "/api/jobs",
        headers={
            "Authorization": "Bearer " + tokens(changes, missing),
            "X-User-Id": "user_a",
        },
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid session"}
    assert manager.list_jobs(owner_id="user_a") == []


@pytest.mark.parametrize("header", ["Basic aaa", "Bearer invalid", "Bearer ", "Bearer a b"])
def test_malformed_auth_rejected(api_client, header):
    client, _ = api_client
    assert client.get("/api/jobs", headers={"Authorization": header}).status_code == 401


@pytest.mark.parametrize("setting", ["CLERK_ISSUER_URL", "CLERK_AUTHORIZED_PARTIES"])
def test_auth_configuration_required(api_client, tokens, monkeypatch, setting):
    client, _ = api_client
    monkeypatch.delenv(setting)
    response = client.get("/api/jobs", headers={"Authorization": "Bearer " + tokens()})
    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication unavailable"}


def test_jwks_outage_fails_closed(api_client, tokens, monkeypatch):
    import jwt

    def fail(client):
        raise jwt.PyJWKClientConnectionError("private network details")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", fail)
    client, _ = api_client
    response = client.get("/api/jobs", headers={"Authorization": "Bearer " + tokens()})
    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication unavailable"}


def test_private_responses_are_not_cacheable(api_client, tokens):
    client, manager = api_client
    auth = {"Authorization": "Bearer " + tokens()}
    created = client.post("/api/jobs", headers=auth, files={"file": ("test.wav", b"audio")})
    assert created.status_code == 201
    job_id = created.json()["id"]
    manager._queue.join()
    for path in [
        "/api/jobs",
        f"/api/jobs/{job_id}",
        f"/api/jobs/{job_id}/download/json",
        f"/api/jobs/{job_id}/download/docx",
    ]:
        response = client.get(path, headers=auth)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert "Authorization" in response.headers["vary"]
    assert client.get("/api/jobs").headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("kind", ["json", "docx"])
def test_download_survives_owner_deletion_before_response_opens(
    api_client, tokens, monkeypatch, kind
):
    client, manager = api_client
    auth = {"Authorization": "Bearer " + tokens()}
    created = client.post("/api/jobs", headers=auth, files={"file": ("test.wav", b"audio")})
    job_id = created.json()["id"]
    manager._queue.join()
    expected = manager.output_path(job_id, kind, owner_id="user_a").read_bytes()
    deleted = False
    opened = []
    original_open = manager.open_output

    def track_open(*args, **kwargs):
        file = original_open(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(manager, "open_output", track_open)

    def delete_before_response(response_class):
        original = response_class.__call__

        async def respond(response, scope, receive, send):
            nonlocal deleted
            if scope["path"] == f"/api/jobs/{job_id}/download/{kind}" and not deleted:
                # Route authorization/path selection has finished; response I/O has not.
                manager.delete_job(job_id, owner_id="user_a")
                deleted = True
            return await original(response, scope, receive, send)

        monkeypatch.setattr(response_class, "__call__", respond)

    for response_class in (FileResponse, StreamingResponse):
        delete_before_response(response_class)
    response = client.get(f"/api/jobs/{job_id}/download/{kind}", headers=auth)
    assert deleted
    assert not (manager.data_dir / job_id).exists()
    assert response.status_code == 200
    assert response.content == expected
    assert len(opened) == 1 and opened[0].closed
    assert response.headers["cache-control"] == "private, no-store"
    assert "Authorization" in response.headers["vary"]
    assert response.headers["content-disposition"] == (
        f'attachment; filename="{job_id}-transcript.{kind}"'
    )


@pytest.mark.parametrize("kind", ["json", "docx"])
def test_download_disappearing_at_open_returns_private_404(api_client, tokens, monkeypatch, kind):
    client, manager = api_client
    auth = {"Authorization": "Bearer " + tokens()}
    created = client.post("/api/jobs", headers=auth, files={"file": ("test.wav", b"audio")})
    job_id = created.json()["id"]
    manager._queue.join()
    target = manager.output_path(job_id, kind, owner_id="user_a")
    original_open = Path.open

    def disappear(path, *args, **kwargs):
        if path == target:
            assert manager._lock.locked(), "opening must be coordinated with deletion"
            path.unlink()
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", disappear)
    response = client.get(f"/api/jobs/{job_id}/download/{kind}", headers=auth)
    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}
    assert response.headers["cache-control"] == "private, no-store"
    assert "Authorization" in response.headers["vary"]


@pytest.mark.parametrize("failure_at", ["http.response.start", "http.response.body", "cancel"])
def test_download_closes_handle_on_send_failure_or_cancellation(tmp_path, failure_at):
    api = importlib.import_module("diarist.api")
    path = tmp_path / "output.json"
    path.write_bytes(b"x" * (128 * 1024))
    file = path.open("rb")
    response = api.DownloadResponse(file, filename="transcript.json", media_type="application/json")
    chunks = []

    async def send(message):
        if message["type"] == "http.response.body":
            chunks.append(message["body"])
        if failure_at == "cancel":
            raise asyncio.CancelledError
        if message["type"] == failure_at:
            raise RuntimeError("connection lost")

    async def receive():
        raise AssertionError("ASGI 2.4 should use send errors for disconnects")

    error = asyncio.CancelledError if failure_at == "cancel" else RuntimeError
    with pytest.raises(error):
        asyncio.run(response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send))
    assert file.closed
    assert all(len(chunk) <= 64 * 1024 for chunk in chunks)


def test_concurrent_first_requests_share_one_manager(tmp_path, monkeypatch):
    api = importlib.import_module("diarist.api")
    if hasattr(api.get_job_manager, "cache_clear"):
        api.get_job_manager.cache_clear()
    monkeypatch.setattr(api, "_manager", None, raising=False)
    created = []
    lock = threading.Lock()

    def make(*args):
        with lock:
            result = object()
            created.append(result)
        time.sleep(0.05)
        return result

    monkeypatch.setattr(api, "JobManager", make)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: api.get_job_manager(), range(8)))
    assert len(created) == 1
    assert all(result is results[0] for result in results)

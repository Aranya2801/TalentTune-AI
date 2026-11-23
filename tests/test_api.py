import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TALENTTUNE_DB", str(tmp_path / "t.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from talenttune.api import app as app_mod

    app_mod.history.cache_clear()
    return TestClient(app_mod.app)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_score_and_tailor(client, resume_text, jd_text):
    body = {"resume_text": resume_text, "job_description": jd_text}
    r = client.post("/api/v1/score", json=body)
    assert r.status_code == 200 and "requirements" in r.json()

    r = client.post("/api/v1/tailor", json=body)
    data = r.json()
    assert data["mode"] == "rules" and data["grounding"]["ok"]
    runs = client.get("/api/v1/history").json()["runs"]
    assert runs[0]["id"] == data["run_id"]
    assert client.delete(f"/api/v1/history/{data['run_id']}").status_code == 200


def test_validation(client):
    assert client.post("/api/v1/score", json={"resume_text": "short", "job_description": "x"}).status_code == 422


@pytest.mark.parametrize("fmt", ["pdf", "docx", "md"])
def test_export_handles_markup_chars(client, fmt):
    r = client.post(f"/api/v1/export/{fmt}", json={"resume_text": "Jane & Co <dev>\nSKILLS\n• C++ & Rust"})
    assert r.status_code == 200 and len(r.content) > 20


def test_parse_txt_upload(client):
    r = client.post("/api/v1/parse", files={"file": ("cv.txt", b"Jane Doe\nEXPERIENCE\n- stuff", "text/plain")})
    assert r.json()["text"].startswith("Jane Doe")
    bad = client.post("/api/v1/parse", files={"file": ("cv.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 415


def test_cover_letter_needs_key(client, resume_text, jd_text):
    r = client.post("/api/v1/cover-letter", json={"resume_text": resume_text, "job_description": jd_text})
    assert r.status_code == 400

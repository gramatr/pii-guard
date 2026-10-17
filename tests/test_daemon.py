from fastapi.testclient import TestClient

from pii_guard import engine
from pii_guard.daemon import app


def setup_module():
    engine.load_engines()


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["engines_loaded"] is True


def test_about_has_no_hosted_tier_claim():
    with TestClient(app) as client:
        resp = client.get("/about")
        assert resp.status_code == 200
        body = resp.json()
        assert "none" in body["hosted_tier"].lower()


def test_analyze_no_auth_required():
    """Unlike injection-guard, there is no AUTH_TOKEN concept here at
    all — this test documents that absence is deliberate (see README
    "Why no hosted tier"), not an oversight."""
    with TestClient(app) as client:
        resp = client.post("/analyze", json={"text": "hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert "found" in body and "redacted_text" in body and "entities" in body

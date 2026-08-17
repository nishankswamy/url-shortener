"""Auth is off until API_KEYS is set, and total once it is."""

import pytest

from app.config import settings


@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setattr(settings, "api_keys", ["secret-key", "second-key"])


def test_open_mode_needs_no_key(client):
    assert client.post(
        "/api/links", json={"target_url": "https://example.com"}
    ).status_code == 201


def test_missing_key_rejected(client, secured):
    response = client.post("/api/links", json={"target_url": "https://example.com"})
    assert response.status_code == 401


def test_wrong_key_rejected(client, secured):
    response = client.post(
        "/api/links",
        json={"target_url": "https://example.com"},
        headers={"X-API-Key": "nope"},
    )
    assert response.status_code == 403


def test_valid_key_accepted(client, secured):
    response = client.post(
        "/api/links",
        json={"target_url": "https://example.com"},
        headers={"X-API-Key": "secret-key"},
    )
    assert response.status_code == 201


def test_any_configured_key_works(client, secured):
    response = client.post(
        "/api/links",
        json={"target_url": "https://example.com"},
        headers={"X-API-Key": "second-key"},
    )
    assert response.status_code == 201


def test_analytics_are_protected(client, secured):
    assert client.get("/api/links").status_code == 401
    assert client.get("/api/links/abc/stats").status_code == 401


def test_redirects_stay_public(client, secured):
    """The product doesn't work if short links need a key."""
    code = client.post(
        "/api/links",
        json={"target_url": "https://example.com/public"},
        headers={"X-API-Key": "secret-key"},
    ).json()["short_code"]

    response = client.get(f"/{code}")
    assert response.status_code == 307


def test_health_reports_auth_mode(client, secured):
    assert client.get("/health").json()["auth"] == "enabled"


def test_health_reports_open_mode(client):
    assert client.get("/health").json()["auth"] == "open"

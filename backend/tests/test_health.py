"""Tests for GET /api/health."""


def test_health_reports_ok_with_database(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_503_without_database(client_without_database):
    response = client_without_database.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_unknown_address_gives_404(client):
    assert client.get("/api/does-not-exist").status_code == 404

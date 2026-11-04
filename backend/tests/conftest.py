import os
import pathlib

# Configure test environment BEFORE the app package is imported.
TEST_DB = "test_civic.db"
if pathlib.Path(TEST_DB).exists():
    os.remove(TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SEED_ON_START"] = "true"
os.environ.setdefault("EMBEDDER", "sentence")

import pytest


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post(
        "/api/auth/login", json={"email": "admin@civic.demo", "password": "admin123"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def citizen_token(client):
    r = client.post(
        "/api/auth/login", json={"email": "citizen1@civic.demo", "password": "demo123"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def team_token(client):
    r = client.post(
        "/api/auth/login", json={"email": "team1@civic.demo", "password": "demo123"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]

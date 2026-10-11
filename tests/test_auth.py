import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-for-auth-tests")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("FIREWALL_GROQ_API_KEY", "test-firewall-groq-key")

from jose import jwt
from fastapi.testclient import TestClient
from app.main import app


def test_login_valid_credentials():
    client = TestClient(app)
    response = client.post(
        "/auth/token",
        data={"username": "alice.johnson@meridianglobal.example", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    client = TestClient(app)
    response = client.post(
        "/auth/token",
        data={"username": "alice.johnson@meridianglobal.example", "password": "wrongpass"},
    )
    assert response.status_code == 401


def test_login_unknown_email():
    client = TestClient(app)
    response = client.post(
        "/auth/token",
        data={"username": "nobody@nowhere.example", "password": "password123"},
    )
    assert response.status_code == 401


def test_me_without_token():
    client = TestClient(app)
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_with_valid_token():
    client = TestClient(app)
    login_res = client.post(
        "/auth/token",
        data={"username": "alice.johnson@meridianglobal.example", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice.johnson@meridianglobal.example"
    assert data["role"] == "employee"


def test_query_without_auth():
    client = TestClient(app)
    response = client.post("/query", json={"query": "hello"})
    assert response.status_code == 401


def test_expired_token_rejected():
    client = TestClient(app)
    payload = {"sub": "E1001", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}
    token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

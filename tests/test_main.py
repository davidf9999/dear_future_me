# tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ping():
    res = client.get("/ping")
    assert res.status_code == 200
    assert res.json() == {"ping": "pong"}

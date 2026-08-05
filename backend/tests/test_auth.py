"""
Unit tests for Telegram initData HMAC verification and Auth API endpoints.
"""

import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from auth import verify_telegram_init_data
from api import app

TEST_BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"


def generate_init_data(bot_token: str, user_dict: dict, query_id: str = "AAH1234", auth_date: int = 1700000000) -> str:
    """Helper to generate a cryptographically valid Telegram WebApp initData string."""
    user_json = json.dumps(user_dict, separators=(",", ":"))
    data_dict = {
        "auth_date": str(auth_date),
        "query_id": query_id,
        "user": user_json,
    }
    # Sort key=value pairs by key
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    data_dict["hash"] = hash_value
    return urlencode(data_dict)


def test_verify_telegram_init_data_valid():
    user = {"id": 965000782, "first_name": "TestUser", "username": "test_user"}
    init_data = generate_init_data(TEST_BOT_TOKEN, user)

    res = verify_telegram_init_data(init_data, TEST_BOT_TOKEN)
    assert res is not None
    assert isinstance(res, dict)
    assert "user" in res
    assert res["user"]["id"] == 965000782
    assert res["user"]["first_name"] == "TestUser"


def test_verify_telegram_init_data_invalid():
    user = {"id": 965000782, "first_name": "TestUser", "username": "test_user"}
    init_data = generate_init_data(TEST_BOT_TOKEN, user)

    # Tamper with the init_data string
    tampered_init_data = init_data + "&extra=hacked"
    res = verify_telegram_init_data(tampered_init_data, TEST_BOT_TOKEN)
    assert res is None

    # Tampered bot token
    res_wrong_token = verify_telegram_init_data(init_data, "wrong_token_123")
    assert res_wrong_token is None

    # Empty string
    res_empty = verify_telegram_init_data("", TEST_BOT_TOKEN)
    assert res_empty is None


def test_auth_verify_endpoint_valid():
    client = TestClient(app)
    user = {"id": 965000782, "first_name": "TestUser", "username": "test_user"}
    from config import settings
    token = settings.bot_token.get_secret_value()
    init_data = generate_init_data(token, user)

    response = client.post("/api/auth/verify", json={"init_data": init_data})
    assert response.status_code == 200
    data = response.json()
    assert data.get("valid") is True
    assert "data" in data


def test_auth_verify_endpoint_invalid():
    client = TestClient(app)
    response = client.post("/api/auth/verify", json={"init_data": "invalid_init_data_hash"})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


def test_dev_mode_backdoor_is_closed():
    """Regression test: the legacy `dev_mode_<id>` Bearer fallback must NOT
    authenticate. Previously anyone could become any user (incl. admins) by
    sending `Authorization: Bearer dev_mode_965000782`."""
    client = TestClient(app)

    # Regular user endpoint rejects the dev_mode token
    resp = client.get("/api/profile", headers={"Authorization": "Bearer dev_mode_965000782"})
    assert resp.status_code == 401

    # The /api/auth/tma endpoint also rejects synthetic dev_mode init_data
    resp_tma = client.post("/api/auth/tma", json={"init_data": "dev_mode_965000782"})
    assert resp_tma.status_code == 400


def test_jwt_token_has_expiry():
    """JWT tokens must carry an `exp` claim (no perpetual tokens)."""
    from api import create_jwt_token
    import jwt as _jwt
    from config import settings

    token = create_jwt_token(965000782)
    payload = _jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
    )
    assert "exp" in payload
    assert "iat" in payload
    assert int(payload["sub"]) == 965000782

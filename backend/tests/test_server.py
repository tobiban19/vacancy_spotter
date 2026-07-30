"""
Unit tests for FastAPI server entry point, CORS middleware, and route integration.
"""

import pytest
from fastapi.testclient import TestClient
from server import app
from fastapi.middleware.cors import CORSMiddleware


def test_cors_middleware_present():
    """Verify CORSMiddleware is attached to FastAPI app instance in server.py."""
    has_cors = any(getattr(m, "cls", None) == CORSMiddleware for m in app.user_middleware)
    assert has_cors is True, "CORSMiddleware must be present on server.app"


def test_cors_preflight_and_headers():
    """Verify CORS headers respond with '*' for Telegram Mini App Vercel domain."""
    with TestClient(app) as client:
        # Test preflight OPTIONS request from Telegram Mini App domain on Vercel
        headers = {
            "Origin": "https://vacancy-spotter-app.vercel.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        }
        response = client.options("/api/professions", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") in ["*", "https://vacancy-spotter-app.vercel.app"]


def test_api_professions_route():
    """Verify /api/professions route works via TestClient."""
    with TestClient(app) as client:
        response = client.get("/api/professions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert any(p["id"] == "video_editor" for p in data)


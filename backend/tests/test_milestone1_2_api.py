"""
Comprehensive pytest test suite for Milestone 1.2:
Backend CRUD API for Profile, Portfolio & Channels.
"""

import sys
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import api
from api import app, create_jwt_token
from database import DatabaseRepository


@pytest_asyncio.fixture
async def async_client(tmp_path):
    test_db = tmp_path / "test_m1_2.sqlite3"
    test_repo = DatabaseRepository(test_db)
    await test_repo.open()

    original_repo = api.repo
    api.repo = test_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    await test_repo.close()
    api.repo = original_repo


@pytest.mark.asyncio
async def test_auth_security(async_client: AsyncClient):
    # 1. Missing Authorization header
    resp = await async_client.get("/api/profile")
    assert resp.status_code == 401
    assert "Missing or invalid Authorization header" in resp.json()["detail"]

    # 2. Invalid Authorization header scheme
    resp = await async_client.get("/api/profile", headers={"Authorization": "Basic 12345"})
    assert resp.status_code == 401

    # 3. Invalid JWT token
    resp = await async_client.get("/api/profile", headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == 401

    # 4. Valid JWT token
    token = create_jwt_token(999901)
    resp = await async_client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == 999901


@pytest.mark.asyncio
async def test_profile_crud(async_client: AsyncClient):
    user_id = 999902
    token = create_jwt_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # GET profile (initial creation)
    get_resp = await async_client.get("/api/profile", headers=headers)
    assert get_resp.status_code == 200
    p = get_resp.json()
    assert p["user_id"] == user_id
    assert p["profession_id"] == "video_editor"
    assert p["experience_years"] == 1
    assert p["stop_words"] == []

    # PUT profile (update fields)
    update_payload = {
        "profession_id": "motion_designer",
        "experience_years": 4,
        "location": "Москва",
        "stop_words": ["Низкий чек", "Без бюджета"],
        "bio_summary": "Опытный моушн-дизайнер 3D & 2D.",
        "software_stack": ["After Effects", "Cinema4D", "Blender"]
    }
    put_resp = await async_client.put("/api/profile", json=update_payload, headers=headers)
    assert put_resp.status_code == 200
    updated_p = put_resp.json()
    assert updated_p["profession_id"] == "motion_designer"
    assert updated_p["experience_years"] == 4
    assert updated_p["location"] == "Москва"
    assert "Низкий чек" in updated_p["stop_words"]
    assert updated_p["bio_summary"] == "Опытный моушн-дизайнер 3D & 2D."
    assert "Blender" in updated_p["software_stack"]

    # Verify persistent GET
    get_resp_2 = await async_client.get("/api/profile", headers=headers)
    assert get_resp_2.status_code == 200
    p2 = get_resp_2.json()
    assert p2["profession_id"] == "motion_designer"
    assert p2["experience_years"] == 4


@pytest.mark.asyncio
async def test_portfolio_crud_and_isolation(async_client: AsyncClient):
    user_a = 999903
    user_b = 999904
    headers_a = {"Authorization": f"Bearer {create_jwt_token(user_a)}"}
    headers_b = {"Authorization": f"Bearer {create_jwt_token(user_b)}"}

    # 1. User A initial portfolio is empty
    res = await async_client.get("/api/portfolio", headers=headers_a)
    assert res.status_code == 200
    assert res.json() == []

    # 2. User A adds portfolio item
    item_payload = {
        "title": "3D Motion Reel",
        "url": "https://vimeo.com/123456",
        "category": "motion",
        "orientation": "horizontal",
        "description": "Reel with Cinema4D & Octane render.",
        "tags": ["3d", "c4d", "octane"]
    }
    post_res = await async_client.post("/api/portfolio", json=item_payload, headers=headers_a)
    assert post_res.status_code == 200
    item_a = post_res.json()
    item_id = item_a["id"]
    assert item_a["user_id"] == user_a
    assert item_a["title"] == "3D Motion Reel"

    # 3. User B portfolio check (Multi-tenant Isolation!)
    res_b = await async_client.get("/api/portfolio", headers=headers_b)
    assert res_b.status_code == 200
    assert res_b.json() == []

    # 4. User B tries to update User A's item -> Should return 404
    update_payload = {
        "title": "Hacked Title",
        "url": "https://hacker.site",
        "category": "motion",
        "orientation": "horizontal",
        "description": "Hack attempt",
        "tags": []
    }
    put_b_res = await async_client.put(f"/api/portfolio/{item_id}", json=update_payload, headers=headers_b)
    assert put_b_res.status_code == 404

    # 5. User B tries to delete User A's item -> Should return 404
    del_b_res = await async_client.delete(f"/api/portfolio/{item_id}", headers=headers_b)
    assert del_b_res.status_code == 404

    # 6. User A updates their portfolio item
    update_payload["title"] = "Updated 3D Motion Reel 2026"
    update_payload["url"] = "https://vimeo.com/123456_updated"
    put_a_res = await async_client.put(f"/api/portfolio/{item_id}", json=update_payload, headers=headers_a)
    assert put_a_res.status_code == 200
    assert put_a_res.json()["title"] == "Updated 3D Motion Reel 2026"

    # 7. User A deletes their portfolio item
    del_a_res = await async_client.delete(f"/api/portfolio/{item_id}", headers=headers_a)
    assert del_a_res.status_code == 200
    assert del_a_res.json()["deleted_id"] == item_id

    # 8. User A portfolio is empty again
    res_a_final = await async_client.get("/api/portfolio", headers=headers_a)
    assert res_a_final.json() == []


@pytest.mark.asyncio
async def test_channels_crud_and_toggle(async_client: AsyncClient):
    user_a = 999905
    user_b = 999906
    headers_a = {"Authorization": f"Bearer {create_jwt_token(user_a)}"}
    headers_b = {"Authorization": f"Bearer {create_jwt_token(user_b)}"}

    # GET channels for default profession (video_editor)
    ch_res = await async_client.get("/api/channels", headers=headers_a)
    assert ch_res.status_code == 200
    channels_a = ch_res.json()
    assert len(channels_a) > 0
    target_channel = channels_a[0]
    ch_id = target_channel["id"]
    assert target_channel["is_enabled"] is True

    # User A toggles channel off
    toggle_res = await async_client.post("/api/channels/toggle", json={"channel_id": ch_id, "is_enabled": False}, headers=headers_a)
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_enabled"] is False

    # Check User A channels -> target channel is disabled
    ch_res_a2 = await async_client.get("/api/channels", headers=headers_a)
    for c in ch_res_a2.json():
        if c["id"] == ch_id:
            assert c["is_enabled"] is False

    # Check User B channels -> target channel remains enabled for User B!
    ch_res_b = await async_client.get("/api/channels", headers=headers_b)
    for c in ch_res_b.json():
        if c["id"] == ch_id:
            assert c["is_enabled"] is True

    # User A adds custom channel
    custom_res = await async_client.post("/api/channels/custom", json={"username_or_link": "https://t.me/my_test_channel"}, headers=headers_a)
    assert custom_res.status_code == 200
    custom_ch = custom_res.json()
    assert custom_ch["username"] == "my_test_channel"
    assert custom_ch["is_enabled"] is True

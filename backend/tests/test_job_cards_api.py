"""
Tests for the /api/cards endpoints (job cards in the Mini App):
listing, status updates, and draft regeneration.
"""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import api
from api import app, create_jwt_token
from database import DatabaseRepository
from models import JobCardCreateDTO, JobCardStatusEnum


@pytest_asyncio.fixture
async def cards_client(tmp_path):
    test_db = tmp_path / "test_cards.sqlite3"
    test_repo = DatabaseRepository(test_db)
    await test_repo.open()

    original_repo = api.repo
    api.repo = test_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, test_repo

    await test_repo.close()
    api.repo = original_repo


@pytest.mark.asyncio
async def test_list_cards_empty(cards_client):
    client, _ = cards_client
    user_id = 880001
    headers = {"Authorization": f"Bearer {create_jwt_token(user_id)}"}

    resp = await client.get("/api/cards", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_card_status_update_and_isolation(cards_client):
    client, repo = cards_client
    owner = 880002
    other = 880003
    headers_owner = {"Authorization": f"Bearer {create_jwt_token(owner)}"}
    headers_other = {"Authorization": f"Bearer {create_jwt_token(other)}"}

    # Ensure both users exist (FK constraint on user_job_cards.user_id)
    await repo.get_or_create_user({"id": owner, "first_name": "Owner"})
    await repo.get_or_create_user({"id": other, "first_name": "Other"})

    # Create a card for the owner directly via the repository
    card = await repo.create_job_card(
        JobCardCreateDTO(
            user_id=owner,
            channel_title="Test",
            channel_username="test_ch",
            post_text="Ищем монтажера reels, оплата 5000р",
            status=JobCardStatusEnum.NEW,
            draft_reply="Здравствуйте!",
        )
    )

    # Owner updates status -> saved
    resp = await client.put(
        f"/api/cards/{card.id}/status",
        json={"status": "saved"},
        headers=headers_owner,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"

    # Other user cannot see or update the owner's card (multi-tenant isolation)
    resp_other = await client.put(
        f"/api/cards/{card.id}/status",
        json={"status": "rejected"},
        headers=headers_other,
    )
    assert resp_other.status_code == 404

    # Owner still sees saved status
    listing = await client.get("/api/cards", headers=headers_owner)
    assert listing.json()[0]["status"] == "saved"


@pytest.mark.asyncio
async def test_card_regenerate_updates_draft(cards_client):
    client, repo = cards_client
    user_id = 880004
    headers = {"Authorization": f"Bearer {create_jwt_token(user_id)}"}

    # Ensure the user profile exists (needed for regenerate)
    await repo.get_or_create_user({"id": user_id, "first_name": "Алекс"})

    card = await repo.create_job_card(
        JobCardCreateDTO(
            user_id=user_id,
            channel_title="Test",
            channel_username="test_ch",
            post_text="Нужен видеограф на свадьбу, бюджет 10000р",
            status=JobCardStatusEnum.NEW,
            draft_reply="старый шаблон",
        )
    )

    resp = await client.post(
        f"/api/cards/{card.id}/regenerate",
        json={"custom_instruction": "сделай тон более официальным"},
        headers=headers,
    )
    assert resp.status_code == 200
    new_draft = resp.json()["draft_reply"]
    assert new_draft != "старый шаблон"
    # The generated draft references the user's name
    assert "Алекс" in new_draft
    assert "сделай тон более официальным" in new_draft


@pytest.mark.asyncio
async def test_card_regenerate_not_found(cards_client):
    client, _ = cards_client
    headers = {"Authorization": f"Bearer {create_jwt_token(880005)}"}
    resp = await client.post(
        "/api/cards/999999/regenerate",
        json={"custom_instruction": ""},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cards_require_auth(cards_client):
    client, _ = cards_client
    # No auth header
    resp = await client.get("/api/cards")
    assert resp.status_code == 401

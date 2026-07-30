"""
Unit and Integration tests for Telegram Bot Interactive Cards & Ingest API (Milestone 1.3 - Task 2).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import api
import bot_service
from api import app
from database import DatabaseRepository
from models import JobCardCreateDTO, JobCardDTO, JobCardStatusEnum, UserProfileUpdateDTO


@pytest_asyncio.fixture
async def test_env(tmp_path):
    test_db = tmp_path / "test_task2.sqlite3"
    test_repo = DatabaseRepository(test_db)
    await test_repo.open()

    # Patch repo in api and bot_service
    orig_api_repo = api.repo
    orig_bot_repo = bot_service.repo

    api.repo = test_repo
    bot_service.repo = test_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield test_repo, client

    await test_repo.close()
    api.repo = orig_api_repo
    bot_service.repo = orig_bot_repo


@pytest.mark.asyncio
async def test_send_job_card_to_user():
    """Test send_job_card_to_user formats message and sends inline keyboard."""
    mock_bot = AsyncMock()
    mock_msg = MagicMock()
    mock_bot.send_message.return_value = mock_msg

    from datetime import datetime, timezone
    card = JobCardDTO(
        id=101,
        user_id=965000782,
        channel_title="Видеомонтаж | Фриланс",
        channel_username="freelance_video",
        post_text="Нужен монтажёр для Reels и Shorts, 5000р/ролик",
        post_url="https://t.me/freelance_video/123",
        status=JobCardStatusEnum.NEW,
        match_score=0.95,
        matched_keywords=["reels", "shorts"],
        draft_reply="",
        created_at=datetime.now(timezone.utc),
    )

    res = await bot_service.send_job_card_to_user(mock_bot, card)

    assert res == mock_msg
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == 965000782
    assert "Видеомонтаж | Фриланс" in call_kwargs["text"]
    assert "https://t.me/freelance_video/123" in call_kwargs["text"]
    assert "reels, shorts" in call_kwargs["text"]
    assert call_kwargs["reply_markup"] is not None
    # Inline keyboard buttons check
    inline_kb = call_kwargs["reply_markup"].inline_keyboard
    assert len(inline_kb) == 1
    assert inline_kb[0][0].callback_data == "approve:101"
    assert inline_kb[0][1].callback_data == "skip:101"


@pytest.mark.asyncio
async def test_callback_query_approve_and_skip(test_env):
    test_repo, _ = test_env

    # Setup user and job card in DB
    user_id = 888111
    await test_repo.get_or_create_user({"id": user_id, "first_name": "Test User"})

    card = await test_repo.create_job_card(
        JobCardCreateDTO(
            user_id=user_id,
            channel_title="Test Channel",
            channel_username="test_ch",
            post_text="Нужен видеомонтажёр",
        )
    )
    assert card.status == JobCardStatusEnum.NEW

    # 1. Test approve callback
    mock_query_approve = MagicMock()
    mock_query_approve.from_user.id = user_id
    mock_query_approve.data = f"approve:{card.id}"
    mock_query_approve.answer = AsyncMock()
    mock_query_approve.message = MagicMock()
    mock_query_approve.message.edit_reply_markup = AsyncMock()

    await bot_service.process_approve_job_card(mock_query_approve)

    updated_card_1 = await test_repo.get_job_card_by_id(card.id, user_id)
    assert updated_card_1.status == JobCardStatusEnum.APPLIED
    mock_query_approve.answer.assert_called_once_with("✅ Отклик отправлен! Заявка одобрена.", show_alert=True)
    mock_query_approve.message.edit_reply_markup.assert_called_once_with(reply_markup=None)

    # 2. Test skip callback
    card2 = await test_repo.create_job_card(
        JobCardCreateDTO(
            user_id=user_id,
            channel_title="Test Channel 2",
            channel_username="test_ch_2",
            post_text="Нужен дизайнер",
        )
    )

    mock_query_skip = MagicMock()
    mock_query_skip.from_user.id = user_id
    mock_query_skip.data = f"skip:{card2.id}"
    mock_query_skip.answer = AsyncMock()
    mock_query_skip.message = MagicMock()
    mock_query_skip.message.edit_reply_markup = AsyncMock()

    await bot_service.process_skip_job_card(mock_query_skip)

    updated_card_2 = await test_repo.get_job_card_by_id(card2.id, user_id)
    assert updated_card_2.status == JobCardStatusEnum.REJECTED
    mock_query_skip.answer.assert_called_once_with("⏩ Вакансия пропущена", show_alert=False)


@pytest.mark.asyncio
async def test_incoming_jobs_api_and_stop_words(test_env):
    test_repo, client = test_env

    # Create User 1 (Subscribed to default channel freelance_video, no stop-words)
    user_1_id = 777001
    await test_repo.get_or_create_user({"id": user_1_id, "first_name": "User One"})

    # Create User 2 (Subscribed to default channel freelance_video, HAS stop-word "казино")
    user_2_id = 777002
    await test_repo.get_or_create_user({"id": user_2_id, "first_name": "User Two"})
    await test_repo.update_user_profile(user_2_id, UserProfileUpdateDTO(stop_words=["казино", "crypto"]))

    # Test POST /api/jobs/incoming with a post containing "казино"
    payload = {
        "channel_username": "freelance_video",
        "post_text": "Ищем монтажёра для роликов Казино и Гемблинг!",
        "post_url": "https://t.me/freelance_video/555",
        "channel_title": "Видеомонтаж | Фриланс Заказы",
    }

    with patch("bot_service.send_job_card_to_user", new_callable=AsyncMock) as mock_send:
        resp = await client.post("/api/jobs/incoming", json=payload)
        assert resp.status_code == 200
        res_data = resp.json()

        assert res_data["status"] == "success"
        assert res_data["users_matched"] == 2
        assert res_data["cards_created"] == 1  # User 2 blocked by stop-words!

        # Check DB cards for User 1
        user_1_cards = await test_repo.get_user_job_cards(user_1_id)
        assert len(user_1_cards) == 1
        assert user_1_cards[0].channel_username == "freelance_video"

        # Check DB cards for User 2 (must be 0!)
        user_2_cards = await test_repo.get_user_job_cards(user_2_id)
        assert len(user_2_cards) == 0

        # Verify bot send_job_card_to_user was called for User 1
        assert mock_send.call_count == 1

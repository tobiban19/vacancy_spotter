"""
Unit tests for Telegram Bot Rewrite/Regen Callbacks & Text Message Handler (Task 3).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import bot_service
from database import DatabaseRepository
from models import JobCardCreateDTO, JobCardStatusEnum


@pytest_asyncio.fixture
async def test_env(tmp_path):
    test_db = tmp_path / "test_regen.sqlite3"
    test_repo = DatabaseRepository(test_db)
    await test_repo.open()

    orig_bot_repo = bot_service.repo
    bot_service.repo = test_repo

    bot_service.USER_REGEN_WAITING.clear()

    yield test_repo

    await test_repo.close()
    bot_service.repo = orig_bot_repo
    bot_service.USER_REGEN_WAITING.clear()


@pytest.mark.asyncio
async def test_rewrite_callback_registers_regen_waiting(test_env):
    """Test rewrite callback registers USER_REGEN_WAITING and sends draft message."""
    test_repo = test_env
    user_id = 999001
    await test_repo.get_or_create_user({"id": user_id, "first_name": "Rewrite User"})

    card = await test_repo.create_job_card(
        JobCardCreateDTO(
            user_id=user_id,
            channel_title="Test Channel",
            channel_username="test_ch",
            post_text="Нужен Python разработчик",
            draft_reply="Привет, я разработчик Python",
        )
    )

    mock_query = MagicMock()
    mock_query.from_user.id = user_id
    mock_query.data = f"rewrite:{card.id}"
    mock_query.answer = AsyncMock()
    mock_query.message = MagicMock()
    mock_query.message.answer = AsyncMock()

    await bot_service.process_rewrite_job_card(mock_query)

    # Verify registration in USER_REGEN_WAITING
    assert bot_service.USER_REGEN_WAITING.get(user_id) == card.id

    # Verify answer was called with draft inside <code> block and prompt for wishes
    mock_query.message.answer.assert_called_once()
    sent_text = mock_query.message.answer.call_args.args[0]
    assert f"#{card.id}" in sent_text
    assert "<code>Привет, я разработчик Python</code>" in sent_text
    assert "пожелания к отклику" in sent_text


@pytest.mark.asyncio
async def test_regen_callback_registers_regen_waiting(test_env):
    """Test regen callback registers USER_REGEN_WAITING and prompts user."""
    test_repo = test_env
    user_id = 999002
    await test_repo.get_or_create_user({"id": user_id, "first_name": "Regen User"})

    mock_query = MagicMock()
    mock_query.from_user.id = user_id
    mock_query.data = "regen:123"
    mock_query.answer = AsyncMock()
    mock_query.message = MagicMock()
    mock_query.message.answer = AsyncMock()

    await bot_service.process_regen_job_card(mock_query)

    assert bot_service.USER_REGEN_WAITING.get(user_id) == 123
    mock_query.message.answer.assert_called_once()
    assert "#123" in mock_query.message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_handle_user_text_message_updates_draft_and_clears_waiting(test_env):
    """Test handle_user_text_message generates new draft, updates DB, and removes user from USER_REGEN_WAITING."""
    test_repo = test_env
    user_id = 999003
    await test_repo.get_or_create_user({"id": user_id, "first_name": "Alex"})

    card = await test_repo.create_job_card(
        JobCardCreateDTO(
            user_id=user_id,
            channel_title="Python Jobs",
            channel_username="py_jobs",
            post_text="Нужен Backend Dev на Django",
        )
    )

    # Register waiting state
    bot_service.USER_REGEN_WAITING[user_id] = card.id

    mock_message = MagicMock()
    mock_message.from_user.id = user_id
    mock_message.text = "Сделай более официальный тон и добавь опыт 3 года"
    mock_message.answer = AsyncMock()

    await bot_service.handle_user_text_message(mock_message)

    # Verify user removed from USER_REGEN_WAITING
    assert user_id not in bot_service.USER_REGEN_WAITING

    # Verify card draft in DB was updated
    updated_card = await test_repo.get_job_card_by_id(card.id, user_id)
    assert updated_card.draft_reply != ""
    assert "Сделай более официальный тон и добавь опыт 3 года" in updated_card.draft_reply

    # Verify response sent to user
    mock_message.answer.assert_called_once()
    sent_text = mock_message.answer.call_args.args[0]
    assert f"Вакансия #{card.id}" in sent_text
    assert "Сделай более официальный тон и добавь опыт 3 года" in sent_text


@pytest.mark.asyncio
async def test_handle_user_text_message_error_handling(test_env):
    """Test handle_user_text_message handles exceptions gracefully and notifies user."""
    test_repo = test_env
    user_id = 999004
    await test_repo.get_or_create_user({"id": user_id, "first_name": "Error User"})

    card = await test_repo.create_job_card(
        JobCardCreateDTO(
            user_id=user_id,
            channel_title="Dev Jobs",
            channel_username="dev_jobs",
            post_text="Looking for dev",
        )
    )

    bot_service.USER_REGEN_WAITING[user_id] = card.id

    mock_message = MagicMock()
    mock_message.from_user.id = user_id
    mock_message.text = "Custom instruction"
    mock_message.answer = AsyncMock()

    with patch("bot_service.generate_draft_reply", side_effect=RuntimeError("AI model error")):
        await bot_service.handle_user_text_message(mock_message)

    # Verify state cleaned up
    assert user_id not in bot_service.USER_REGEN_WAITING

    # Verify error notification sent to user
    mock_message.answer.assert_called_once()
    assert "Ошибка при перегенерации отклика" in mock_message.answer.call_args.args[0]

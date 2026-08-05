"""
Unit tests for Telethon parser draft reply generation & intent filtering integration (Task 2).
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
import telethon_parser
from database import DatabaseRepository
from matching_service import generate_draft_reply, is_vacancy_post
from models import JobCardCreateDTO, UserProfileUpdateDTO


@pytest_asyncio.fixture
async def test_env(tmp_path):
    test_db = tmp_path / "test_parser_draft.sqlite3"
    test_repo = DatabaseRepository(test_db)
    await test_repo.open()

    orig_parser_repo = telethon_parser.repo
    orig_bot_repo = bot_service.repo

    telethon_parser.repo = test_repo
    bot_service.repo = test_repo

    yield test_repo

    await test_repo.close()
    telethon_parser.repo = orig_parser_repo
    bot_service.repo = orig_bot_repo


@pytest.mark.asyncio
async def test_non_vacancy_chat_filtered_by_parser(test_env):
    """
    Test that non-vacancy post containing keywords is classified by is_vacancy_post
    and filtered out without creating job cards or sending messages.
    """
    test_repo = test_env

    # Seed user subscribed to default channel (editors_video)
    user_id = 999101
    user_profile = await test_repo.get_or_create_user({"id": user_id, "first_name": "Алексей"})
    assert user_profile is not None

    # Chat post with keyword 'видеомонтаж' but NO vacancy intent (chat question)
    text = "Ребята, подскажите, кто знает, как сделать качественный видеомонтаж и цветокоррекцию в DaVinci?"

    # Verify is_vacancy_post standalone classification
    is_vac, score, triggers = is_vacancy_post(text)
    assert not is_vac
    assert score < 0.3

    # Mock Telegram Event
    mock_chat = MagicMock()
    mock_chat.username = "editors_video"
    mock_chat.title = "Монтажеры | Видеомонтаж"

    mock_event = MagicMock()
    mock_event.text = text
    mock_event.id = 501
    mock_event.get_chat = AsyncMock(return_value=mock_chat)

    with patch("bot_service.send_job_card_to_user", new_callable=AsyncMock) as mock_send, \
         patch("bot_service.get_bot") as mock_get_bot:
        mock_bot = AsyncMock()
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="vacancy_spott_bot"))
        mock_get_bot.return_value = mock_bot

        await telethon_parser.handle_new_channel_post(mock_event)

        # Job card should NOT be created for non-vacancy chat
        cards = await test_repo.get_user_job_cards(user_id)
        assert len(cards) == 0
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_vacancy_post_generates_draft_reply_and_creates_card(test_env):
    """
    Test that a valid vacancy post passes intent check, generates personalized draft reply,
    and sets draft_reply and match_score on JobCardCreateDTO and stored card.
    """
    test_repo = test_env

    user_id = 999102
    await test_repo.get_or_create_user({"id": user_id, "first_name": "Мария"})
    await test_repo.update_user_profile(
        user_id,
        UserProfileUpdateDTO(
            experience_years=4,
            bio_summary="Специализируюсь на динамичном монтаже Reels, Shorts и TikTok.",
            software_stack=["Premiere Pro", "After Effects", "CapCut"],
        ),
    )

    updated_profile = await test_repo.get_user_profile(user_id)

    # Post with keyword 'reels' AND clear vacancy hiring intent
    text = "Ищу монтажёра для Reels и Shorts! Нужен динамичный видеомонтаж, оплата 4000р/ролик. ТЗ в ЛС @hr_video"

    is_vac, vac_score, vac_triggers = is_vacancy_post(text)
    assert is_vac
    assert vac_score >= 0.3

    # Generate reference draft reply
    expected_draft = await generate_draft_reply(updated_profile, text)
    assert "Здравствуйте! Меня зовут Мария." in expected_draft
    assert "4 года" in expected_draft
    assert "Premiere Pro, After Effects, CapCut" in expected_draft
    assert "Специализируюсь на динамичном монтаже Reels" in expected_draft

    mock_chat = MagicMock()
    mock_chat.username = "editors_video"
    mock_chat.title = "Монтажеры | Видеомонтаж"

    mock_event = MagicMock()
    mock_event.text = text
    mock_event.id = 502
    mock_event.get_chat = AsyncMock(return_value=mock_chat)

    with patch("bot_service.send_job_card_to_user", new_callable=AsyncMock) as mock_send, \
         patch("bot_service.get_bot") as mock_get_bot:
        mock_bot = AsyncMock()
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="vacancy_spott_bot"))
        mock_get_bot.return_value = mock_bot
        mock_send.return_value = MagicMock()

        await telethon_parser.handle_new_channel_post(mock_event)

        # Verify job card was created in DB
        cards = await test_repo.get_user_job_cards(user_id)
        assert len(cards) == 1
        card = cards[0]
        assert card.user_id == user_id
        assert card.channel_username == "editors_video"
        assert card.match_score == vac_score
        assert card.draft_reply != ""
        assert card.draft_reply == expected_draft

        # Verify bot service received card with non-empty draft_reply
        mock_send.assert_called_once()
        sent_card = mock_send.call_args[0][1]
        assert sent_card.draft_reply == expected_draft
        assert sent_card.match_score == vac_score


def test_job_card_create_dto_draft_reply():
    """
    Unit test for JobCardCreateDTO schema containing non-empty draft_reply.
    """
    draft_text = "Здравствуйте! Меня зовут Илья. Мой опыт — 2 года."
    dto = JobCardCreateDTO(
        user_id=12345,
        channel_title="Test Channel",
        channel_username="test_channel",
        post_text="Нужен видеомонтажёр",
        match_score=0.7,
        draft_reply=draft_text,
    )
    assert dto.draft_reply == draft_text
    assert dto.match_score == 0.7

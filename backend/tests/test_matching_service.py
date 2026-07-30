"""
Pytest unit tests for matching_service.py and DatabaseRepository Job Cards CRUD.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
import pytest
import pytest_asyncio

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from database import DatabaseRepository
from models import (
    JobCardCreateDTO,
    JobCardDTO,
    JobCardStatusEnum,
    UserProfileDTO,
)
from matching_service import (
    calculate_match_score,
    generate_draft_reply,
    should_filter_by_stop_words,
)


# ---------------------------------------------------------------------------
# Matching Service Unit Tests
# ---------------------------------------------------------------------------

def test_should_filter_by_stop_words_empty():
    assert should_filter_by_stop_words("", ["бесплатно"]) is False
    assert should_filter_by_stop_words("Нужен монтажер", []) is False
    assert should_filter_by_stop_words("", []) is False


def test_should_filter_by_stop_words_matches():
    stop_words = ["бартер", "низкий чек", "оплата отзывом"]
    text1 = "Ищем монтажера на БАРТЕР для YouTube канала"
    text2 = "Проект без денег, низкий чек по 100 рублей"
    text3 = "Срочно требуется видеомонтажер в команду, ставка 5000р/ролик"

    assert should_filter_by_stop_words(text1, stop_words) is True
    assert should_filter_by_stop_words(text2, stop_words) is True
    assert should_filter_by_stop_words(text3, stop_words) is False


def test_should_filter_by_stop_words_whitespace_and_case():
    stop_words = ["  СТАЖИРОВКА  ", "Без Оплаты"]
    assert should_filter_by_stop_words("Предлагается стажировка в агентстве", stop_words) is True
    assert should_filter_by_stop_words("Опыт от 1 года, без оплаты не работаем", stop_words) is True


def test_calculate_match_score():
    text = "Ищем видеомонтажера со знанием Premier Pro и After Effects на Reels"
    keywords = ["Premier Pro", "After Effects", "Davinci", "3D"]

    score, matched = calculate_match_score(text, keywords)
    assert score == 0.5
    assert "Premier Pro" in matched
    assert "After Effects" in matched
    assert "Davinci" not in matched


def test_generate_draft_reply_with_dto():
    now = datetime.now(timezone.utc)
    profile = UserProfileDTO(
        user_id=1001,
        first_name="Алексей",
        experience_years=3,
        bio_summary="Специализируюсь на коротких динамичных Reels.",
        software_stack=["Premiere Pro", "After Effects"],
        demo_until=now,
    )
    reply = generate_draft_reply(profile)
    assert "Алексей" in reply
    assert "3 года" in reply
    assert "Premiere Pro, After Effects" in reply
    assert "Специализируюсь на коротких динамичных Reels." in reply


def test_generate_draft_reply_with_dict():
    profile_dict = {
        "first_name": "Елена",
        "experience_years": 5,
        "bio_summary": "Создаю 2D и 3D анимации.",
        "software_stack": ["Cinema4D", "Blender"],
    }
    reply = generate_draft_reply(profile_dict)
    assert "Елена" in reply
    assert "5 лет" in reply
    assert "Cinema4D, Blender" in reply
    assert "Создаю 2D и 3D анимации." in reply


# ---------------------------------------------------------------------------
# Database Job Cards Async Integration Tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_repo(tmp_path):
    db_file = tmp_path / "test_job_cards.sqlite3"
    repo = DatabaseRepository(db_file)
    await repo.open()
    yield repo
    await repo.close()


@pytest.mark.asyncio
async def test_job_card_db_crud(db_repo: DatabaseRepository):
    user_id = 900001
    await db_repo.get_or_create_user({"id": user_id, "first_name": "Test User"})

    # 1. Create Job Card
    card_dto = JobCardCreateDTO(
        user_id=user_id,
        channel_title="Фриланс Заказы",
        channel_username="freelance_video",
        post_text="Нужен видеомонтажер для Reels. Бюджет 5000 руб.",
        post_url="https://t.me/freelance_video/123",
        match_score=0.85,
        matched_keywords=["видеомонтажер", "Reels"],
        draft_reply="Здравствуйте! Готов выполнить заказ.",
    )
    created_card = await db_repo.create_job_card(card_dto)
    assert created_card.id is not None
    assert created_card.user_id == user_id
    assert created_card.status == JobCardStatusEnum.NEW
    assert created_card.match_score == 0.85
    assert "Reels" in created_card.matched_keywords

    # 2. Get User Job Cards
    user_cards = await db_repo.get_user_job_cards(user_id)
    assert len(user_cards) == 1
    assert user_cards[0].id == created_card.id

    # Filter by status "new"
    new_cards = await db_repo.get_user_job_cards(user_id, status=JobCardStatusEnum.NEW)
    assert len(new_cards) == 1

    # Filter by status "saved" -> should be empty
    saved_cards = await db_repo.get_user_job_cards(user_id, status=JobCardStatusEnum.SAVED)
    assert len(saved_cards) == 0

    # 3. Update Job Card Status
    updated_card = await db_repo.update_job_card_status(created_card.id, user_id, JobCardStatusEnum.SAVED)
    assert updated_card is not None
    assert updated_card.status == JobCardStatusEnum.SAVED

    # Verify updated status via GET
    saved_cards_2 = await db_repo.get_user_job_cards(user_id, status="saved")
    assert len(saved_cards_2) == 1
    assert saved_cards_2[0].id == created_card.id

    # 4. Multi-tenant isolation test (another user gets empty list)
    other_user_cards = await db_repo.get_user_job_cards(900002)
    assert len(other_user_cards) == 0

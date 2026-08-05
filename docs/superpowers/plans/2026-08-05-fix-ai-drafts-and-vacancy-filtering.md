# AI Draft Generation, Rewrite Handler & Vacancy Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix missing AI draft responses in Telegram vacancy cards, fix crash on custom instruction rewrites (`TypeError: custom_instruction`), and implement a smart Vacancy Intent Classifier to filter out non-vacancy chat messages.

**Architecture:** 
1. `backend/matching_service.py` receives a new `is_vacancy_post(text: str)` intent analyzer and an upgraded `generate_draft_reply(user_profile, job_text, custom_instruction="")` function supporting custom user prompt overrides.
2. `backend/telethon_parser.py` is updated to generate draft replies before saving `JobCardCreateDTO` and to run `is_vacancy_post()` before matching users.
3. `backend/bot_service.py` is updated to fix callback handling, remove `TypeError` in `handle_user_text_message`, and format draft responses cleanly.

**Tech Stack:** Python 3.11, Pytest, FastAPI, aiogram 3.x, Telethon, Pydantic v2.

## Global Constraints

- **Python Version**: Python 3.11+
- **Test Framework**: `pytest` with `PYTHONPATH=backend`
- **Zero Breaking Changes**: Preserve existing DB repository interfaces and Pydantic DTO models.

---

### Task 1: Vacancy Intent Classifier & `custom_instruction` Support in `matching_service.py`

**Files:**
- Modify: `backend/matching_service.py:1-82`
- Test: `backend/tests/test_matching_service.py`

**Interfaces:**
- Consumes: `user_profile: UserProfileDTO | dict[str, Any]`, `job_text: str`, `custom_instruction: str = ""`
- Produces: 
  - `is_vacancy_post(text: str) -> tuple[bool, float, list[str]]` (returns `(is_vacancy, confidence_score, matched_vacancy_triggers)`)
  - `generate_draft_reply(user_profile, job_text="", custom_instruction="") -> str`

- [ ] **Step 1: Write failing tests for `is_vacancy_post` and `custom_instruction` in `generate_draft_reply`**

```python
# backend/tests/test_matching_service.py
from matching_service import is_vacancy_post, generate_draft_reply

def test_is_vacancy_post_positive():
    vacancy_text = "Ищем видеомонтажера Reels! Оплата 5000р/ролик. ТЗ в ЛС, присылайте портфолио @recruiter."
    is_vac, score, triggers = is_vacancy_post(vacancy_text)
    assert is_vac is True
    assert score >= 0.5
    assert len(triggers) > 0

def test_is_vacancy_post_negative_discussion():
    chat_text = "Ребята, подскажите по видеомонтажу: какой эффект лучше использовать в After Effects для перехода?"
    is_vac, score, triggers = is_vacancy_post(chat_text)
    assert is_vac is False

def test_generate_draft_reply_with_custom_instruction():
    profile = {"first_name": "Павел", "experience_years": 3, "bio_summary": "Монтирую ролики"}
    instruction = "Укажи, что смогу сдать проект завтра"
    reply = generate_draft_reply(profile, job_text="Ищем монтажера", custom_instruction=instruction)
    assert "смогу сдать проект завтра" in reply
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend pytest backend/tests/test_matching_service.py -k "test_is_vacancy_post or test_generate_draft_reply_with_custom_instruction"`
Expected: FAIL (ImportError / TypeError)

- [ ] **Step 3: Implement `is_vacancy_post` and update `generate_draft_reply` in `matching_service.py`**

```python
# backend/matching_service.py
import re
from typing import Any
from models import UserProfileDTO

VACANCY_INTENT_TRIGGERS = [
    "ищу", "нужен", "требуется", "вакансия", "заказ", "оплата", "бюджет",
    "тз", "в команду", "отклик", "портфолио", "резюме", "в лс", "пишите в личку",
    "ставки", "гонорар", "руб", "рублей", "$", "usd", "/ролик", "/видео", "/месяц",
    "проекты", "напишите", "связь", "контакт"
]

NON_VACANCY_CHAT_TRIGGERS = [
    "кто знает", "подскажите", "как сделать", "посоветуйте", "оцените", "чекните",
    "какой лучше", "где скачать", "проблема с", "ошибка в", "почему не"
]

def is_vacancy_post(text: str) -> tuple[bool, float, list[str]]:
    """
    Analyzes whether a Telegram post represents a real job vacancy / client order.
    Returns (is_vacancy: bool, confidence_score: float, matched_triggers: list[str]).
    """
    if not text or len(text.strip()) < 15:
        return False, 0.0, []

    text_lower = text.lower()
    
    # Negative chatter check
    non_vacancy_matches = [tr for tr in NON_VACANCY_CHAT_TRIGGERS if tr in text_lower]
    
    matched_triggers = [tr for tr in VACANCY_INTENT_TRIGGERS if tr in text_lower]
    
    # Contains username (@username) or link (t.me/)
    has_contact = bool(re.search(r"@[a-zA-Z0-9_]+|t\.me/|https?://", text))
    if has_contact and "contact" not in matched_triggers:
        matched_triggers.append("contact_link")

    score = len(matched_triggers) * 0.3
    if non_vacancy_matches:
        score -= len(non_vacancy_matches) * 0.4

    is_vac = score >= 0.3 and len(matched_triggers) >= 1
    return is_vac, max(0.0, min(1.0, round(score, 2))), matched_triggers


def generate_draft_reply(
    user_profile: UserProfileDTO | dict[str, Any],
    job_text: str = "",
    custom_instruction: str = ""
) -> str:
    """
    Generates a personalized, professional draft reply for a job posting.
    Accepts custom_instruction to customize tone or add user notes.
    """
    if isinstance(user_profile, dict):
        first_name = user_profile.get("first_name", "Фрилансер")
        experience_years = user_profile.get("experience_years", 1)
        bio_summary = user_profile.get("bio_summary", "")
        software_stack = user_profile.get("software_stack", [])
    else:
        first_name = getattr(user_profile, "first_name", "Фрилансер")
        experience_years = getattr(user_profile, "experience_years", 1)
        bio_summary = getattr(user_profile, "bio_summary", "")
        software_stack = getattr(user_profile, "software_stack", [])

    exp_str = _format_experience_years(experience_years)
    lines = [f"Здравствуйте! Меня зовут {first_name}. Мой опыт работы — {exp_str}."]

    if software_stack:
        if isinstance(software_stack, list):
            stack_str = ", ".join(str(s) for s in software_stack if s)
        else:
            stack_str = str(software_stack)
        if stack_str:
            lines.append(f"Стек / инструменты: {stack_str}.")

    if bio_summary and bio_summary.strip():
        lines.append(bio_summary.strip())

    if custom_instruction and custom_instruction.strip():
        lines.append(f"📌 Дополнение: {custom_instruction.strip()}")

    lines.append("Заинтересовал ваш проект! Буду рад обсудить детали и приступить к выполнению.")
    return "\n\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_matching_service.py`
Expected: PASS

---

### Task 2: Fix Telethon Parser Draft Generation & Intent Filtering

**Files:**
- Modify: `backend/telethon_parser.py:86-175`
- Test: `backend/tests/test_server.py`

**Interfaces:**
- Consumes: `is_vacancy_post(event.text)`, `generate_draft_reply(u, event.text)`
- Produces: Populated `JobCardCreateDTO(..., draft_reply=draft)` sent via Telegram Bot.

- [ ] **Step 1: Write test verifying draft generation in `telethon_parser.py` pipeline**

```python
# backend/tests/test_parser_draft.py
import pytest
from matching_service import generate_draft_reply, is_vacancy_post
from models import UserProfileDTO, JobCardCreateDTO

def test_parser_card_creation_includes_draft():
    user = UserProfileDTO(
        user_id=123,
        first_name="Иван",
        experience_years=2,
        bio_summary="Делаю качественный видеомонтаж",
        demo_until="2030-01-01T00:00:00"
    )
    post_text = "Нужен видеомонтажер Reels! Оплата 3000р. Писать @manager."
    
    is_vac, _, _ = is_vacancy_post(post_text)
    assert is_vac is True

    draft = generate_draft_reply(user, post_text)
    card_dto = JobCardCreateDTO(
        user_id=user.user_id,
        channel_title="Тест Канал",
        channel_username="test_channel",
        post_text=post_text,
        draft_reply=draft,
    )
    assert card_dto.draft_reply != ""
    assert "Иван" in card_dto.draft_reply
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_parser_draft.py`
Expected: PASS

- [ ] **Step 3: Update `backend/telethon_parser.py`**

In `backend/telethon_parser.py`:
1. Import `is_vacancy_post` and `generate_draft_reply` from `matching_service`.
2. Check `is_vac, score, triggers = is_vacancy_post(event.text)` before matching users. If `not is_vac`, skip the post (filtering out non-vacancy discussions).
3. Inside the user loop, call `draft = generate_draft_reply(u, event.text)` and pass `draft_reply=draft` into `JobCardCreateDTO(...)`.

```python
# In backend/telethon_parser.py handle_new_channel_post:
    text_lower = event.text.lower()
    matched_kws = [kw for kw in KEYWORDS if kw in text_lower]
    if not matched_kws:
        return

    # Check vacancy intent (filter out discussions/questions)
    from matching_service import is_vacancy_post, generate_draft_reply
    is_vac, vac_score, vac_triggers = is_vacancy_post(event.text)
    if not is_vac:
        log.info("[TRACE:%s] 💬 non_vacancy_chat | @%s | text: %s",
                 trace_id, username, event.text[:60].replace("\n", " "))
        return

    parser_stats.keywords_matched += 1
...
        for u in users:
            if any(sw.strip() and sw.strip().lower() in text_lower for sw in u.stop_words if sw):
                ...
                continue

            # Generate AI draft reply for this user
            draft = generate_draft_reply(u, event.text)

            card_create = JobCardCreateDTO(
                user_id=u.user_id,
                channel_title=title,
                channel_username=username,
                post_text=event.text,
                post_url=post_url,
                status=JobCardStatusEnum.NEW,
                match_score=vac_score,
                matched_keywords=matched_kws,
                draft_reply=draft,
            )
            card = await repo.create_job_card(card_create)
```

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH=backend pytest backend/tests`
Expected: PASS

---

### Task 3: Fix Bot Callback Handler & Rewrite/Regen Flow in `bot_service.py`

**Files:**
- Modify: `backend/bot_service.py:447-525`
- Test: `backend/tests/test_job_card_bot.py`

**Interfaces:**
- Consumes: `CallbackQuery("rewrite:<id>")`, `CallbackQuery("regen:<id>")`, `Message(text)`
- Produces: Correct prompt for edits, crash-free regeneration via `generate_draft_reply(profile, card.post_text, custom_instruction=user_instruction)` and updated Telegram card.

- [ ] **Step 1: Write test for bot text message handler for custom instruction rewrite**

```python
# backend/tests/test_bot_regen_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot_service import handle_user_text_message, USER_REGEN_WAITING

@pytest.mark.asyncio
async def test_handle_user_text_message_regen_success():
    USER_REGEN_WAITING[965000782] = 101
    
    mock_msg = MagicMock()
    mock_msg.from_user.id = 965000782
    mock_msg.text = "Сделай отклик короче"
    mock_msg.answer = AsyncMock()

    # Call handler
    await handle_user_text_message(mock_msg)
    
    assert mock_msg.answer.called
    assert 965000782 not in USER_REGEN_WAITING
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=backend pytest backend/tests/test_bot_regen_handler.py`
Expected: PASS

- [ ] **Step 3: Update `rewrite` and `regen` callback button labels & handlers in `bot_service.py`**

In `backend/bot_service.py`:
1. `rewrite:` handler: prompt user to enter edits (or send draft to copy) and register `USER_REGEN_WAITING[user_id] = card_id`.
2. Ensure both `rewrite` and `regen` set `USER_REGEN_WAITING[user_id] = card_id` so whenever user sends a text message after clicking edit, `handle_user_text_message` processes it safely without throwing `TypeError`.
3. Wrap `handle_user_text_message` in clean try/except block with friendly error notification on message.

- [ ] **Step 4: Run full test suite to verify everything passes**

Run: `PYTHONPATH=backend pytest backend/tests`
Expected: 100% PASS

---

## Plan Verification

### Automated Tests
```bash
PYTHONPATH=backend pytest backend/tests -v
```

### Manual Verification
1. Start local server `python app.py`.
2. Trigger test vacancy post to MTProto channel or test card endpoint.
3. Check Telegram message card:
   - Verified: Draft response section `✍️ Готовый отклик` is visible and readable.
   - Verified: Pressing `✍️ Переписать отклик` / `🔄 Перегенерировать` prompts for edits.
   - Verified: Typing a custom edit ("Сделай официальный тон") regenerates the response without errors.
   - Verified: Non-vacancy chat messages ("кто знает как смонтировать...") are filtered out and not sent as job cards.

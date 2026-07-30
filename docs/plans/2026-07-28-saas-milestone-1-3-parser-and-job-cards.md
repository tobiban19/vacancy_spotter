# Implementation Plan: Milestone 1.3 — Multi-Tenant Parser Integration & Job Alert Cards

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build multi-tenant vacancy filtering engine, draft reply generator, and Telegram Bot inline approval card sender with callback handlers.

**Architecture:** Incoming channel messages are ingested by `/api/jobs/incoming`, filtered against active user profiles, and dispatched as interactive Telegram messages via `aiogram 3`.

**Tech Stack:** Python 3.11, FastAPI, aiogram 3, Pydantic, aiosqlite/PostgreSQL.

## Global Constraints

- **Bot Token**: Read from `backend/.env`.
- **Security**: Closed-loop callback checks (verify user ID matches callback sender).

---

### Task 1: Job Cards Database & Matching Engine

**Files:**
- Modify: `vacancy-spotter-app/backend/models.py`
- Modify: `vacancy-spotter-app/backend/database.py`
- Create: `vacancy-spotter-app/backend/matching_service.py`
- Create: `vacancy-spotter-app/backend/tests/test_matching_service.py`

**Interfaces:**
- Consumes: User profile, resume, portfolio, and stop_words from DB.
- Produces: `MatchingEngine.match_job_for_users(raw_text: str, channel_username: str) -> list[JobCardDTO]`

- [ ] **Step 1: Write failing unit test for MatchingEngine**

```python
# vacancy-spotter-app/backend/tests/test_matching_service.py
import pytest
from matching_service import should_filter_by_stop_words

def test_stop_words_filtering():
    stop_words = ["бартер", "без оплаты", "adobe"]
    assert should_filter_by_stop_words("Ищем монтажера на бартер", stop_words) is True
    assert should_filter_by_stop_words("Ищем монтажера в Premiere Pro 100k", stop_words) is False
```

- [ ] **Step 2: Add Database methods for job cards in database.py**

Add `create_job_card`, `get_user_job_cards`, `update_job_card_status`.

- [ ] **Step 3: Implement MatchingEngine in matching_service.py**

Implement stop_words filtering and draft response builder.

- [ ] **Step 4: Run pytest tests**

Run command: `pytest vacancy-spotter-app/backend/tests/test_matching_service.py`
Expected output: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add vacancy-spotter-app/backend/
git commit -m "feat(backend): add JobCard database schema and MatchingEngine"
```

---

### Task 2: Telegram Bot Interactive Cards & Ingest API

**Files:**
- Modify: `vacancy-spotter-app/backend/bot_service.py`
- Modify: `vacancy-spotter-app/backend/api.py`
- Create: `vacancy-spotter-app/backend/tests/test_job_card_bot.py`

**Interfaces:**
- Consumes: Incoming vacancies via `POST /api/jobs/incoming`
- Produces: Telegram Bot inline cards with callbacks `approve:{card_id}`, `skip:{card_id}`.

- [ ] **Step 1: Write failing test for job card ingestion and callbacks**

```python
# vacancy-spotter-app/backend/tests/test_job_card_bot.py
import pytest
from bot_service import build_job_card_keyboard

def test_build_job_card_keyboard():
    kb = build_job_card_keyboard(card_id=42)
    assert len(kb.inline_keyboard) == 2
    assert "approve:42" in kb.inline_keyboard[0][0].callback_data
```

- [ ] **Step 2: Implement send_job_card and callback query handlers in bot_service.py**

Implement handlers for `approve:`, `skip:` with closed-loop authorization.

- [ ] **Step 3: Add POST /api/jobs/incoming in api.py**

Endpoint to ingest external Telegram channel messages, trigger matching engine, and send cards via bot.

- [ ] **Step 4: Run pytest test suite**

Run command: `pytest vacancy-spotter-app/backend/tests/test_job_card_bot.py`
Expected output: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add vacancy-spotter-app/backend/
git commit -m "feat(bot): implement interactive job card approval and ingest endpoint"
```

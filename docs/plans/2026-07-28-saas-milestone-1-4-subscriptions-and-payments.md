# Implementation Plan: Milestone 1.4 — Tariffs, Card Payments & Telegram Stars

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement subscription extension API, admin card payment approval workflow (card number: 2203 3101 8911 3452), Telegram Stars payment handlers, and frontend tariffs screen update.

**Architecture:** User selects plan (300 ₽ / 7 days or 600 ₽ / 30 days) in React TMA. Card transfer requests alert admin via Bot with approval callbacks. Telegram Stars checkout updates DB automatically.

**Tech Stack:** Python 3.11, aiogram 3, FastAPI, React 18, TailwindCSS.

## Global Constraints

- **Card Number**: `2203 3101 8911 3452`
- **Tariffs**: 300 ₽ / 7 days (150 Stars), 600 ₽ / 30 days (300 Stars)
- **Admin Chat ID**: Read from `ADMIN_CHAT_ID` (`965000782`)

---

### Task 1: Backend Subscription Extension API & Admin Manual Approvals

**Files:**
- Modify: `vacancy-spotter-app/backend/database.py`
- Modify: `vacancy-spotter-app/backend/api.py`
- Modify: `vacancy-spotter-app/backend/bot_service.py`
- Create: `vacancy-spotter-app/backend/tests/test_subscription_payments.py`

**Interfaces:**
- Consumes: User payment selection (Card / Stars)
- Produces: `extend_user_subscription(user_id: int, days: int)` and bot callback `admin_approve:{user_id}:{days}`.

- [ ] **Step 1: Write failing unit tests for subscription extension and API endpoints**

```python
# vacancy-spotter-app/backend/tests/test_subscription_payments.py
import pytest

@pytest.mark.asyncio
async def test_extend_subscription(repo):
    profile, _ = await repo.get_or_create_user({"id": 111, "first_name": "Test"})
    sub_before = await repo.get_subscription_status(111)
    
    await repo.extend_user_subscription(111, days=7)
    sub_after = await repo.get_subscription_status(111)
    assert sub_after.days_left >= 7
```

- [ ] **Step 2: Add extend_user_subscription in database.py**

```python
async def extend_user_subscription(self, user_id: int, days: int) -> SubscriptionStatusDTO:
    # Update subscription_until = max(now, existing_until) + timedelta(days=days)
    # Set subscription_status = 'active'
```

- [ ] **Step 3: Add subscription endpoints in api.py and admin callback handlers in bot_service.py**

Implement `POST /api/subscription/request_card` and bot handler `@router.callback_query(F.data.startswith("admin_approve:"))`.

- [ ] **Step 4: Run pytest tests**

Run command: `pytest vacancy-spotter-app/backend/tests/test_subscription_payments.py`
Expected output: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add vacancy-spotter-app/backend/
git commit -m "feat(subscription): add subscription extension database logic and admin approval callbacks"
```

---

### Task 2: Frontend Tariffs Tab Update & Vercel Production Deploy

**Files:**
- Modify: `vacancy-spotter-app/frontend/src/App.tsx`

**Interfaces:**
- Consumes: Backend `/api/subscription/request_card`
- Produces: Updated React tariffs screen with Card (2203 3101 8911 3452) and Telegram Stars options.

- [ ] **Step 1: Update App.tsx Subscription tab UI**

Display 2 plans:
- **Неделя (7 дней)** — 300 ₽ / ⭐️ 150 Stars
- **Месяц (30 дней)** — 600 ₽ / ⭐️ 300 Stars
Add copy card button `2203 3101 8911 3452` and "Я оплатил (уведомить админа)" action.

- [ ] **Step 2: Test build & Deploy to Vercel**

Run command: `npm --prefix vacancy-spotter-app/frontend run build && npx vercel --prod --yes`
Expected output: Success.

- [ ] **Step 3: Commit changes**

```bash
git add vacancy-spotter-app/frontend/
git commit -m "feat(frontend): update Subscription tab with card transfers and Telegram Stars options"
```

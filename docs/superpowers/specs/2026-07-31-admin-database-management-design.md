# Design Spec: Admin Database Management & Subscription Control for Vacancy Spotter

**Date:** 2026-07-31  
**Status:** Approved by User  
**Target Repository:** `vacancy-spotter-app` (`backend` & `frontend`)

---

## 1. Executive Summary

This spec outlines the design for introducing comprehensive database user tracking, channel subscription viewing, profile details monitoring, subscription management (granting/extending/revoking), and ban/unban capabilities directly inside the **Vacancy Spotter Telegram Mini App** and its **FastAPI Backend**.

Existing database schema (`SQLite` in `backend/database.py`) already contains `users`, `resumes`, `portfolios`, `channels`, and `user_channels` tables. This feature expands the backend repository, adds administrative REST endpoints guarded by Telegram authentication, and builds a dedicated Admin Panel tab in the Telegram Mini App frontend.

---

## 2. Database Schema Changes (`backend/database.py`)

### 2.1 Schema Extensions

Extend `users` table migration:
- `is_banned` `INTEGER DEFAULT 0` (0 = active, 1 = banned)
- `ban_reason` `TEXT DEFAULT NULL`

### 2.2 Repository Methods to Add

- `get_admin_stats()`:
  - Returns count of total users, active paid subscriptions, active demo users, expired users, and banned users.
- `get_admin_users_list(page: int = 1, limit: int = 20, search: str = "", status_filter: str = "all")`:
  - Returns paginated list of users with username, first_name, subscription status, demo_until, subscription_until, is_banned, and connected channel count.
- `get_admin_user_details(user_id: int)`:
  - Returns complete object:
    - User profile (ID, username, first_name, profession, experience, location, stop_words, subscription dates, ban status)
    - Resume/Bio (`bio_summary`, `software_stack`)
    - Portfolio items
    - Connected channels list (channel ID, username, title, enabled state)
- `update_user_subscription(user_id: int, status: str, subscription_until: datetime | None)`:
  - Updates subscription_status and subscription_until timestamp for a target user.
- `set_user_ban_status(user_id: int, is_banned: bool, ban_reason: str | None)`:
  - Toggles ban status and updates reason.
- `is_user_banned(user_id: int) -> bool`:
  - Rapid check for authentication and bot message filtering.

---

## 3. Backend API & Auth (`backend/api.py` & `backend/config.py`)

### 3.1 Admin Authentication Guard

- Configure `ADMIN_TELEGRAM_IDS` in `config.py` (comma-separated list of Telegram user IDs parsed from `.env`).
- Admin Auth Middleware/Dependency:
  - Validates Telegram `initData`.
  - Checks if `user_id` is in `ADMIN_TELEGRAM_IDS`.
  - Rejects unauthorized users with `403 Forbidden`.

### 3.2 REST API Endpoints

- `GET /api/admin/stats`
  - Returns SaaS usage statistics.
- `GET /api/admin/users?page=1&limit=20&search=&status=`
  - Returns paginated users list.
- `GET /api/admin/users/{user_id}`
  - Returns full user profile including bio, stack, and connected channels.
- `POST /api/admin/users/{user_id}/subscription`
  - Request body: `{ "action": "add_days" | "set_status" | "revoke", "days": int | None, "status": str | None }`
  - Updates subscription expiration.
- `POST /api/admin/users/{user_id}/ban`
  - Request body: `{ "is_banned": bool, "reason": str | None }`
  - Updates ban state.

---

## 4. Frontend Telegram Mini App Integration (`frontend`)

### 4.1 Navigation & Permissions

- On app initialization, check if user is admin.
- Display an **"Админка" (Admin)** tab icon in navigation bar if authorized.

### 4.2 Admin Panel View Components

1. **Stats Header Cards**:
   - Total Users | Active Paid | Active Demo | Banned
2. **User Table & Controls**:
   - Search input (filter by Username / ID / Name).
   - Status filters (`All`, `Demo`, `Active`, `Expired`, `Banned`).
   - User table displaying: User ID, Name, Username, Profession, Sub Status, Expiration, Channels count, Action button ("Детали / Управление").
3. **User Details Drawer / Modal**:
   - **Profile Tab**: Name, Username, ID, Profession, Experience, Location, Stop Words.
   - **Resume Tab**: Bio summary, Software stack badges.
   - **Channels Tab**: Connected Telegram channels list with status.
   - **Subscription Management**: Quick buttons (`+7 дней`, `+30 дней`, `+365 дней`, `Сбросить в Demo`, `Аннулировать`).
   - **Ban Controls**: Toggle Ban switch + input reason + Save button.

---

## 5. Error Handling & Security

- **Banned User Access**: Banned users receive `403 Banned` on all user API calls and a message in Telegram Bot indicating account suspension.
- **Audit Logging**: Admin actions (subscription modifications, bans) logged to database console/logs.
- **Input Validation**: All dates and numeric inputs validated via Pydantic DTOs.

---

## 6. Verification Plan

1. **Unit/Integration Tests**:
   - Test `database.py` admin methods (`get_admin_users_list`, `update_user_subscription`, `set_user_ban_status`).
   - Test admin API endpoints in `api.py` with both admin and non-admin tokens.
2. **End-to-End Verification**:
   - Verify Admin tab visibility in Mini App frontend.
   - Test searching users, viewing user details, extending subscription, and banning a test user.

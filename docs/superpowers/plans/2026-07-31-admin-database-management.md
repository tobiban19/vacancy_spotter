# Admin Database Management & Subscription Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide full administrative visibility and management of users, subscriptions, connected Telegram channels, and user banning in Vacancy Spotter via FastAPI and Telegram Mini App.

**Architecture:** Extend SQLite schema with ban fields; implement admin repository methods and FastAPI REST endpoints guarded by Telegram `ADMIN_TELEGRAM_IDS` validation; add an Admin Panel view tab in the Telegram Mini App frontend.

**Tech Stack:** Python 3.11+, FastAPI, SQLite (aiosqlite), Pydantic v2, React / TypeScript / Tailwind CSS.

## Global Constraints

- Database engine: SQLite with WAL mode via `aiosqlite`.
- Auth mechanism: Telegram `initData` HMAC-SHA256 verification.
- Admin protection: Configurable `ADMIN_TELEGRAM_IDS` in `.env`.
- Response format: JSON adhering to Pydantic DTO schemas.

---

### Task 1: Extend Data Models and Backend Configuration

**Files:**
- Modify: `c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/models.py`
- Modify: `c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/config.py`

**Interfaces:**
- Produces: `AdminUserDTO`, `AdminUserDetailDTO`, `AdminStatsDTO`, `AdminSubscriptionUpdateDTO`, `AdminBanUpdateDTO` in `models.py`.
- Produces: `settings.admin_telegram_ids` list in `config.py`.

- [ ] **Step 1: Write Pydantic DTOs for Admin in `models.py`**

```python
class AdminUserDTO(BaseModel):
    user_id: int
    username: str | None = None
    first_name: str
    profession_id: str
    subscription_status: str
    demo_until: datetime
    subscription_until: datetime | None = None
    is_banned: bool = False
    ban_reason: str | None = None
    channels_count: int = 0
    created_at: datetime


class AdminStatsDTO(BaseModel):
    total_users: int
    active_paid_users: int
    demo_users: int
    expired_users: int
    banned_users: int


class AdminUserDetailDTO(BaseModel):
    profile: UserProfileDTO
    is_banned: bool
    ban_reason: str | None
    bio_summary: str
    software_stack: list[str]
    stop_words: list[str]
    connected_channels: list[dict[str, Any]]
    created_at: datetime


class AdminSubscriptionUpdateDTO(BaseModel):
    action: Literal["add_days", "set_status", "revoke"]
    days: int | None = None
    status: Literal["demo", "active", "expired"] | None = None


class AdminBanUpdateDTO(BaseModel):
    is_banned: bool
    ban_reason: str | None = None
```

- [ ] **Step 2: Add `admin_telegram_ids` to `config.py`**

```python
class Settings(BaseSettings):
    ...
    admin_telegram_ids_raw: str = Field(default="", alias="ADMIN_TELEGRAM_IDS")

    @property
    def admin_telegram_ids(self) -> list[int]:
        if not self.admin_telegram_ids_raw:
            return []
        return [int(x.strip()) for x in self.admin_telegram_ids_raw.split(",") if x.strip().isdigit()]
```

---

### Task 2: Extend SQLite Schema & Admin Repository Methods in `database.py`

**Files:**
- Modify: `c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/database.py`

**Interfaces:**
- Consumes: `AdminUserDTO`, `AdminStatsDTO`, `AdminUserDetailDTO` from `models.py`.
- Produces: `get_admin_stats()`, `get_admin_users_list()`, `get_admin_user_details()`, `update_user_subscription()`, `set_user_ban_status()`, `is_user_banned()`.

- [ ] **Step 1: Add Migration for `is_banned` and `ban_reason` in `_init_tables`**

```python
# Add columns to users table if they do not exist
columns = await self._conn.execute("PRAGMA table_info(users);")
cols = {row["name"] for row in await columns.fetchall()}
if "is_banned" not in cols:
    await self._conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0;")
if "ban_reason" not in cols:
    await self._conn.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT DEFAULT NULL;")
```

- [ ] **Step 2: Implement Admin Query Methods in `DatabaseRepository`**

Implement `get_admin_stats`, `get_admin_users_list`, `get_admin_user_details`, `update_user_subscription`, `set_user_ban_status`, `is_user_banned`.

---

### Task 3: Implement Backend Admin Endpoints & Security Guard in `api.py`

**Files:**
- Modify: `c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/api.py`

**Interfaces:**
- Consumes: `DatabaseRepository` admin methods and `settings.admin_telegram_ids`.
- Produces: REST Endpoints under `/api/admin/*`.

- [ ] **Step 1: Add Admin Auth Dependency `verify_admin`**

```python
async def verify_admin(user: dict[str, Any] = Depends(get_current_telegram_user)) -> dict[str, Any]:
    user_id = user.get("id")
    if user_id not in settings.admin_telegram_ids:
        raise HTTPException(status_code=403, detail="Access denied: Admin privileges required")
    return user
```

- [ ] **Step 2: Register Admin Endpoints in FastAPI `app`**

Implement:
- `GET /api/admin/stats`
- `GET /api/admin/users`
- `GET /api/admin/users/{user_id}`
- `POST /api/admin/users/{user_id}/subscription`
- `POST /api/admin/users/{user_id}/ban`

---

### Task 4: Build Admin Panel UI in Frontend Mini App

**Files:**
- Modify/Create components in `vacancy-spotter-app/frontend/src/`

- [ ] **Step 1: Add Admin API client calls and TypeScript types**
- [ ] **Step 2: Create Admin Panel view with Stats cards, search/filter User table, and User details drawer/modal**
- [ ] **Step 3: Connect subscription extend/revoke and Ban/Unban actions to API**

---

### Task 5: End-to-End Verification & Testing

- [ ] **Step 1: Run pytest backend tests to verify database migrations and API endpoints**
- [ ] **Step 2: Verify ban guard blocks banned user API calls**

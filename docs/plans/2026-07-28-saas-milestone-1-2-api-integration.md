# Implementation Plan: Milestone 1.2 — Frontend TMA Integration with Backend REST API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full CRUD endpoints in FastAPI backend for User Profile, Portfolio, and Channels, and connect React Telegram Mini App to persist data in SQLite/PostgreSQL database.

**Architecture:** React SPA frontend calls FastAPI REST API using `Authorization: Bearer <initData>`. FastAPI verifies signature and performs DB operations using `DatabaseRepository`.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, aiosqlite, React 18, Vite, TypeScript.

## Global Constraints

- **Security**: All API endpoints must extract user identity from validated `initData` or bearer token.
- **Port**: FastAPI running on `http://localhost:8000`.

---

### Task 1: Backend CRUD API for Profile, Portfolio & Channels

**Files:**
- Modify: `vacancy-spotter-app/backend/database.py`
- Modify: `vacancy-spotter-app/backend/api.py`
- Create: `vacancy-spotter-app/backend/tests/test_milestone1_2_api.py`

**Interfaces:**
- Consumes: Verified user ID from `auth.py`
- Produces: `/api/profile`, `/api/portfolio`, `/api/channels` REST endpoints.

- [ ] **Step 1: Write failing unit tests for Profile, Portfolio, and Channels API**

```python
# vacancy-spotter-app/backend/tests/test_milestone1_2_api.py
import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
```

- [ ] **Step 2: Implement DatabaseRepository methods in database.py**

Add methods: `update_user_profile`, `add_portfolio_item`, `delete_portfolio_item`, `get_user_portfolio`, `toggle_user_channel`.

- [ ] **Step 3: Add API routes in api.py**

Implement `GET /api/profile`, `PUT /api/profile`, `GET /api/portfolio`, `POST /api/portfolio`, `DELETE /api/portfolio/{item_id}`, `GET /api/channels`, `POST /api/channels/toggle`.

- [ ] **Step 4: Run tests to verify pass**

Run command: `pytest vacancy-spotter-app/backend/tests/test_milestone1_2_api.py`
Expected output: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add vacancy-spotter-app/backend/
git commit -m "feat(backend): add CRUD REST API for profile, portfolio, and channels"
```

---

### Task 2: Frontend REST API Client & React State Sync

**Files:**
- Create: `vacancy-spotter-app/frontend/src/api.ts`
- Modify: `vacancy-spotter-app/frontend/src/App.tsx`

**Interfaces:**
- Consumes: Backend REST API endpoints
- Produces: Interactive React UI with real-time API sync and Vercel deployment.

- [ ] **Step 1: Create api.ts module**

```typescript
// vacancy-spotter-app/frontend/src/api.ts
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function getInitData(): string {
  return (window as any).Telegram?.WebApp?.initData || '';
}

export async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getInitData()}`,
    ...(options.headers || {})
  };
  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}
```

- [ ] **Step 2: Update App.tsx to bind forms and state to api.ts**

Connect tabs in `App.tsx` so changing profession/stop-words saves to API, adding portfolio item posts to API, and toggling channels syncs with API.

- [ ] **Step 3: Test build & Re-deploy to Vercel**

Run command: `npm --prefix vacancy-spotter-app/frontend run build && npx vercel --prod`
Expected output: Production deployment updated on Vercel.

- [ ] **Step 4: Commit changes**

```bash
git add vacancy-spotter-app/frontend/
git commit -m "feat(frontend): connect TMA React UI with FastAPI REST API endpoints"
```

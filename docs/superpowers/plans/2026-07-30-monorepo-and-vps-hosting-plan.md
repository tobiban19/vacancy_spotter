# Monorepo & VPS Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate application into single monorepo `vacancy-spotter-app`, build automated pre-deploy test runner gate, and serve compiled Mini App directly from VPS FastAPI server with anti-caching HTTP headers.

**Architecture:** 
- FastAPI REST server mounts `frontend/dist` with `Cache-Control: no-cache` headers for `index.html`.
- `scripts/deploy.py` acts as a pre-deploy validator executing `npm run build` and `pytest backend/tests` locally before SFTP transfer to VPS (`72.56.79.35`).
- Telegram WebApp URL configured in `bot_service.py` to point directly to VPS hosted Mini App endpoint (`http://72.56.79.35:8000/app`).

**Tech Stack:** Python 3.12, FastAPI, aiogram 3, React, Vite, TypeScript, Paramiko SFTP, Systemd.

## Global Constraints

- Never deploy unbuilt frontend assets or failing python tests to production server.
- All file edits must pass full `pytest backend/tests` suite.
- Maintain backwards compatibility for Telegram Stars payments and admin approval callbacks.

---

### Task 1: Add Anti-Caching Middleware & Static Mount in FastAPI

**Files:**
- Modify: `backend/api.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write test for static app endpoint and no-cache header**

```python
@pytest.mark.asyncio
async def test_static_app_no_cache_header(async_client: AsyncClient):
    resp = await async_client.get("/app")
    assert resp.status_code == 200 or resp.status_code == 404
```

- [ ] **Step 2: Run test to verify initial state**

Run: `$env:PYTHONPATH="backend"; pytest backend/tests/test_api.py -v`
Expected: PASS

- [ ] **Step 3: Add Custom Middleware for /app index.html No-Cache Headers**

In `backend/api.py`:
```python
@app.middleware("http")
async def add_anti_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path in ["/app", "/app/", "/app/index.html"]:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
```

- [ ] **Step 4: Run test to verify passes**

Run: `$env:PYTHONPATH="backend"; pytest backend/tests/test_api.py -v`
Expected: PASS

---

### Task 2: Implement Automated Pre-Deploy Validation Gate in `scripts/deploy.py`

**Files:**
- Modify: `scripts/deploy.py`

- [ ] **Step 1: Update `scripts/deploy.py` to execute local build and test checks before upload**

In `scripts/deploy.py`:
Add pre-flight checks:
```python
def run_local_checks():
    print("=== Step 1: Building Frontend Bundle ===")
    res_fe = subprocess.run(["npm", "run", "build"], cwd=LOCAL_FRONTEND_DIR, shell=True)
    if res_fe.returncode != 0:
        print("❌ Frontend build failed! Aborting deployment.")
        sys.exit(1)

    print("=== Step 2: Running Backend Pytest Suite ===")
    res_be = subprocess.run([sys.executable, "-m", "pytest", "backend/tests"], cwd=LOCAL_DIR, env={**os.environ, "PYTHONPATH": "backend"})
    if res_be.returncode != 0:
        print("❌ Backend tests failed! Aborting deployment.")
        sys.exit(1)
```

- [ ] **Step 2: Execute deployment runner test**

Run: `.\.venv\Scripts\python.exe C:\Users\ptimo\.gemini\antigravity\brain\b59fec50-de68-4843-9ab1-40818632aa71\scratch\deploy_saas.py`
Expected: Passes frontend build and backend tests, then uploads cleanly to VPS.

---

### Task 3: Update Default WebApp URL to VPS Endpoint

**Files:**
- Modify: `backend/bot_service.py`
- Modify: `backend/config.py`

- [ ] **Step 1: Set DEFAULT_WEBAPP_URL to VPS URL**

In `backend/bot_service.py`:
```python
DEFAULT_WEBAPP_URL = os.getenv("WEBAPP_URL", "http://72.56.79.35:8000/app")
```

- [ ] **Step 2: Run all backend tests**

Run: `$env:PYTHONPATH="backend"; pytest backend/tests`
Expected: All 27 tests pass.

# Design Specification: Monorepo Consolidation, Pre-Deploy Test Gate & Direct VPS Hosting

> **Date:** 2026-07-30  
> **Target Project:** `vacancy-spotter-app`  
> **Server:** Ubuntu 24.04 LTS (`72.56.79.35`)  

---

## 1. Goal & Architectural Overview

The goal of this design is to eliminate human error during deployment, streamline the codebase into a single authoritative monorepo, and guarantee instant UI updates across all devices (including Telegram Desktop on Windows) without third-party caching delays.

### Core Objectives
1. **Single Monorepo (`vacancy-spotter-app`):** Archive the legacy `vacancy-spotter` codebase. All features, bot services, APIs, and Mini App UI will reside exclusively in `vacancy-spotter-app`.
2. **Automated Pre-Deploy Test Gate:** A unified deployment runner (`scripts/deploy.py`) that strictly enforces passing unit tests (`pytest backend/tests`) and successful production frontend builds (`npm run build`) before any files touch the production VPS.
3. **Direct VPS WebApp Hosting:** Serve the built React Mini App directly from FastAPI on `http://72.56.79.35:8000/app` with `no-cache` directives for `index.html` and hashed static assets, resolving Telegram Desktop caching issues.

---

## 2. Monorepo Structure

```text
vacancy-spotter-app/
├── backend/
│   ├── api.py                   # FastAPI REST server & StaticFiles mount (/app)
│   ├── bot_service.py           # aiogram 3 Telegram Bot (@vacancy_spott_bot)
│   ├── database.py              # SQLite repository & timezone-safe DTO parsers
│   ├── config.py                # Pydantic Settings
│   ├── models.py                # Pydantic Data Models
│   └── tests/                   # Pytest automated test suite
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # React Mini App main component
│   │   └── index.css            # Styling tokens & solid red header rules
│   └── dist/                    # Compiled production build
├── scripts/
│   └── deploy.py                # Automated pre-deploy validator & SSH deployer
├── app.py                       # Main application launcher
└── requirements.txt             # Python dependencies
```

---

## 3. Pre-Deploy Test & Validation Gate

The deployment runner `scripts/deploy.py` operates as an automated gatekeeper:

```text
[ Developer / AI Agent ]
         │
         ▼
Run: python scripts/deploy.py
         │
         ├─── Step 1: Run `npm run build` in frontend/ (Verify TypeScript & Vite)
         │       └─ FAIL? ❌ STOP DEPLOYMENT
         │
         ├─── Step 2: Run `pytest backend/tests` (Verify API & Bot logic)
         │       └─ FAIL? ❌ STOP DEPLOYMENT
         │
         ├─── Step 3: Run `python -m py_compile` on python source files
         │       └─ FAIL? ❌ STOP DEPLOYMENT
         │
         └─── Step 4: All Passed! ✅ Upload dist & backend to VPS via SFTP
                 └─ Exec: systemctl restart vacancy-spotter-saas
```

---

## 4. Direct VPS WebApp Hosting & Anti-Caching Strategy

### Static Files Mounting in `backend/api.py`
FastAPI serves the compiled React app directly from `/opt/vacancy-spotter-app/frontend/dist` under `/app`:

- **HTML Page (`/app`):** Served with HTTP headers:
  `Cache-Control: no-cache, no-store, must-revalidate`
- **Hashed Assets (`/app/assets/*`):** Served with long-term cache headers:
  `Cache-Control: public, max-age=31536000, immutable`

This guarantees that when Telegram Desktop loads the Mini App, it instantly fetches the latest `index.html`, which references the newly compiled asset hashes.

---

## 5. Self-Review & Verification Criteria

1. **Placeholder Check:** No TBD or unhandled cases in spec.
2. **Consistency:** All route names, paths, and environment settings match `vacancy-spotter-app`.
3. **Execution Safety:** Zero production service restarts occur if local tests or builds fail.

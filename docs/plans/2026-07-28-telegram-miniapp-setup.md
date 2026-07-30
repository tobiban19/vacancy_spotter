# Telegram Mini App Infrastructure Setup & Deployment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up Telegram Mini App frontend (React Vite + SDK), FastAPI backend authentication endpoints with Telegram `initData` HMAC verification, CORS rules for Vercel deployment, and Render service configuration.

**Architecture:** A multi-tenant architecture where Telegram Mini App (React) runs inside Telegram client, authenticates via `initData` HMAC SHA256 against FastAPI backend, and communicates with PostgreSQL/SQLite.

**Tech Stack:** React 18, Vite, `@telegram-apps/sdk-react`, TailwindCSS, Python 3.11, FastAPI, Pydantic, pytest.

## Global Constraints

- **Bot Token**: Read from `backend/.env` (`8773545660:AAGP...`)
- **Backend Port**: `http://localhost:8000` (FastAPI)
- **Frontend Port**: `http://localhost:5173` (Vite)
- **Security**: Never bypass `initData` HMAC signature verification on backend endpoints.

---

### Task 1: Backend HMAC initData Verification & Auth API

**Files:**
- Create: `vacancy-spotter-app/backend/auth.py`
- Modify: `vacancy-spotter-app/backend/api.py`
- Test: `vacancy-spotter-app/backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `BOT_TOKEN` from `vacancy-spotter-app/backend/config.py`
- Produces: `verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None` and `/api/auth/verify` endpoint.

- [ ] **Step 1: Write the failing test**

```python
# vacancy-spotter-app/backend/tests/test_auth.py
import hmac
import hashlib
from urllib.parse import urlencode
import pytest

from auth import verify_telegram_init_data

def test_verify_telegram_init_data_valid():
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    init_data_dict = {
        "user": '{"id":965000782,"first_name":"Pavel"}',
        "auth_date": "1700000000"
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(init_data_dict.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    raw_init_data = urlencode(init_data_dict) + f"&hash={calculated_hash}"
    
    result = verify_telegram_init_data(raw_init_data, bot_token)
    assert result is not None
    assert result["user"] == '{"id":965000782,"first_name":"Pavel"}'

def test_verify_telegram_init_data_invalid():
    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    raw_init_data = "user=fake&hash=invalidhash"
    result = verify_telegram_init_data(raw_init_data, bot_token)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run command: `pytest vacancy-spotter-app/backend/tests/test_auth.py`
Expected output: ModuleNotFoundError / ImportError `auth` not found.

- [ ] **Step 3: Write minimal implementation in auth.py**

```python
# vacancy-spotter-app/backend/auth.py
import hashlib
import hmac
from urllib.parse import parse_qsl

def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    if not init_data or not bot_token:
        return None
        
    parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_to_check = parsed_data.pop("hash", None)
    if not hash_to_check:
        return None
    
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if hmac.compare_digest(calculated_hash, hash_to_check):
        return parsed_data
    return None
```

Modify `vacancy-spotter-app/backend/api.py` to add `/api/auth/verify`:

```python
# vacancy-spotter-app/backend/api.py
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from auth import verify_telegram_init_data
from config import settings

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])

class AuthVerifyResponse(BaseModel):
    success: bool
    user_id: int
    first_name: str

@auth_router.post("/verify", response_model=AuthVerifyResponse)
async def verify_auth(authorization: str = Header(...)):
    # Expected format: "Bearer <raw_init_data>"
    init_data = authorization.replace("Bearer ", "").strip()
    verified_data = verify_telegram_init_data(init_data, settings.BOT_TOKEN)
    if not verified_data:
        raise HTTPException(status_code=401, detail="Invalid Telegram initData signature")
        
    import json
    user_info = json.loads(verified_data.get("user", "{}"))
    return AuthVerifyResponse(
        success=True,
        user_id=user_info.get("id", 0),
        first_name=user_info.get("first_name", "User")
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run command: `pytest vacancy-spotter-app/backend/tests/test_auth.py`
Expected output: PASS (2 passed).

- [ ] **Step 5: Commit changes**

```bash
git add vacancy-spotter-app/backend/auth.py vacancy-spotter-app/backend/api.py vacancy-spotter-app/backend/tests/test_auth.py
git commit -m "feat(backend): add Telegram initData HMAC verification endpoint"
```

---

### Task 2: Frontend Setup (Vite + React + Telegram WebApp SDK + Theme Matching)

**Files:**
- Create: `vacancy-spotter-app/frontend/package.json`
- Create: `vacancy-spotter-app/frontend/vite.config.ts`
- Create: `vacancy-spotter-app/frontend/index.html`
- Create: `vacancy-spotter-app/frontend/src/index.css`
- Create: `vacancy-spotter-app/frontend/src/main.tsx`
- Create: `vacancy-spotter-app/frontend/src/App.tsx`
- Create: `vacancy-spotter-app/frontend/vercel.json`

**Interfaces:**
- Consumes: Telegram Client `window.Telegram.WebApp` & Backend `/api/auth/verify`
- Produces: React SPA with 4 tabs (Profile, Portfolio, Channels, Subscription)

- [ ] **Step 1: Create package.json and vite.config.ts**

`vacancy-spotter-app/frontend/package.json`:
```json
{
  "name": "vacancy-spotter-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@telegram-apps/sdk-react": "^2.0.0",
    "lucide-react": "^0.300.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.2.2",
    "vite": "^5.0.8"
  }
}
```

- [ ] **Step 2: Setup index.html with Telegram WebApp Script**

`vacancy-spotter-app/frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
    <title>Vacancy Spotter Cabinet</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
  </head>
  <body class="bg-[var(--tg-theme-bg-color,#0f172a)] text-[var(--tg-theme-text-color,#f8fafc)] min-h-screen">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Create Tailwind and App.tsx with 4 Tabs UI**

`vacancy-spotter-app/frontend/src/App.tsx`:
```tsx
import React, { useEffect, useState } from 'react';
import { User, Briefcase, Radio, CreditCard } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'profile' | 'portfolio' | 'channels' | 'subscription'>('profile');
  const [tgUser, setTgUser] = useState<any>(null);

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      setTgUser(tg.initDataUnsafe?.user || { first_name: 'Демо Фрилансер' });
    }
  }, []);

  return (
    <div className="flex flex-col min-h-screen max-w-md mx-auto pb-20 px-4 pt-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <h1 className="text-xl font-bold text-blue-400">Vacancy Spotter</h1>
          <p className="text-xs text-slate-400">Привет, {tgUser?.first_name} 👋</p>
        </div>
        <span className="bg-emerald-500/10 text-emerald-400 text-xs px-2.5 py-1 rounded-full border border-emerald-500/20 font-medium">
          Демо: 24ч
        </span>
      </div>

      {/* Main Content Area */}
      <div className="flex-1">
        {activeTab === 'profile' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold flex items-center gap-2"><User size={20}/> Мой Профиль</h2>
            <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-3">
              <label className="block text-xs text-slate-400">Профессия</label>
              <select className="w-full bg-slate-800 text-white p-2.5 rounded-lg border border-slate-700">
                <option value="video_editor">🎬 Видеомонтажёр / Reelsmaker</option>
                <option value="motion_designer">🎨 Motion Designer</option>
                <option value="copywriter">✍️ Копирайтер</option>
                <option value="3d_artist">🧊 3D Artist</option>
              </select>
            </div>
          </div>
        )}

        {activeTab === 'portfolio' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold flex items-center gap-2"><Briefcase size={20}/> Мое Портфолио</h2>
            <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 text-center">
              <p className="text-sm text-slate-400 mb-3">У вас пока нет загруженных работ</p>
              <button className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg transition-colors text-sm">
                + Добавить работу
              </button>
            </div>
          </div>
        )}

        {activeTab === 'channels' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold flex items-center gap-2"><Radio size={20}/> Вакансии & Чаты</h2>
            <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
              <p className="text-xs text-slate-400 mb-2">Рекомендованные каналы:</p>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between py-1.5 border-b border-slate-800">
                  <span>📢 @editors_video</span>
                  <input type="checkbox" defaultChecked className="toggle" />
                </div>
                <div className="flex items-center justify-between py-1.5">
                  <span>📢 @vakansii_reelsmaker</span>
                  <input type="checkbox" defaultChecked className="toggle" />
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'subscription' && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold flex items-center gap-2"><CreditCard size={20}/> Подписка</h2>
            <div className="bg-gradient-to-br from-blue-900/40 to-slate-900 p-5 rounded-xl border border-blue-500/30 text-center">
              <h3 className="font-bold text-lg text-white mb-1">PRO Доступ</h3>
              <p className="text-xs text-slate-300 mb-4">Безлимитный ИИ-отклик во все каналы</p>
              <button className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold py-3 rounded-xl transition-all shadow-lg shadow-amber-500/20 text-sm">
                Оформить за ⭐️ 250 Stars
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-slate-950/90 backdrop-blur-md border-t border-slate-800 py-2 px-4">
        <div className="flex justify-around max-w-md mx-auto">
          <button onClick={() => setActiveTab('profile')} className={`flex flex-col items-center gap-1 text-xs ${activeTab === 'profile' ? 'text-blue-400' : 'text-slate-400'}`}>
            <User size={20} /> Профиль
          </button>
          <button onClick={() => setActiveTab('portfolio')} className={`flex flex-col items-center gap-1 text-xs ${activeTab === 'portfolio' ? 'text-blue-400' : 'text-slate-400'}`}>
            <Briefcase size={20} /> Портфолио
          </button>
          <button onClick={() => setActiveTab('channels')} className={`flex flex-col items-center gap-1 text-xs ${activeTab === 'channels' ? 'text-blue-400' : 'text-slate-400'}`}>
            <Radio size={20} /> Чаты
          </button>
          <button onClick={() => setActiveTab('subscription')} className={`flex flex-col items-center gap-1 text-xs ${activeTab === 'subscription' ? 'text-blue-400' : 'text-slate-400'}`}>
            <CreditCard size={20} /> Тарифы
          </button>
        </div>
      </div>
    </div>
  );
}
export default App;
```

- [ ] **Step 4: Add vercel.json rewrite configuration**

`vacancy-spotter-app/frontend/vercel.json`:
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

- [ ] **Step 5: Verify build**

Run command: `npm --prefix vacancy-spotter-app/frontend run build` (or verify TypeScript compilation).
Expected output: Build success.

- [ ] **Step 6: Commit changes**

```bash
git add vacancy-spotter-app/frontend/
git commit -m "feat(frontend): setup Vite React Telegram Mini App with 4 tabs"
```

---

### Task 3: Production CORS & Render Configuration

**Files:**
- Modify: `vacancy-spotter-app/backend/server.py`
- Create: `vacancy-spotter-app/backend/render.yaml`

**Interfaces:**
- Consumes: Frontend HTTP requests from Vercel domain.
- Produces: Production FastAPI app with CORS middleware and Render build manifest.

- [ ] **Step 1: Add CORS Middleware to server.py**

```python
# Add CORS middleware to FastAPI in server.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (including Vercel TMA domain)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Create Render deployment configuration render.yaml**

`vacancy-spotter-app/backend/render.yaml`:
```yaml
services:
  - type: web
    name: vacancy-spotter-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn server:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: BOT_TOKEN
        sync: false
      - key: JWT_SECRET
        generateValue: true
```

- [ ] **Step 3: Test backend health endpoint**

Run command: `pytest vacancy-spotter-app/backend/tests/`
Expected output: PASS.

- [ ] **Step 4: Commit changes**

```bash
git add vacancy-spotter-app/backend/server.py vacancy-spotter-app/backend/render.yaml
git commit -m "chore(backend): add CORS middleware and Render deployment manifest"
```

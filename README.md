---
title: Vacancy Spotter SaaS Backend & Telegram Mini App
emoji: 🚀
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.21.0
app_file: app.py
pinned: false
short_description: Vacancy Spotter SaaS Backend & Telegram Bot 24/7
---

# 🚀 Vacancy Spotter — SaaS Техническая Документация

**Vacancy Spotter** — автономный SaaS-сервис и Telegram-бот (`@vacancy_spott_bot`) с интегрированным Telegram Mini App кабинетом для автоматического отслеживания вакансий, фильтрации интентов найма, генерации персонализированных откликов с помощью ИИ и взаимодействия с клиентами.

---

## 📐 Архитектура Системы

```
┌─────────────────────────────────────────────────────────────┐
│                 Telegram Client / User                      │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
     Telegram WebApp                        Bot Inline
     (React 18 + Vite)                     Commands & Menu
               │                              │
               ▼                              ▼
┌─────────────────────────────┐  ┌────────────────────────────┐
│   Vercel / Mini App Host    │  │  aiogram 3 Telegram Bot    │
└──────────────┬──────────────┘  └────────────┬───────────────┘
               │                              │
               │ (REST API / JWT Auth)        │ (Card Actions / Payments)
               ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (app.py)                 │
├─────────────────────────────────────────────────────────────┤
│  • Auth Engine (Telegram initData HMAC SHA256)              │
│  • Vacancy Intent Classifier & Matching Engine              │
│  • Userbot Parser (Telethon MTProto listener)               │
│  • Database Repository (SQLite / WAL mode via aiosqlite)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  SQLite Data Store (data/)                  │
│   (Users, Portfolios, Channels, Job Cards, Trace Logs, etc.)│
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Технологический Стек

- **Backend**: Python 3.11, FastAPI, Pydantic v2, `aiogram` 3.x, `Telethon` (MTProto), `aiosqlite`, `PyJWT`.
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Lucide Icons, Telegram WebApp SDK.
- **База Данных**: SQLite (WAL-режим, асинхронные пулы `aiosqlite`).
- **Деплой**:
  - Frontend: **Vercel** (`https://frontend-psi-nine-2ydjpsdrfq.vercel.app`).
  - Backend / Bot: **VPS Linux (systemd)** / Hugging Face Spaces / Render.

---

## 🚀 Быстрый Запуск Проекта

### 1. Установка backend
```bash
# Клонирование и переход в директорию backend
cd backend

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Переменные окружения (`backend/.env`)
```env
BOT_TOKEN=<получить у @BotFather>
TELEGRAM_API_ID=<получить на https://my.telegram.org>
TELEGRAM_API_HASH=<получить на https://my.telegram.org>
JWT_SECRET=<случайная строка >= 32 байт>
DATABASE_URL=sqlite+aiosqlite:///../data/saas_spotter.sqlite3
ADMIN_CHAT_ID=<ваш Telegram ID>
ADMIN_TELEGRAM_IDS=<список ID админов через запятую>
DEMO_DURATION_DAYS=2
# ИИ-генерация откликов (без этого ключа используется локальный шаблон):
OPENROUTER_API_KEY=<ключ с https://openrouter.ai>
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
# Опционально (production):
CORS_ORIGINS=https://ваш-miniapp.vercel.app,https://ваш-домен
JOBS_WEBHOOK_SECRET=<случайная строка для защиты /api/jobs/incoming>
```

### 3. Запуск локального бэкенда и бота
```bash
python app.py
# или напрямую через uvicorn:
python backend/server.py
```

### 4. Запуск фронтенда (Telegram Mini App)
```bash
cd frontend
npm install
npm run dev
```

---

## 📚 Документация Модулей Проекта

Подробная полная техническая спецификация всех API endpoints, структуры БД и сервисов доступна в файле [`docs/TECHNICAL_DOCS.md`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/docs/TECHNICAL_DOCS.md).

### Ключевые компоненты:
1. [`app.py`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/app.py): Главный единый точка входа для запуска FastAPI, Telegram-бота, MTProto парсера и интерфейса Gradio.
2. [`backend/api.py`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/api.py): REST API для Mini App (авторизация через `initData` HMAC, профиль, портфолио, каналы, карточки вакансий, панель администратора).
3. [`backend/bot_service.py`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/bot_service.py): Логика Telegram-бота (команды `/start`, `/status`, `/help`, `/debug`, генерация откликов, подписки, перегенерация через `USER_REGEN_WAITING`).
4. [`backend/matching_service.py`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/matching_service.py): Классификатор интента коммерческих вакансий (`is_vacancy_post`) и генератор ИИ-откликов через OpenRouter (`async generate_draft_reply`), учитывающий текст вакансии, профиль и пользовательские пожелания. При отсутствии `OPENROUTER_API_KEY` используется локальный шаблонный fallback.
5. [`backend/telethon_parser.py`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/telethon_parser.py): MTProto парсер каналов Telegram в реальном времени с фильтрацией интентов и автосозданием откликов.
6. [`backend/database.py`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/backend/database.py): Репозиторий базы данных SQLite на `aiosqlite`.
7. [`frontend/src/App.tsx`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/frontend/src/App.tsx): Главное клиентское приложение Telegram Mini App.
8. [`scripts/deploy.py`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/scripts/deploy.py): Автоматический скрипт деплоя с pre-flight валидацией (npm build + pytest + git push + vercel deploy + VPS systemd deployment). Параметры подключения к VPS берутся из переменных окружения (`VPS_HOST`, `VPS_USER`, `VPS_PASSWORD`).

---

## 🧪 Тестирование и Валидация

Для запуска пакета юнит-тестов (47 тестов):
```bash
$env:PYTHONPATH='backend'; python -m pytest backend/tests
```

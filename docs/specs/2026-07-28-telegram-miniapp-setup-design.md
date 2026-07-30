# Spec: Telegram Mini App Infrastructure Setup & Deployment (Milestone 1.1)

> **Дата**: 2026-07-28  
> **Статус**: Одобрено пользователем (Approved)  
> **Цель**: Настройка Telegram Bot (@BotFather), деплой React Mini App на Vercel, деплой FastAPI бэкенда на Render и обеспечение связи по HTTPS.

---

## 1. Архитектура и Компоненты

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TELEGRAM CLIENT                                  │
└──────────────────────┬───────────────────────────────┬──────────────────────┘
                       │                               │
                       ▼                               ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│   Telegram Bot (aiogram 3)   │              │   Telegram Mini App (React)  │
│   • Token: 8773545...        │              │   • Hosted on Vercel         │
│   • Menu Button: 💼 Кабинет  │              │   • Telegram WebApp SDK      │
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               │                                             │
               │         ┌───────────────────────────┐       │
               └────────►│   FastAPI Backend (REST)  │◄──────┘
                         │   • Hosted on Render          │
                         │   • HMAC initData Auth        │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │    PostgreSQL / SQLite    │
                         └───────────────────────────┘
```

---

## 2. Конфигурация Компонентов

### 2.1 Telegram Bot & BotFather
- **Bot Token**: Сохранён в `vacancy-spotter-app/backend/.env` (`8773545660:AAGP...`).
- **Menu Button**: Кнопка меню чата настраивается командой `/setmenubutton` на собранный Vercel HTTPS URL.
- **Bot Commands**:
  - `/start` - Запустить бота и получить приветствие.
  - `/app` - Открыть веб-кабинет Telegram Mini App.
  - `/help` - Инструкции и поддержка.

### 2.2 Frontend (React + Vite + Telegram WebApp SDK)
- **Путь**: `vacancy-spotter-app/frontend/`
- **Стек**: React 18, Vite, `@telegram-apps/sdk-react`, TailwindCSS.
- **Деплой**: Vercel CLI / GitHub Integration.
- **Вкладки**:
  1. Профиль & Профессия
  2. Портфолио
  3. Каналы вакансий
  4. Подписка

### 2.3 Backend (FastAPI + HMAC Validation)
- **Путь**: `vacancy-spotter-app/backend/`
- **Стек**: Python 3.11, FastAPI, Pydantic, SQLAlchemy/aiosqlite.
- **Деплой**: Render Web Service.
- **Ключевой метод авторизации**: `verify_telegram_init_data(init_data_string, bot_token)`.

---

## 3. Этапы деплоя и настройки

1. **Frontend Scaffolding**: Сборка React 18 приложения в `vacancy-spotter-app/frontend` со всеми 4 экранами и Telegram WebApp SDK.
2. **Backend API Readiness**: Подготовка FastAPI веб-сервера `vacancy-spotter-app/backend/server.py` со свободным CORS для Vercel домена.
3. **Vercel Deploy**: Публикация фронтенда и получение публичного HTTPS URL (`https://vacancy-spotter-app.vercel.app` или аналогичного).
4. **BotFather Linking**: Привязка Vercel HTTPS URL к кнопке меню `@BotFather` (`/setmenubutton`).

---

## 4. Критерии Успеха (Verification)
- Открытие бота в Telegram -> нажатие кнопки `💼 Кабинет` сразу загружает Mini App из Vercel.
- Mini App корректно считывает тему Telegram (светлая/тёмная).
- Запрос `initData` успешно валидируется на бэкенде FastAPI без ошибок 401 Unauthorized.

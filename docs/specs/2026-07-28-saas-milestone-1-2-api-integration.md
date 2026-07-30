# Spec: Frontend TMA Integration with Backend REST API (Milestone 1.2)

> **Дата**: 2026-07-28  
> **Статус**: Одобрено пользователем (Approved)  
> **Цель**: Полная интеграция Telegram Mini App фронтенда с REST API бэкенда для синхронизации Профиля, Портфолио, Каналов и Подписки.

---

## 1. REST API Эндпоинты бэкенда (`backend/api.py`)

Все эндпоинты требуют заголовок `Authorization: Bearer <initData>` и валидируют пользователя через `verify_telegram_init_data`.

### 1.1 Профиль пользователя
- `GET /api/profile` -> Возвращает `{ user_id, first_name, username, profession_id, experience_years, location, stop_words, subscription_status, demo_until }`.
- `PUT /api/profile` -> Принимает `{ profession_id, experience_years, location, stop_words }`, обновляет запись в SQLite/PostgreSQL.

### 1.2 Портфолио фрилансера
- `GET /api/portfolio` -> Возвращает список кейсов пользователя `[ { id, title, url, category, orientation, description, tags, created_at } ]`.
- `POST /api/portfolio` -> Добавляет новый кейс `{ title, url, category, orientation, description, tags }`.
- `DELETE /api/portfolio/{item_id}` -> Удаляет кейс по ID.

### 1.3 Каналы вакансий
- `GET /api/channels` -> Возвращает доступные каналы по профессии пользователя с флагом `is_enabled`.
- `POST /api/channels/toggle` -> Принимает `{ channel_id, is_enabled }`, обновляет подписку пользователя на канал.
- `POST /api/channels/custom` -> Принимает `{ username }`, проверяет публичный канал и добавляет его в чаты пользователя.

---

## 2. Frontend Слой API & Интеграция (`frontend/src/`)

- `src/api.ts` — модуль для выполнения `fetch` запросов к бэкенду с автоматической подстановкой `window.Telegram.WebApp.initData`.
- `src/App.tsx` — интеграция состояний React c бэкендом:
  - Автоматическая загрузка данных профиля при запуске приложения.
  - Мгновенное сохранение изменений при смене профессии, добавлении стоп-слов или кейса в портфолио.
  - Отображение реального остатка времени демо-доступа / подписки.

---

## 3. Критерии Проверки (Verification)
1. Изменение профессии или стоп-слов в Mini App сохраняется в БД и отображается при повторном открытии.
2. Добавление ссылки на портфолио в Mini App сохраняет работу в SQLite и возвращает её в GET `/api/portfolio`.
3. Переключение галочек каналов вакансий обновляет таблицу `user_channels`.

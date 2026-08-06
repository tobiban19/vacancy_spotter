# 📘 Vacancy Spotter SaaS — Полное Техническое Руководство

В данном документе описана полная техническая спецификация архитектуры, структуры базы данных, API endpoints, парсера вакансий, фильтрации интентов, ИИ-генерации откликов, Telegram-бота и систем взаимодействия компонентов **Vacancy Spotter SaaS**.

---

## 1. Схема Базы Данных (SQLite / `backend/database.py`)

Репозиторий `DatabaseRepository` управляет SQLite базой данных (`data/saas_spotter.sqlite3`) в формате WAL (Write-Ahead Logging), `PRAGMA foreign_keys=ON`. Соединение — единое асинхронное (`aiosqlite`).

### 1.1 Таблицы:

1. **`users`** — Пользователи сервиса:
   - `id` (BIGINT PRIMARY KEY) — Telegram User ID.
   - `username` (TEXT) — Username Telegram (@username).
   - `first_name` (TEXT NOT NULL) — Имя пользователя.
   - `profession_id` (TEXT DEFAULT 'video_editor') — Выбранная профессия (FK → `professions.id`).
   - `experience_years` (INTEGER DEFAULT 1) — Опыт работы в годах.
   - `location` (TEXT DEFAULT 'Удалённо') — Локация / формат работы.
   - `stop_words` (TEXT DEFAULT '[]') — JSON-массив стоп-слов для фильтрации вакансий.
   - `subscription_status` (TEXT DEFAULT 'demo') — Статус: `'demo'`, `'active'`, `'expired'`.
   - `demo_until` (TEXT NOT NULL) — Дата окончания пробного периода (ISO 8601, UTC).
   - `subscription_until` (TEXT) — Дата окончания платной подписки (ISO 8601, UTC).
   - `is_banned` (INTEGER DEFAULT 0) — Флаг блокировки пользователя (1/0) — добавляется миграцией.
   - `ban_reason` (TEXT DEFAULT NULL) — Причина блокировки — добавляется миграцией.
   - `created_at` (TEXT NOT NULL) — Дата регистрации.

2. **`resumes`** — Резюме/профиль навыков пользователя (вынесено отдельно от `users`):
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `user_id` (BIGINT UNIQUE NOT NULL, FK → `users.id` ON DELETE CASCADE).
   - `bio_summary` (TEXT DEFAULT '') — Описание опыта и «о себе» для генерации отклика.
   - `software_stack` (TEXT DEFAULT '[]') — JSON-массив используемого ПО и стека.

3. **`portfolios`** — Элементы портфолио пользователя:
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `user_id` (BIGINT NOT NULL, FK → `users.id` ON DELETE CASCADE).
   - `title` (TEXT NOT NULL) — Название кейса/работы.
   - `url` (TEXT NOT NULL) — Ссылка на проект.
   - `category` (TEXT DEFAULT 'general').
   - `orientation` (TEXT DEFAULT 'horizontal') — `'horizontal'` | `'vertical'`.
   - `description` (TEXT NOT NULL).
   - `tags` (TEXT DEFAULT '[]') — JSON-массив тегов.
   - `created_at` (TEXT NOT NULL).

4. **`professions`** — Справочник профессий (6 записей: `video_editor`, `motion_designer`, `web_designer`, `copywriter`, `3d_artist`, `smm`):
   - `id` (TEXT PRIMARY KEY) — Идентификатор.
   - `title_ru` (TEXT NOT NULL) — Русское название.
   - `icon_emoji` (TEXT NOT NULL) — Эмодзи иконка.

5. **`channels`** — Telegram-каналы с вакансиями (публичный каталог):
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `profession_id` (TEXT NOT NULL) — Привязка к профессии.
   - `chat_id` (BIGINT) — Внутренний ID чата (опционально, используется Telethon).
   - `username` (TEXT NOT NULL) — Username канала без `@`. Уникальный индекс `(profession_id, username)`.
   - `title` (TEXT NOT NULL) — Название канала.
   - `is_recommended` (BOOLEAN DEFAULT 1) — Рекомендованный (`1`) или пользовательский (`0`).
   - `is_active` (BOOLEAN DEFAULT 1) — Включён ли канал в парсинг.

6. **`user_channels`** — Персональные подписки пользователей на каналы:
   - `user_id` (BIGINT, FK → `users.id` ON DELETE CASCADE).
   - `channel_id` (INTEGER, FK → `channels.id` ON DELETE CASCADE).
   - `is_enabled` (BOOLEAN DEFAULT 1) — Включён ли канал у конкретного пользователя.
   - PRIMARY KEY `(user_id, channel_id)`.

7. **`user_job_cards`** — Найденные карточки вакансий:
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `user_id` (BIGINT NOT NULL, FK → `users.id` ON DELETE CASCADE). Индекс `idx_user_job_cards_user_id`.
   - `channel_title` (TEXT DEFAULT ''), `channel_username` (TEXT DEFAULT '').
   - `post_text` (TEXT NOT NULL) — Исходный текст вакансии из канала.
   - `post_url` (TEXT DEFAULT '') — Прямая ссылка на пост Telegram (`https://t.me/{username}/{id}`).
   - `post_date` (TEXT) — Дата поста.
   - `status` (TEXT DEFAULT 'new') — Статус карточки: `'new'`, `'saved'`, `'applied'`, `'rejected'`, `'hidden'`.
   - `match_score` (REAL DEFAULT 0.0) — Оценка релевантности (0.0 — 1.0).
   - `matched_keywords` (TEXT DEFAULT '[]') — JSON-массив совпавших ключевых слов.
   - `draft_reply` (TEXT DEFAULT '') — Сгенерированный проект отклика (ИИ / шаблон).
   - `created_at` (TEXT NOT NULL).

8. **`pipeline_trace`** — Журнал трейсинга обработки парсера (хранит последние 500 записей, автопрунинг):
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `trace_id` (TEXT NOT NULL) — Уникальный 8-символьный hex-ID цепочки обработки. Индексы по `trace_id` и `post_url`.
   - `event` (TEXT NOT NULL) — Тип события (`received`, `non_vacancy_chat`, `users_matched`, `no_subscribers`, `stop_word_filtered`, `card_created`, `card_sent`, `card_send_failed`, `card_send_error`, `pipeline_error`).
   - `channel`, `post_url`, `post_snippet` (до 100 символов), `user_id`, `card_id`, `bot_username`, `bot_token_prefix` (первые 10 символов), `detail`, `created_at`.

> **Примечание:** отдельной таблицы `subscription_requests` нет — обработка заявок на оплату идёт через inline-кнопки в чате администратора (`admin_approve:` / `admin_reject:` callback'и в `bot_service.py`), а продление подписки вызывает метод `repo.extend_user_subscription()`.

---

## 2. Спецификация REST API (`backend/api.py`)

Все приватные маршруты защищены авторизацией `Bearer JWT_TOKEN` (проверка через зависимости `get_current_user_id` / `get_admin_user_id`). Токен выдаётся эндпоинтом `POST /api/auth/tma` после успешной валидации `initData` Telegram WebApp по алгоритму HMAC-SHA256. JWT содержит `sub`, `iat` и `exp` (срок жизни — `JWT_EXPIRE_HOURS`, по умолчанию 7 дней).

### 2.1 Авторизация (`/api/auth`)
- **`POST /api/auth/verify`**: Проверяет подпись HMAC `initData` и возвращает `{ valid, data }`. **Не создаёт пользователя и не выдаёт JWT** — это диагностический эндпоинт.
- **`POST /api/auth/tma`**: Основной логин Mini App. Проверяет `initData`, создаёт/обновляет пользователя в БД (новым юзерам назначается демо-период `DEMO_DURATION_DAYS`), возвращает `TokenResponse` с `access_token` (JWT).

### 2.2 Профиль и Настройки (`/api/profile`)
- **`GET /api/profile`**: Возвращает профиль текущего пользователя (`UserProfileDTO`).
- **`PUT /api/profile`**: Обновляет данные профиля (профессию, стаж, стоп-слова, стек, о себе).
- **`POST /api/profile/parse_pdf`**: Парсит загруженный PDF-файл резюме (`UploadFile`) через `pypdf`, извлекает текст (до 2000 символов) и возвращает его для автозаполнения профиля.

### 2.3 Портфолио (`/api/portfolio`)
- **`GET /api/portfolio`**: Получение всех кейсов пользователя.
- **`POST /api/portfolio`**: Добавление нового элемента портфолио.
- **`PUT /api/portfolio/{item_id}`**: Обновление элемента портфолио.
- **`DELETE /api/portfolio/{item_id}`**: Удаление элемента портфолио.

### 2.4 Каналы Вакансий (`/api/channels`)
- **`GET /api/channels`**: Получение списка отслеживаемых каналов для текущей профессии.
- **`POST /api/channels/toggle`**: Включение/выключение канала для пользователя.
- **`POST /api/channels/custom`**: Добавление своего кастомного Telegram-канала по username или ссылке.

### 2.5 Карточки Вакансий (`/api/cards`)
- **`GET /api/cards?status_filter=new`**: Список карточек вакансий пользователя с опциональной фильтрацией по статусу (`new`, `saved`, `applied`, `rejected`, `hidden`).
- **`PUT /api/cards/{card_id}/status`**: Обновление статуса карточки. Тело: `{ "status": "new|saved|applied|rejected|hidden" }`.
- **`POST /api/cards/{card_id}/regenerate`**: Перегенерация черновика отклика с учётом текущего профиля. Тело: `{ "custom_instruction": "..." }`.

### 2.6 Подписка и Оплаты (`/api/subscription`)
- **`GET /api/subscription`**: Информация о текущей подписке и оставшихся днях.
- **`POST /api/subscription/request_card`**: Отправка заявки администратору на активацию подписки после оплаты по реквизитам карты. Тело: `{ "plan": "week|month", "receipt_info": "...", "receipt_file_b64": "...", "receipt_filename": "..." }`. Заявка приходит админу в Telegram с кнопками одобрения/отклонения.

### 2.7 Профессии (`/api/professions`)
- **`GET /api/professions`**: Список доступных профессий. Является единым источником правды для фронтенда.

### 2.8 Вебхук парсера (`/api/jobs/incoming`)
- **`POST /api/jobs/incoming`**: Внутренний эндпоинт инъекции постов из Telegram-каналов. **Защищён**: при заданном `JOBS_WEBHOOK_SECRET` требует заголовок `X-Webhook-Secret`. Создаёт карточки и отправляет их подписчикам. В штатном режиме не используется — основной поток идёт через Telethon MTProto-парсер.

### 2.9 Админ-Панель (`/api/admin/*`)
Защищена проверкой Telegram ID пользователя по списку `ADMIN_TELEGRAM_IDS` (через `get_admin_user_id`).
- **`GET /api/admin/check`**: Проверка, является ли текущий пользователь администратором.
- **`GET /api/admin/stats`**: Статистика (всего пользователей, активных/демо/истёкших/заблокированных).
- **`GET /api/admin/users?page&limit&search&status`**: Список пользователей с пагинацией и фильтром.
- **`GET /api/admin/users/{user_id}`**: Детальная информация о пользователе.
- **`POST /api/admin/users/{user_id}/subscription`**: Управление подпиской (`add_days`, `set_status`, `revoke`).
- **`POST /api/admin/users/{user_id}/ban`**: Блокировка/разблокировка пользователя.

> **Примечание:** заявки на оплату обрабатываются inline-кнопками прямо в чате администратора (`admin_approve:` / `admin_reject:` callback'и в `bot_service.py`). Отдельной таблицы `subscription_requests` и REST-эндпоинтов для этого нет.

---

## 3. Модуль Парсинга, Интента и Генерирования Откликов

1. **MTProto Слушатель (`telethon_parser.py`)**:
   - Работает через клиент Telethon для связи с Telegram MTProto API.
   - В реальном времени получает посты из отслеживаемых каналов.
   - **Двухуровневый фильтр**:
     1. `KEYWORDS` — расширенный набор терминов по всем профессиям (видео, motion/3D, веб-дизайн, копирайтинг, SMM). Пост без совпадений по ключевым словам отбрасывается сразу.
     2. **Фильтр интента вакансии**: `is_vacancy_post(event.text)`. Если сообщение является чатовым вопросом или флудом, пост отклоняется (`non_vacancy_chat`).
   - Для подписчиков канала запускает генерацию ИИ-отклика `await generate_draft_reply(u, event.text)`.
   - Записывает карточку `JobCardCreateDTO(..., draft_reply=draft)` в SQLite БД и отправляет уведомление в Telegram-бот.

2. **Движок Фильтрации и ИИ-Откликов (`matching_service.py`)**:
   - `is_vacancy_post(text: str) -> tuple[bool, float, list[str]]`:
     Анализирует текст на коммерческие триггеры найма (`ищу`, `требуется`, `оплата`, `бюджет`, `тз`, `в команду`, `отклик`, контакты) и штрафует обычный чатовый флуд (`кто знает`, `подскажите`, `как сделать`, `где скачать`).
   - `should_filter_by_stop_words(text, stop_words)`: Проверяет текст на пользовательские стоп-слова.
   - `async generate_draft_reply(user_profile, job_text, custom_instruction="")`:
     - При заданном `OPENROUTER_API_KEY` генерирует отклик через LLM (по умолчанию `google/gemini-2.5-flash-lite`), **учитывая текст вакансии** (`job_text`), профиль (имя, опыт, стек, о себе) и пожелание (`custom_instruction`). До 120 слов, на русском, от первого лица.
     - При отсутствии ключа или любой ошибке сети/API — graceful fallback на локальный шаблон (имя + опыт в правильном склонении + стек + `custom_instruction`), ошибка логируется как warning.
     - Модель и провайдер настраиваются через `OPENROUTER_MODEL` / `OPENROUTER_BASE_URL`.

---

## 4. Telegram Bot Service (`backend/bot_service.py`)

- **Библиотека**: `aiogram` 3.x.
- **Интерактивное меню** (`/start`):
  - Кнопка `📱 Открыть личный кабинет` открывает WebApp (`DEFAULT_WEBAPP_URL`, по умолчанию `https://frontend-psi-nine-2ydjpsdrfq.vercel.app`).
  - Инлайн кнопки `💳 Подписка и тарифы`, `❓ Как это работает`, `💬 Поддержка`.
- **Карточка вакансии** (`send_job_card_to_user`) с инлайн-кнопками: `✅ Отправить отклик` (`approve:`), `✍️ Переписать отклик` (`rewrite:`), `🔄 Перегенерировать` (`regen:`), `🔗 Перейти к вакансии` (если есть `post_url`).
- **Машина состояний перегенерации (`USER_REGEN_WAITING: dict[int,int]`)**:
  - При нажатии `rewrite:` / `regen:` бот регистрирует ожидание ввода и запрашивает пожелания к тексту (например, *«Сделай тон более официальным»*).
  - При отправке любого текстового сообщения `handle_user_text_message` вызывает `await generate_draft_reply(..., custom_instruction=...)`, обновляет `draft_reply` карточки в БД и присылает новый отклик с клавиатурой действий.
- **Команды**:
  - `/start` — приветствие, выдача демо-периода новым пользователям, WebApp-клавиатура.
  - `/stats` (или `статистика`/`стат`) — статус подписки и доступа текущего пользователя.
  - `/debug` (только админ) — живая диагностика: имя бота, префикс токена, статистика Telethon-парсера (`parser_stats`), последние trace-события.
  - `/trace <url|card_id|trace_id|last>` (только админ) — поиск цепочки обработки поста по URL / ID карточки / trace_id / последние события.
- **Колбэки подписок** (`menu_subscription`, `menu_help`) — статус подписки и тарифы, справка «как это работает».
- **Оплаты**: Оплата переводом на карту РФ с ручным подтверждением администратором через inline-кнопки `admin_approve:{user_id}:{days}` / `admin_reject:{user_id}`. При одобрении подписка продляется через `repo.extend_user_subscription()`, пользователю уходит поздравительное сообщение. Telegram Stars отключён (мёртвый код удалён).

---

## 5. Покрытие Юнит-Тестами и Деплой

1. **Тестовая сюита** (50 тестов):
   - Запуск: `$env:PYTHONPATH='backend'; python -m pytest backend/tests`
   - Покрытие: авторизация (включая регрессионный тест закрытия `dev_mode_*` бэкдора и наличие `exp` в JWT), профиль, портфолио (с multi-tenant изоляцией), каналы, карточки вакансий `/api/cards` (список, смена статуса, перегенерация, 404, требование auth), подписки, админка, классификатор интентов, генерация откликов (AI-путь с моком LLM, fallback при ошибке, шаблонный режим без ключа) и интеграция парсера.

2. **Скрипт Деплоя (`scripts/deploy.py`)**:
   - Параметры подключения к VPS берутся из переменных окружения (`VPS_HOST`, `VPS_USER`, `VPS_PASSWORD`); при отсутствии пароля используется SSH-ключ.
   - Gate 1: сборка фронтенда React TypeScript (`npm run build`).
   - Gate 2: прогон всех pytest-тестов.
   - Gate 3: индексация изменений (`git add -u` + `frontend/dist`) и пуш в `origin main` (без blanket `git add .`).
   - Gate 4: публикация фронтенда в Vercel Production и деплой бэкенда на VPS (systemd `vacancy-spotter-saas.service`, entrypoint `app.py`).
   - Альтернативный bootstrap-скрипт: `deploy.sh` (PM2 на чистом VPS, клонирует `vacancy-spotter-app`, ставит `venv`, запускает `app.py`).

3. **Конфигурации окружения**:
   - Все секреты — через переменные окружения / `backend/.env` (см. `config.py:Settings`). Никакие токены не захардкожены в коде.
   - Render-конфиги: `render.yaml` (корневой, monorepo) и `backend/render.yaml` с полным набором envVars.
   - CORS настраивается через `CORS_ORIGINS` (whitelist; пусто = permissive режим для локальной разработки).

---

## 6. Переменные окружения (`backend/.env` / `config.py`)

| Переменная | Назначение | Обязательно |
|---|---|---|
| `BOT_TOKEN` | Токен Telegram-бота (@BotFather). Используется и ботом, и проверкой HMAC initData. | ✅ |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | Учётные данные MTProto для userbot-парсера (my.telegram.org). | ✅ для парсера |
| `JWT_SECRET` | Секрет для подписи JWT. Рекомендуется ≥ 32 байт. | ✅ |
| `JWT_EXPIRE_HOURS` | Срок жизни JWT в часах (по умолчанию 168 = 7 дней). | нет |
| `DATABASE_URL` | DSN вида `sqlite+aiosqlite:///../data/saas_spotter.sqlite3`. | нет |
| `DEMO_DURATION_DAYS` | Длина демо-периода для новых пользователей (по умолчанию 2). | нет |
| `ADMIN_CHAT_ID` / `ADMIN_TELEGRAM_IDS` | Telegram ID администраторов (через запятую). | ✅ |
| `OPENROUTER_API_KEY` | Ключ OpenRouter для ИИ-генерации откликов. Без него — локальный шаблон. | нет (но нужен для ИИ) |
| `OPENROUTER_MODEL` | ID модели (по умолчанию `google/gemini-2.5-flash-lite`). | нет |
| `OPENROUTER_BASE_URL` / `OPENROUTER_TIMEOUT_SECONDS` | URL API и таймаут (по умолчанию 20с). | нет |
| `CORS_ORIGINS` | Whitelist источников через запятую (домены Mini App). | ✅ в проде |
| `JOBS_WEBHOOK_SECRET` | Секрет для защиты `POST /api/jobs/incoming` (заголовок `X-Webhook-Secret`). | нет |
| `HOST` / `PORT` | Bind-адрес FastAPI (по умолчанию `0.0.0.0:8000`). | нет |

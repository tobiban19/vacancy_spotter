# 📘 Vacancy Spotter SaaS — Полное Техническое Руководство

В данном документе описана полная техническая спецификация архитектуры, структуры базы данных, API endpoints, парсера вакансий, фильтрации интентов, ИИ-генерации откликов, Telegram-бота и систем взаимодействия компонентов **Vacancy Spotter SaaS**.

---

## 1. Схема Базы Данных (SQLite / `backend/database.py`)

Репозиторий `DatabaseRepository` управляет SQLite базой данных (`data/saas_spotter.sqlite3`) в формате WAL (Write-Ahead Logging).

### 1.1 Таблицы:

1. **`users`** — Пользователи сервиса:
   - `user_id` (INTEGER PRIMARY KEY) — Telegram User ID.
   - `username` (TEXT) — Username Telegram (@username).
   - `first_name` (TEXT) — Имя пользователя.
   - `profession_id` (TEXT DEFAULT 'video_editor') — Выбранная профессия.
   - `experience_years` (INTEGER DEFAULT 1) — Опыт работы в годах.
   - `location` (TEXT DEFAULT 'Удалённо') — Локация / формат работы.
   - `stop_words_json` (TEXT) — JSON-массив стоп-слов для фильтрации вакансий.
   - `subscription_status` (TEXT DEFAULT 'demo') — Статус: `'demo'`, `'active'`, `'expired'`.
   - `demo_until` (TEXT) — Дата окончания пробного периода (ISO format).
   - `subscription_until` (TEXT) — Дата окончания платной подписки.
   - `bio_summary` (TEXT) — Описание опыта и о себе для генерации отклика.
   - `software_stack_json` (TEXT) — JSON-массив используемого ПО и стека.
   - `is_banned` (INTEGER DEFAULT 0) — Флаг блокировки пользователя (1/0).
   - `created_at` (TEXT) — Дата регистрации.

2. **`portfolio_items`** — Элементы портфолио пользователя:
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `user_id` (INTEGER, FK -> users).
   - `title` (TEXT) — Название кейса/работы.
   - `url` (TEXT) — Ссылка на проект.
   - `category` (TEXT DEFAULT 'general').
   - `description` (TEXT).
   - `created_at` (TEXT).

3. **`professions`** — Справочник профессий:
   - `id` (TEXT PRIMARY KEY) — Идентификатор (например, `video_editor`, `motion_designer`).
   - `title_ru` (TEXT) — Русское название.
   - `icon_emoji` (TEXT) — Эмодзи иконка.

4. **`channels`** — Telegram-каналы с вакансиями:
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `profession_id` (TEXT, FK -> professions).
   - `username` (TEXT UNIQUE) — Username канала без `@`.
   - `title` (TEXT) — Название канала.
   - `is_active` (INTEGER DEFAULT 1).

5. **`user_channels`** — Привязка пользовательских каналов (для кастомного списка):
   - `user_id` (INTEGER), `channel_username` (TEXT), `is_enabled` (INTEGER DEFAULT 1).

6. **`job_cards`** — Найденные карточки вакансий:
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `user_id` (INTEGER, FK -> users).
   - `channel_title` (TEXT), `channel_username` (TEXT).
   - `post_text` (TEXT) — Исходный текст вакансии из канала.
   - `post_url` (TEXT) — Прямая ссылка на пост Telegram (`https://t.me/c/...`).
   - `post_date` (TEXT).
   - `status` (TEXT DEFAULT 'new') — Статус карточки: `'new'`, `'saved'`, `'applied'`, `'rejected'`, `'hidden'`.
   - `match_score` (REAL) — Оценка релевантности (0.0 — 1.0).
   - `matched_keywords_json` (TEXT) — Массив совпавших ключевых слов.
   - `draft_reply` (TEXT) — Автоматически сгенерированный проект сопроводительного письма (ИИ).
   - `created_at` (TEXT).

7. **`pipeline_trace`** — Журнал трейсинга обработки парсера (хранит последние 500 записей, автопрунинг):
   - `id`, `trace_id` (TEXT) — Уникальный 8-символьный ID цепочки обработки.
   - `event` (TEXT) — Тип события (`received`, `non_vacancy_chat`, `users_matched`, `no_subscribers`, `stop_word_filtered`, `card_created`, `card_sent`, `card_send_failed`, `card_send_error`, `pipeline_error`).
   - `channel`, `post_url`, `post_snippet`, `user_id`, `card_id`, `bot_username`, `bot_token_prefix`, `detail`, `created_at`.

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
- **Интерактивное меню**:
  - Кнопка `📱 Открыть личный кабинет` открывает WebApp (`https://frontend-psi-nine-2ydjpsdrfq.vercel.app`).
  - Инлайн кнопки под карточкой вакансии (`✅ Отправить отклик`, `✍️ Переписать отклик`, `🔄 Перегенерировать`, `🔗 Перейти к вакансии`).
- **Машина состояний перегенерации (`USER_REGEN_WAITING`)**:
  - При нажатии `rewrite` или `regen` бот выводит текущий отклик в тегах `<code>...</code>` и запрашивает у пользователя пожелания к тексту (например, *«Сделай тон более официальным»*).
  - При отправке текста `handle_user_text_message` перегенерирует отклик с вызовом `generate_draft_reply(..., custom_instruction=...)` и обновляет карточку в базе данных.
- **Команды**:
  - `/start` — Приветственное сообщение и открытие WebApp.
  - `/status` — Проверка статуса подписки и аккаунта.
  - `/help` — Руководство по работе.
  - `/debug` (для администраторов) — Живая статистика работы MTProto парсера.
- **Оплаты**: Оплата переводом на карту РФ с ручным подтверждением администратором через inline-кнопки (`admin_approve:` / `admin_reject:`). При одобрении подписка продляется через `repo.extend_user_subscription()`. Telegram Stars отключён (мёртвый код удалён).

---

## 5. Покрытие Юнит-Тестами и Деплой

1. **Тестовая сюита**:
   - Запуск: `$env:PYTHONPATH='backend'; python -m pytest backend/tests`
   - Юнит-тесты покрывают: авторизацию (включая регрессионный тест закрытия `dev_mode_*` бэкдора и наличие `exp` в JWT), профиль, портфолио, каналы, карточки вакансий (`/api/cards`), подписки, админку, классификатор интентов и перегенерацию откликов.

2. **Скрипт Деплоя (`scripts/deploy.py`)**:
   - Gate 1: Компиляция фронтенда React TypeScript (`npm run build`).
   - Gate 2: Запуск всех 41 Pytest тестов.
   - Gate 3: Синхронизация репозитория Git main (`git push origin main`).
   - Gate 4: Публикация фронтенда Vercel Production и обновление `vacancy-spotter-saas.service` на VPS.

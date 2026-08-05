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

7. **`trace_logs`** — Журнал трейсинга обработки парсера:
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `trace_id` (TEXT) — Уникальный хэш цепочки обработки.
   - `event` (TEXT), `payload_json` (TEXT), `timestamp` (TEXT).

8. **`subscription_requests`** — Заявки на оплату подписки переводом по карте (СБП):
   - `id` (INTEGER PRIMARY KEY AUTOINCREMENT).
   - `user_id` (INTEGER), `plan` (TEXT), `amount` (INTEGER), `status` (TEXT DEFAULT 'pending'), `created_at` (TEXT).

---

## 2. Спецификация REST API (`backend/api.py`)

Все приватные маршруты защищены авторизацией `Bearer JWT_TOKEN`.  
Токен выдаётся методом POST `/api/auth/verify` после успешной валидации `initData` Telegram WebApp по алгоритму HMAC-SHA256.

### 2.1 Авторизация (`/api/auth`)
- **`POST /api/auth/verify`**
  - **Тело запроса**: `InitDataAuthRequest` (`init_data`: str).
  - **Описание**: Проверяет подпись HMAC `window.Telegram.WebApp.initData`, создает или обновляет запись пользователя в БД (назначая 2 дня демо-периода новым юзерам) и возвращает JWT токен.

### 2.2 Профиль и Настройки (`/api/profile`)
- **`GET /api/profile`**: Возвращает профиль текущего пользователя (`UserProfileDTO`).
- **`PUT /api/profile`**: Обновляет данные профиля (профессию, стаж, стоп-слова, стек, о себе).
- **`POST /api/profile/upload-resume`**: Парсит загруженный PDF-файл резюме (`UploadFile`) через `pypdf`, извлекает опыт и навыки и автозаполняет профиль.
- **`GET /api/professions`**: Возвращает доступный список профессий.

### 2.3 Портфолио (`/api/portfolio`)
- **`GET /api/portfolio`**: Получение всех кейсов пользователя.
- **`POST /api/portfolio`**: Добавление нового элемента портфолио.
- **`DELETE /api/portfolio/{item_id}`**: Удаление элемента портфолио.

### 2.4 Каналы Вакансий (`/api/channels`)
- **`GET /api/channels`**: Получение списка отслеживаемых каналов для текущей профессии.
- **`POST /api/channels/custom`**: Добавление своего кастомного Telegram-канала по username.
- **`DELETE /api/channels/custom/{username}`**: Удаление кастомного канала.

### 2.5 Карточки Вакансий (`/api/cards`)
- **`GET /api/cards?status=new`**: Список карточек вакансий пользователя с фильтрацией по статусу.
- **`PUT /api/cards/{card_id}/status`**: Обновление статуса карточки (`new`, `saved`, `applied`, `rejected`).
- **`POST /api/cards/{card_id}/regenerate`**: Перегенерация черновика отклика с учетом текущего профиля.

### 2.6 Подписка и Оплаты (`/api/subscription`)
- **`GET /api/subscription/status`**: Информация о текущей подписке и оставшихся днях.
- **`POST /api/subscription/card-request`**: Отправка заявки на активацию подписки после оплаты по реквизитам СБП.

### 2.7 Админ-Панель (`/api/admin/*`)
Защищена проверкой Telegram ID пользователя по списку `ADMIN_TELEGRAM_IDS`.
- **`GET /api/admin/stats`**: Статистика (всего пользователей, активных подписок, обработанных карточек).
- **`GET /api/admin/users`**: Список всех пользователей с пагинацией и поиском.
- **`GET /api/admin/users/{user_id}`**: Детальная информация о пользователе.
- **`PUT /api/admin/users/{user_id}/subscription`**: Продление/изменение подписки пользователя вручную.
- **`PUT /api/admin/users/{user_id}/ban`**: Блокировка/разблокировка пользователя.
- **`GET /api/admin/subscription-requests`**: Список pending заявок на оплату.
- **`POST /api/admin/subscription-requests/{req_id}/approve`**: Одобрение оплаты и продление подписки.

---

## 3. Модуль Парсинга, Интента и Генерирования Откликов

1. **MTProto Слушатель (`telethon_parser.py`)**:
   - Работает через клиент Telethon для связи с Telegram MTProto API.
   - В реальном времени получает посты из подплановых каналов.
   - **Фильтр интента вакансии**: Вызывает `is_vacancy_post(event.text)`. Если сообщение является чатовым вопросом или флудом, пост отклоняется (`non_vacancy_chat`).
   - Для подписчиков канала запускает генерацию ИИ-отклика `generate_draft_reply(u, event.text)`.
   - Записывает карточку `JobCardCreateDTO(..., draft_reply=draft)` в SQLite БД и отправляет уведомление в Telegram-бот.

2. **Движок Фильтрации и ИИ-Откликов (`matching_service.py`)**:
   - `is_vacancy_post(text: str) -> tuple[bool, float, list[str]]`:
     Анализирует текст на коммерческие триггеры найма (`ищу`, `требуется`, `оплата`, `бюджет`, `тз`, `в команду`, `отклик`, контакты) и штрафует обычный чатовый флуд (`кто знает`, `подскажите`, `как сделать`, `где скачать`).
   - `should_filter_by_stop_words(text, stop_words)`: Проверяет текст на пользовательские стоп-слова.
   - `generate_draft_reply(user_profile, job_text="", custom_instruction="")`: Генерирует вежливое персонализированное сопроводительное письмо с указанием имени, опыта в правильном русском склонении ("3 года", "5 лет"), стека инструментов и пользовательских дополнений/пожеланий.

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
- **Оплаты**: Поддержка Telegram Stars и ручных подтверждений администратором.

---

## 5. Покрытие Юнит-Тестами и Деплой

1. **Тестовая сюита**:
   - Запуск: `$env:PYTHONPATH='backend'; python -m pytest backend/tests`
   - Все **41 юнит-тест** полностью покрывают авторизацию, профиль, каналы, подписки, админку, парсер, карточки, классификатор интентов и перегенерацию откликов.

2. **Скрипт Деплоя (`scripts/deploy.py`)**:
   - Gate 1: Компиляция фронтенда React TypeScript (`npm run build`).
   - Gate 2: Запуск всех 41 Pytest тестов.
   - Gate 3: Синхронизация репозитория Git main (`git push origin main`).
   - Gate 4: Публикация фронтенда Vercel Production и обновление `vacancy-spotter-saas.service` на VPS.

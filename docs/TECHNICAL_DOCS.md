# 📘 Vacancy Spotter SaaS — Полное Техническое Руководство

В данном документе описана полная техническая спецификация архитектуры, структуры базы данных, API endpoints, парсера вакансий, Telegram-бота и систем взаимодействия компонентов **Vacancy Spotter SaaS**.

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
   - `draft_reply` (TEXT) — Автоматически сгенерированный проект сопроводительного письма.
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

## 3. Модуль Парсинга и Поиска (`backend/telethon_parser.py` & `backend/matching_service.py`)

1. **MTProto Слушатель (`telethon_parser.py`)**:
   - Использует клиент Telethon для работы через Telegram MTProto API.
   - Прослушивает все incoming сообщения в режиме реального времени.
   - Фильтрует по ключевым словам профессии (`KEYWORDS`).
   - Если пост содержит ключевые слова и не содержит стоп-слов пользователя, формирует карточку вакансии (`JobCardDTO`).
   - Отправляет уведомление пользователю в `@vacancy_spott_bot` с кнопками быстрых действий (Откликнуться, Переписать отклик, Перегенерировать).

2. **Движок Откликов (`matching_service.py`)**:
   - `should_filter_by_stop_words(text, stop_words)`: Проверяет пост на наличие пользовательских стоп-слов.
   - `generate_draft_reply(user_profile, job_text)`: Формирует вежливое персонализированное сопроводительное письмо с указанием имени, опыта в правильном склонении ("3 года", "5 лет"), стека и описания навыков.

---

## 4. Telegram Bot Service (`backend/bot_service.py`)

- **Библиотека**: `aiogram` 3.x.
- **Интерактивное меню**:
  - Кнопка `📱 Открыть личный кабинет` открывает WebApp (`https://frontend-psi-nine-2ydjpsdrfq.vercel.app`).
  - Инлайн кнопки под карточкой вакансии позволят мгновенно одобрить отклик, отредактировать текст или перейти к оригиналу поста в канале.
- **Команды**:
  - `/start` — Приветственное сообщение и открытие WebApp.
  - `/status` — Проверка статуса подписки и аккаунта.
  - `/help` — Руководство по работе.
  - `/debug` (только для админов) — Отображение живой статистики MTProto парсера в памяти (кол-во просмотренных постов, совпадений, запущен ли парсер).
- **Оплаты**: Поддержка Telegram Stars (Invoice Payments) и ручных подтверждений администратором.

---

## 5. Процесс Деплоя (`scripts/deploy.py`)

Скрипт деплоя автоматизирует 4 шага валидации и деплоя:
1. **Gate 1**: Компиляция фронтенда React TypeScript (`npm run build`).
2. **Gate 2**: Запуск пакета тестов Pytest backend (`pytest backend/tests`).
3. **Gate 3**: Синхронизация с Git репозиторием (`git push origin main`).
4. **Gate 4**: Деплой фронтенда на Vercel Production (`vercel --prod`) и обновление сервиса systemd на целевом VPS проекте (`vacancy-spotter-saas.service`).

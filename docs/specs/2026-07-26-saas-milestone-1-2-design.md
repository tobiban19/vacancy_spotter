# Spec: Vacancy Spotter SaaS — Milestones 1 & 2 (Database Schema & Telegram Mini App)

> **Дата**: 2026-07-26  
> **Статус**: На рассмотрении пользователем (Draft for Approval)  
> **Цель**: Архитектура мультитенентного бэкенда (БД + API) и веб-кабинета Telegram Mini App (TMA) для коммерческого запуска платформы.

---

## 1. Обзор системы и Цели

Превратить локальный бот в публичный сервис по подписке для любых фрилансеров (видеомонтажёры, моушн-дизайнеры, копирайтеры, 3D-художники, SMM и т.д.).

### Ключевые требования:
1. **Изоляция пользователей**: Каждый фрилансер видит только свои отклики и настраивает своё портфолио/резюме.
2. **Удобный веб-кабинет (TMA)**: Заполнение профиля, загрузка работ, выработка правил отбора и оплата происходят в Telegram Mini App прямо внутри бота.
3. **Каталог профессий и чатов**: Наличие преднастроенного списка проверенных каналов с вакансиями по категориям + возможность пользователю добавить свои чаты.
4. **Демо-доступ и подписка**: 1 день бесплатного демо для каждого нового пользователя, далее — платная подписка (Telegram Stars / Карты / Крипта).

---

## 2. Архитектура и Границы компонентов

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TELEGRAM CLIENT                                  │
└──────────────────────┬───────────────────────────────┬──────────────────────┘
                       │                               │
                       ▼                               ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│  Telegram Bot (aiogram 3)    │              │  Telegram Mini App (React)   │
│  • Отправка карточек         │              │  • Выбор профессии           │
│  • Кнопки одобрения/правоу   │              │  • Портфолио & Резюме        │
│  • Команда /stats            │              │  • Чаты & Подписка           │
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               │                                             │
               │         ┌───────────────────────────┐       │
               └────────►│  FastAPI Backend (REST)   │◄──────┘
                         │  • HMAC Verification      │
                         │  • Multi-tenant Services  │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │   PostgreSQL Data Store   │
                         │   (Мультипользовательская)│
                         └───────────────────────────┘
```

---

## 3. Майлстоун 1: Схема Базы Данных (PostgreSQL / SQLite Multi-Tenant)

### Таблицы бэкенда:

#### `users` (Пользователи платформы)
- `id`: BIGINT PRIMARY KEY (Telegram User ID)
- `username`: VARCHAR(64) NULLABLE
- `first_name`: VARCHAR(128) NOT NULL
- `profession_id`: VARCHAR(64) NOT NULL (например, `video_editor`, `motion_designer`, `copywriter`)
- `experience_years`: INT DEFAULT 0
- `location`: VARCHAR(128) DEFAULT 'Удалённо'
- `stop_words`: JSONB DEFAULT '[]' (слова-исключения, например Adobe, бартер)
- `subscription_status`: VARCHAR(32) DEFAULT 'demo' (`demo`, `active`, `expired`)
- `demo_until`: TIMESTAMP WITH TIME ZONE NOT NULL
- `subscription_until`: TIMESTAMP WITH TIME ZONE NULLABLE
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT NOW()

#### `resumes` (Профиль и факты кандидата)
- `id`: SERIAL PRIMARY KEY
- `user_id`: BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE
- `bio_summary`: TEXT NOT NULL
- `software_stack`: JSONB NOT NULL DEFAULT '[]'
- `equipment`: JSONB DEFAULT '{}'
- `metrics`: JSONB DEFAULT '{}'
- `contacts`: JSONB DEFAULT '{}'

#### `portfolios` (Кейсы и примеры работ)
- `id`: SERIAL PRIMARY KEY
- `user_id`: BIGINT REFERENCES users(id) ON DELETE CASCADE
- `title`: VARCHAR(256) NOT NULL
- `url`: VARCHAR(2048) NOT NULL
- `category`: VARCHAR(64) NOT NULL
- `orientation`: VARCHAR(32) DEFAULT 'horizontal' (`horizontal`, `vertical`)
- `description`: TEXT NOT NULL
- `tags`: JSONB NOT NULL DEFAULT '[]'
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT NOW()

#### `professions` (Каталог профессий)
- `id`: VARCHAR(64) PRIMARY KEY (`video_editor`, `motion_designer`, `copywriter`, `graphic_designer`, `3d_artist`, `smm`)
- `title_ru`: VARCHAR(128) NOT NULL
- `icon_emoji`: VARCHAR(16) NOT NULL

#### `channels` (Каталог чатов с вакансиями)
- `id`: SERIAL PRIMARY KEY
- `profession_id`: VARCHAR(64) REFERENCES professions(id) ON DELETE CASCADE
- `chat_id`: BIGINT NULLABLE
- `username`: VARCHAR(128) NOT NULL
- `title`: VARCHAR(256) NOT NULL
- `is_recommended`: BOOLEAN DEFAULT TRUE
- `is_active`: BOOLEAN DEFAULT TRUE

#### `user_channels` (Связка пользователей с чатами)
- `user_id`: BIGINT REFERENCES users(id) ON DELETE CASCADE
- `channel_id`: INT REFERENCES channels(id) ON DELETE CASCADE
- PRIMARY KEY (`user_id`, `channel_id`)

#### `user_job_cards` (Персональные карточки согласования)
- `id`: SERIAL PRIMARY KEY
- `user_id`: BIGINT REFERENCES users(id) ON DELETE CASCADE
- `job_id`: INT NOT NULL
- `status`: VARCHAR(32) DEFAULT 'awaiting_review' (`awaiting_review`, `approved`, `sent`, `skipped`, `snoozed`)
- `draft_reply`: TEXT NULLABLE
- `draft_rich`: JSONB NULLABLE
- `custom_prompt`: TEXT NULLABLE
- `created_at`: TIMESTAMP WITH TIME ZONE DEFAULT NOW()

---

## 4. Майлстоун 2: Telegram Mini App (TMA) — Экраны и UX

### Технологический стек TMA:
- **Frontend**: React 18 + Vite + TailwindCSS + Framer Motion.
- **Telegram Integration**: `@telegram-apps/sdk-react` + WebApp theme matching.
- **State Management**: Zustand / React Query.

### Сетка Экранов (4 вкладки навигации):

#### 📱 Вкладка 1: Профиль & Профессия
- Выбор профессии из списка с иконками (🎬 Видеомонтаж, 🎨 Motion Design, ✍️ Копирайтинг и т.д.).
- Опыт работы, город/удалёнка.
- Стек софта и стоп-слова (например: отсеивать «Adobe» или «бартер»).

#### 💼 Вкладка 2: Портфолио
- Список загруженных кейсов.
- Форма добавления нового кейса:
  - Название работы
  - Прямая ссылка (YouTube, Telegram, Vimeo, Behance)
  - Теги навыков (например: `reels`, `подкаст`, `s-log3`, `инфографика`)
  - Краткое описание результатов.

#### 🌐 Вкладка 3: Каналы вакансий
- **Рекомендованные каналы** (готовая подборка лучших чатов по выбранной профессии).
- Переключатель «Включить / Выключить канал».
- Кнопка **«+ Добавить свой чат»** (ввод ссылки `@username` публичного чата).

#### 💳 Вкладка 4: Подписка & Тарифы
- Отображение статуса: **«Демо-доступ активен ещё 18 часов»** или **«Подписка активна до 26.08.2026»**.
- Кнопка оплаты подписки в 1 клик (Telegram Stars / Карты РФ / Крипта).

---

## 5. Безопасность и Авторизация

1. **HMAC-SHA256 InitData Validation**:
   Все REST API эндпоинты бэкенда для TMA проверяют подлинность подписи `window.Telegram.WebApp.initData` через `BOT_TOKEN`. Поделать `user_id` невозможно.
2. **Мультитенентная изоляция**:
   Все SQL-запросы параметризованы и содержат условие `WHERE user_id = :current_user_id`.

---

## 6. План тестирования и проверки

- **Бэкенд**: Юнит-тесты Pydantic-схем, генерации токенов и миграций базы данных.
- **TMA Frontend**: Проверка валидности `initData`, адаптации светлой/тёмной темы Telegram и отзывчивости на мобильных устройствах iOS/Android.

"""
Multi-tenant SQLite Repository for Vacancy Spotter SaaS Backend.
"""

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import aiosqlite


def normalize_telegram_username(input_str: str) -> str:
    if not input_str:
        return ""
    s = input_str.strip()
    s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:t|telegram)\.(?:me|dog)/", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^s/", "", s, flags=re.IGNORECASE)
    s = s.lstrip("@")
    s = s.split("/")[0].split("?")[0]
    return s.strip()

from config import settings
from models import (
    AdminBanUpdateDTO,
    AdminStatsDTO,
    AdminSubscriptionUpdateDTO,
    AdminUserDetailDTO,
    AdminUserDTO,
    ChannelDTO,
    JobCardCreateDTO,
    JobCardDTO,
    JobCardStatusEnum,
    PortfolioItemCreateDTO,
    PortfolioItemDTO,
    ProfessionDTO,
    SubscriptionStatusDTO,
    UserProfileDTO,
    UserProfileUpdateDTO,
)

DEFAULT_PROFESSIONS = [
    ProfessionDTO(id="video_editor", title_ru="Видеомонтажёр / Рилик", icon_emoji="🎬"),
    ProfessionDTO(id="motion_designer", title_ru="Моушн-дизайнер / 2D/3D", icon_emoji="🎨"),
    ProfessionDTO(id="videographer", title_ru="Оператор / Видеограф", icon_emoji="📹"),
    ProfessionDTO(id="copywriter", title_ru="Копирайтер / Сценарист", icon_emoji="✍️"),
    ProfessionDTO(id="graphic_designer", title_ru="Графический дизайнер", icon_emoji="🖌️"),
    ProfessionDTO(id="smm_specialist", title_ru="SMM-специалист / Маркетолог", icon_emoji="📱"),
]

DEFAULT_CHANNELS = [
    # Video Editing & Videography
    {"profession_id": "video_editor", "username": "freelance_video", "title": "Видеомонтаж | Фриланс Заказы"},
    {"profession_id": "video_editor", "username": "reels_orders", "title": "Reels / Shorts / TikTok Заказы"},
    {"profession_id": "video_editor", "username": "kinomontage_jobs", "title": "Кино & Видео Монтаж"},
    
    # Motion Design
    {"profession_id": "motion_designer", "username": "motion_jobs", "title": "Motion Design & VFX Jobs"},
    {"profession_id": "motion_designer", "username": "cg_freelance", "title": "3D & Graphic Freelance"},
    
    # Copywriting
    {"profession_id": "copywriter", "username": "copywriter_jobs", "title": "Копирайтинг и Сценарии"},
    {"profession_id": "copywriter", "username": "text_orders", "title": "Тексты & Редактура"},

    # SMM
    {"profession_id": "smm_specialist", "username": "smm_vacancies", "title": "SMM & Трафик Вакансии"},
]


class DatabaseRepository:
    def __init__(self, db_path: Path | str) -> None:
        if isinstance(db_path, str) and db_path.startswith("sqlite+aiosqlite:///"):
            db_path = db_path.replace("sqlite+aiosqlite:///", "")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._init_tables()
        await self._seed_professions_and_channels()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _init_tables(self) -> None:
        assert self._conn is not None
        await self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT NOT NULL,
            profession_id TEXT NOT NULL DEFAULT 'video_editor',
            experience_years INT DEFAULT 1,
            location TEXT DEFAULT 'Удалённо',
            stop_words TEXT DEFAULT '[]',
            subscription_status TEXT DEFAULT 'demo',
            demo_until TEXT NOT NULL,
            subscription_until TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT UNIQUE NOT NULL,
            bio_summary TEXT DEFAULT '',
            software_stack TEXT DEFAULT '[]',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            orientation TEXT DEFAULT 'horizontal',
            description TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS professions (
            id TEXT PRIMARY KEY,
            title_ru TEXT NOT NULL,
            icon_emoji TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profession_id TEXT NOT NULL,
            chat_id BIGINT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            is_recommended BOOLEAN DEFAULT 1,
            is_active BOOLEAN DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS user_channels (
            user_id BIGINT NOT NULL,
            channel_id INTEGER NOT NULL,
            is_enabled BOOLEAN DEFAULT 1,
            PRIMARY KEY (user_id, channel_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS user_job_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            channel_title TEXT DEFAULT '',
            channel_username TEXT DEFAULT '',
            post_text TEXT NOT NULL,
            post_url TEXT DEFAULT '',
            post_date TEXT,
            status TEXT DEFAULT 'new',
            match_score REAL DEFAULT 0.0,
            matched_keywords TEXT DEFAULT '[]',
            draft_reply TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_user_job_cards_user_id ON user_job_cards(user_id);

        CREATE TABLE IF NOT EXISTS pipeline_trace (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT NOT NULL,
            event TEXT NOT NULL,
            channel TEXT DEFAULT '',
            post_url TEXT DEFAULT '',
            post_snippet TEXT DEFAULT '',
            user_id BIGINT DEFAULT NULL,
            card_id INTEGER DEFAULT NULL,
            bot_username TEXT DEFAULT '',
            bot_token_prefix TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pipeline_trace_url ON pipeline_trace(post_url);
        CREATE INDEX IF NOT EXISTS idx_pipeline_trace_trace_id ON pipeline_trace(trace_id);
        """)

        # Clean up duplicate channels if any exist
        await self._conn.execute("""
            DELETE FROM channels 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM channels 
                GROUP BY profession_id, LOWER(username)
            );
        """)

        # Clean up t.me/ prefixes in existing channels
        await self._conn.execute("UPDATE channels SET username = REPLACE(REPLACE(username, 't.me/', ''), 'https://t.me/', '') WHERE username LIKE '%t.me%';")
        await self._conn.execute("UPDATE channels SET title = '@' || username WHERE title LIKE '%t.me%';")

        await self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_channels_prof_user ON channels(profession_id, username);")
        
        # Additive migration for is_banned & ban_reason
        columns = await self._conn.execute("PRAGMA table_info(users);")
        existing_cols = {row["name"] for row in await columns.fetchall()}
        if "is_banned" not in existing_cols:
            await self._conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0;")
        if "ban_reason" not in existing_cols:
            await self._conn.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT DEFAULT NULL;")

        await self._conn.commit()

    async def _seed_professions_and_channels(self) -> None:
        assert self._conn is not None
        for p in DEFAULT_PROFESSIONS:
            await self._conn.execute(
                "INSERT OR IGNORE INTO professions (id, title_ru, icon_emoji) VALUES (?, ?, ?)",
                (p.id, p.title_ru, p.icon_emoji)
            )
        for c in DEFAULT_CHANNELS:
            await self._conn.execute(
                "INSERT OR IGNORE INTO channels (profession_id, username, title, is_recommended, is_active) VALUES (?, ?, ?, 1, 1)",
                (c["profession_id"], c["username"], c["title"])
            )
        await self._conn.commit()

    # ---------------------------------------------------------------------------
    # Authentication & User Provisioning
    # ---------------------------------------------------------------------------

    def verify_telegram_init_data(self, init_data_str: str) -> dict[str, Any] | None:
        """Validates Telegram WebApp initData string against BOT_TOKEN using HMAC-SHA256."""
        try:
            from urllib.parse import parse_qsl
            parsed = dict(parse_qsl(init_data_str, keep_blank_values=True))
            if "hash" not in parsed:
                return None
            hash_check = parsed.pop("hash")
            data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

            bot_token = settings.bot_token.get_secret_value()
            if not bot_token or bot_token == "placeholder_token":
                return None
            secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
            calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

            if hmac.compare_digest(calculated_hash, hash_check):
                user_data = json.loads(parsed.get("user", "{}"))
                return user_data
        except Exception:
            return None
        return None

    async def get_or_create_user(self, telegram_user: dict[str, Any]) -> tuple[UserProfileDTO, bool]:
        assert self._conn is not None
        user_id = int(telegram_user["id"])
        first_name = telegram_user.get("first_name", "Фрилансер")
        username = telegram_user.get("username")

        async with self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        now = datetime.now(timezone.utc)
        if row is not None:
            # User exists
            res_row = await self._get_resume(user_id)
            return self._row_to_profile(row, res_row), False

        # New user -> Create with 1-day demo
        demo_until = now + timedelta(days=settings.demo_duration_days)
        created_at_str = now.isoformat()
        demo_until_str = demo_until.isoformat()

        await self._conn.execute(
            """INSERT OR IGNORE INTO users (id, username, first_name, profession_id, experience_years, location, stop_words, subscription_status, demo_until, created_at)
               VALUES (?, ?, ?, 'video_editor', 1, 'Удалённо', '[]', 'demo', ?, ?)""",
            (user_id, username, first_name, demo_until_str, created_at_str)
        )
        await self._conn.execute(
            "INSERT OR IGNORE INTO resumes (user_id, bio_summary, software_stack) VALUES (?, '', '[]')",
            (user_id,)
        )
        await self._conn.commit()

        # Seed default channels for user
        await self.sync_default_channels_for_user(user_id, "video_editor")

        async with self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        res_row = await self._get_resume(user_id)
        assert row is not None
        return self._row_to_profile(row, res_row), True

    async def _get_resume(self, user_id: int) -> aiosqlite.Row | None:
        assert self._conn is not None
        async with self._conn.execute("SELECT * FROM resumes WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

    def _row_to_profile(self, u_row: aiosqlite.Row, r_row: aiosqlite.Row | None) -> UserProfileDTO:
        stop_words = json.loads(u_row["stop_words"] or "[]")
        software_stack = json.loads(r_row["software_stack"] if r_row else "[]")
        bio_summary = r_row["bio_summary"] if r_row else ""

        demo_until = datetime.fromisoformat(u_row["demo_until"])
        if demo_until.tzinfo is None:
            demo_until = demo_until.replace(tzinfo=timezone.utc)

        sub_until = None
        if u_row["subscription_until"]:
            sub_until = datetime.fromisoformat(u_row["subscription_until"])
            if sub_until.tzinfo is None:
                sub_until = sub_until.replace(tzinfo=timezone.utc)

        return UserProfileDTO(
            user_id=u_row["id"],
            username=u_row["username"],
            first_name=u_row["first_name"],
            profession_id=u_row["profession_id"],
            experience_years=u_row["experience_years"],
            location=u_row["location"],
            stop_words=stop_words,
            subscription_status=u_row["subscription_status"],
            demo_until=demo_until,
            subscription_until=sub_until,
            bio_summary=bio_summary,
            software_stack=software_stack,
        )

    async def get_user_profile(self, user_id: int) -> UserProfileDTO | None:
        assert self._conn is not None
        async with self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            u_row = await cursor.fetchone()
        if not u_row:
            return None
        r_row = await self._get_resume(user_id)
        return self._row_to_profile(u_row, r_row)

    # ---------------------------------------------------------------------------
    # User Profile & Portfolio CRUD
    # ---------------------------------------------------------------------------

    async def update_user_profile(self, user_id: int, update_dto: UserProfileUpdateDTO) -> UserProfileDTO:
        assert self._conn is not None
        async with self._conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)) as cursor:
            if not await cursor.fetchone():
                await self.get_or_create_user({"id": user_id, "first_name": "User"})

        if update_dto.profession_id is not None:
            await self._conn.execute("UPDATE users SET profession_id = ? WHERE id = ?", (update_dto.profession_id, user_id))
            await self.sync_default_channels_for_user(user_id, update_dto.profession_id)
        if update_dto.experience_years is not None:
            await self._conn.execute("UPDATE users SET experience_years = ? WHERE id = ?", (update_dto.experience_years, user_id))
        if update_dto.location is not None:
            await self._conn.execute("UPDATE users SET location = ? WHERE id = ?", (update_dto.location, user_id))
        if update_dto.stop_words is not None:
            await self._conn.execute("UPDATE users SET stop_words = ? WHERE id = ?", (json.dumps(update_dto.stop_words), user_id))

        if update_dto.bio_summary is not None or update_dto.software_stack is not None:
            res_row = await self._get_resume(user_id)
            if res_row:
                bio = update_dto.bio_summary if update_dto.bio_summary is not None else res_row["bio_summary"]
                stack = json.dumps(update_dto.software_stack) if update_dto.software_stack is not None else res_row["software_stack"]
                await self._conn.execute("UPDATE resumes SET bio_summary = ?, software_stack = ? WHERE user_id = ?", (bio, stack, user_id))
            else:
                bio = update_dto.bio_summary or ""
                stack = json.dumps(update_dto.software_stack or [])
                await self._conn.execute("INSERT INTO resumes (user_id, bio_summary, software_stack) VALUES (?, ?, ?)", (user_id, bio, stack))

        await self._conn.commit()
        async with self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        res_row = await self._get_resume(user_id)
        assert row is not None
        return self._row_to_profile(row, res_row)

    async def get_portfolio(self, user_id: int) -> list[PortfolioItemDTO]:
        assert self._conn is not None
        items = []
        async with self._conn.execute("SELECT * FROM portfolios WHERE user_id = ? ORDER BY id DESC", (user_id,)) as cursor:
            async for row in cursor:
                items.append(PortfolioItemDTO(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    url=row["url"],
                    category=row["category"],
                    orientation=row["orientation"],
                    description=row["description"],
                    tags=json.loads(row["tags"] or "[]"),
                    created_at=datetime.fromisoformat(row["created_at"])
                ))
        return items

    async def get_portfolio_item(self, user_id: int, item_id: int) -> PortfolioItemDTO | None:
        assert self._conn is not None
        async with self._conn.execute("SELECT * FROM portfolios WHERE id = ? AND user_id = ?", (item_id, user_id)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return PortfolioItemDTO(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            url=row["url"],
            category=row["category"],
            orientation=row["orientation"],
            description=row["description"],
            tags=json.loads(row["tags"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"])
        )

    async def add_portfolio_item(self, user_id: int, item_dto: PortfolioItemCreateDTO) -> PortfolioItemDTO:
        assert self._conn is not None
        async with self._conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)) as cursor:
            if not await cursor.fetchone():
                await self.get_or_create_user({"id": user_id, "first_name": "User"})
        now_str = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(item_dto.tags)
        cursor = await self._conn.execute(
            """INSERT INTO portfolios (user_id, title, url, category, orientation, description, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, item_dto.title, item_dto.url, item_dto.category, item_dto.orientation, item_dto.description, tags_json, now_str)
        )
        await self._conn.commit()
        item_id = cursor.lastrowid
        assert item_id is not None
        return PortfolioItemDTO(
            id=item_id,
            user_id=user_id,
            title=item_dto.title,
            url=item_dto.url,
            category=item_dto.category,
            orientation=item_dto.orientation,
            description=item_dto.description,
            tags=item_dto.tags,
            created_at=datetime.fromisoformat(now_str)
        )

    async def update_portfolio_item(self, user_id: int, item_id: int, item_dto: PortfolioItemCreateDTO) -> PortfolioItemDTO | None:
        assert self._conn is not None
        tags_json = json.dumps(item_dto.tags)
        cursor = await self._conn.execute(
            """UPDATE portfolios
               SET title = ?, url = ?, category = ?, orientation = ?, description = ?, tags = ?
               WHERE id = ? AND user_id = ?""",
            (item_dto.title, item_dto.url, item_dto.category, item_dto.orientation, item_dto.description, tags_json, item_id, user_id)
        )
        await self._conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_portfolio_item(user_id, item_id)

    async def delete_portfolio_item(self, user_id: int, item_id: int) -> bool:
        assert self._conn is not None
        cursor = await self._conn.execute("DELETE FROM portfolios WHERE id = ? AND user_id = ?", (item_id, user_id))
        await self._conn.commit()
        return cursor.rowcount > 0

    # ---------------------------------------------------------------------------
    # Professions & Channels
    # ---------------------------------------------------------------------------

    async def get_professions(self) -> list[ProfessionDTO]:
        assert self._conn is not None
        items = []
        async with self._conn.execute("SELECT * FROM professions ORDER BY id ASC") as cursor:
            async for row in cursor:
                items.append(ProfessionDTO(id=row["id"], title_ru=row["title_ru"], icon_emoji=row["icon_emoji"]))
        return items

    async def sync_default_channels_for_user(self, user_id: int, profession_id: str) -> None:
        assert self._conn is not None
        async with self._conn.execute("SELECT id FROM channels WHERE profession_id = ?", (profession_id,)) as cursor:
            async for row in cursor:
                await self._conn.execute(
                    "INSERT OR IGNORE INTO user_channels (user_id, channel_id, is_enabled) VALUES (?, ?, 1)",
                    (user_id, row["id"])
                )
        await self._conn.commit()

    async def get_user_channels(self, user_id: int, profession_id: str) -> list[ChannelDTO]:
        assert self._conn is not None
        items = []
        sql = """
        SELECT c.id, c.profession_id, c.username, c.title, c.is_recommended, COALESCE(uc.is_enabled, 1) as is_enabled
        FROM channels c
        LEFT JOIN user_channels uc ON uc.channel_id = c.id AND uc.user_id = ?
        WHERE c.profession_id = ? AND c.is_active = 1
        GROUP BY LOWER(c.username)
        """
        async with self._conn.execute(sql, (user_id, profession_id)) as cursor:
            async for row in cursor:
                items.append(ChannelDTO(
                    id=row["id"],
                    profession_id=row["profession_id"],
                    username=row["username"],
                    title=row["title"],
                    is_recommended=bool(row["is_recommended"]),
                    is_enabled=bool(row["is_enabled"])
                ))
        return items

    async def toggle_user_channel(self, user_id: int, channel_id: int, enabled: bool) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """INSERT INTO user_channels (user_id, channel_id, is_enabled) VALUES (?, ?, ?)
               ON CONFLICT(user_id, channel_id) DO UPDATE SET is_enabled = excluded.is_enabled""",
            (user_id, channel_id, int(enabled))
        )
        await self._conn.commit()

    async def add_custom_channel(self, user_id: int, profession_id: str, username_or_link: str) -> ChannelDTO:
        assert self._conn is not None
        clean_user = normalize_telegram_username(username_or_link)
        cursor = await self._conn.execute(
            "INSERT INTO channels (profession_id, username, title, is_recommended, is_active) VALUES (?, ?, ?, 0, 1) ON CONFLICT(profession_id, username) DO UPDATE SET is_active = 1",
            (profession_id, clean_user, f"@{clean_user}")
        )
        ch_id = cursor.lastrowid
        if not ch_id:
            async with self._conn.execute("SELECT id FROM channels WHERE profession_id = ? AND username = ?", (profession_id, clean_user)) as c:
                row = await c.fetchone()
                ch_id = row["id"] if row else 1

        await self._conn.execute(
            "INSERT INTO user_channels (user_id, channel_id, is_enabled) VALUES (?, ?, 1) ON CONFLICT(user_id, channel_id) DO UPDATE SET is_enabled = 1",
            (user_id, ch_id)
        )
        await self._conn.commit()
        return ChannelDTO(
            id=ch_id,
            profession_id=profession_id,
            username=clean_user,
            title=f"@{clean_user}",
            is_recommended=False,
            is_enabled=True
        )

    async def get_users_subscribed_to_channel(self, channel_username: str) -> list[UserProfileDTO]:
        assert self._conn is not None
        clean_user = normalize_telegram_username(channel_username).lower()
        sql = """
        SELECT DISTINCT u.*
        FROM users u
        JOIN user_channels uc ON uc.user_id = u.id
        JOIN channels c ON c.id = uc.channel_id
        WHERE (LOWER(c.username) = ? OR LOWER(c.username) = ?) AND uc.is_enabled = 1 AND c.is_active = 1
        """
        profiles = []
        async with self._conn.execute(sql, (clean_user, f"@{clean_user}")) as cursor:
            async for row in cursor:
                res_row = await self._get_resume(row["id"])
                profiles.append(self._row_to_profile(row, res_row))
        return profiles


    # ---------------------------------------------------------------------------
    # Subscription Status
    # ---------------------------------------------------------------------------

    async def get_subscription_status(self, user_id: int) -> SubscriptionStatusDTO:
        assert self._conn is not None
        async with self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            now = datetime.now(timezone.utc)
            return SubscriptionStatusDTO(
                status="expired",
                demo_until=now,
                subscription_until=None,
                days_left=0,
                is_valid=False
            )
        now = datetime.now(timezone.utc)
        demo_until = datetime.fromisoformat(row["demo_until"])
        if demo_until.tzinfo is None:
            demo_until = demo_until.replace(tzinfo=timezone.utc)

        sub_until = None
        if row["subscription_until"]:
            sub_until = datetime.fromisoformat(row["subscription_until"])
            if sub_until.tzinfo is None:
                sub_until = sub_until.replace(tzinfo=timezone.utc)

        if sub_until and sub_until > now:
            status = "active"
            days_left = (sub_until - now).days + 1
            is_valid = True
        elif demo_until > now:
            status = "demo"
            days_left = (demo_until - now).days + 1
            is_valid = True
        else:
            status = "expired"
            days_left = 0
            is_valid = False

        return SubscriptionStatusDTO(
            status=status,
            demo_until=demo_until,
            subscription_until=sub_until,
            days_left=days_left,
            is_valid=is_valid
        )

    async def extend_user_subscription(self, user_id: int, days: int) -> SubscriptionStatusDTO:
        assert self._conn is not None
        async with self._conn.execute("SELECT subscription_until FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            await self.get_or_create_user({"id": user_id, "first_name": "User"})
            async with self._conn.execute("SELECT subscription_until FROM users WHERE id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()

        now = datetime.now(timezone.utc)
        existing_until: datetime | None = None
        if row and row["subscription_until"]:
            try:
                existing_until = datetime.fromisoformat(row["subscription_until"])
                if existing_until.tzinfo is None:
                    existing_until = existing_until.replace(tzinfo=timezone.utc)
            except ValueError:
                existing_until = None

        base_time = max(now, existing_until) if existing_until else now
        new_sub_until = base_time + timedelta(days=days)

        await self._conn.execute(
            "UPDATE users SET subscription_until = ?, subscription_status = 'active' WHERE id = ?",
            (new_sub_until.isoformat(), user_id)
        )
        await self._conn.commit()

        return await self.get_subscription_status(user_id)

    # ---------------------------------------------------------------------------
    # Job Cards CRUD
    # ---------------------------------------------------------------------------

    def _row_to_job_card(self, row: aiosqlite.Row) -> JobCardDTO:
        status_str = row["status"] or "new"
        try:
            status_val = JobCardStatusEnum(status_str)
        except ValueError:
            status_val = JobCardStatusEnum.NEW

        matched_kw = json.loads(row["matched_keywords"] or "[]")
        post_date = datetime.fromisoformat(row["post_date"]) if row["post_date"] else None
        created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc)

        return JobCardDTO(
            id=row["id"],
            user_id=row["user_id"],
            channel_title=row["channel_title"] or "",
            channel_username=row["channel_username"] or "",
            post_text=row["post_text"],
            post_url=row["post_url"] or "",
            post_date=post_date,
            status=status_val,
            match_score=float(row["match_score"] or 0.0),
            matched_keywords=matched_kw,
            draft_reply=row["draft_reply"] or "",
            created_at=created_at,
        )

    async def create_job_card(self, job_card: JobCardCreateDTO) -> JobCardDTO:
        assert self._conn is not None
        now_str = datetime.now(timezone.utc).isoformat()
        post_date_str = job_card.post_date.isoformat() if job_card.post_date else now_str
        status_str = job_card.status.value if isinstance(job_card.status, JobCardStatusEnum) else str(job_card.status)
        keywords_json = json.dumps(job_card.matched_keywords)

        cursor = await self._conn.execute(
            """INSERT INTO user_job_cards
               (user_id, channel_title, channel_username, post_text, post_url, post_date, status, match_score, matched_keywords, draft_reply, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_card.user_id,
                job_card.channel_title,
                job_card.channel_username,
                job_card.post_text,
                job_card.post_url,
                post_date_str,
                status_str,
                job_card.match_score,
                keywords_json,
                job_card.draft_reply,
                now_str,
            )
        )
        await self._conn.commit()
        card_id = cursor.lastrowid
        assert card_id is not None

        async with self._conn.execute("SELECT * FROM user_job_cards WHERE id = ?", (card_id,)) as cur:
            row = await cur.fetchone()
        assert row is not None
        return self._row_to_job_card(row)

    async def get_user_job_cards(
        self,
        user_id: int,
        status: str | JobCardStatusEnum | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[JobCardDTO]:
        assert self._conn is not None
        cards = []
        if status is not None:
            status_str = status.value if isinstance(status, JobCardStatusEnum) else str(status)
            query = "SELECT * FROM user_job_cards WHERE user_id = ? AND status = ? ORDER BY id DESC LIMIT ? OFFSET ?"
            params: tuple[Any, ...] = (user_id, status_str, limit, offset)
        else:
            query = "SELECT * FROM user_job_cards WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?"
            params = (user_id, limit, offset)

        async with self._conn.execute(query, params) as cursor:
            async for row in cursor:
                cards.append(self._row_to_job_card(row))
        return cards

    async def get_job_card_by_id(self, card_id: int, user_id: int) -> JobCardDTO | None:
        assert self._conn is not None
        async with self._conn.execute("SELECT * FROM user_job_cards WHERE id = ? AND user_id = ?", (card_id, user_id)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_job_card(row)

    async def update_job_card_status(self, card_id: int, user_id: int, status: str | JobCardStatusEnum) -> JobCardDTO | None:
        assert self._conn is not None
        status_str = status.value if isinstance(status, JobCardStatusEnum) else str(status)
        cursor = await self._conn.execute(
            "UPDATE user_job_cards SET status = ? WHERE id = ? AND user_id = ?",
            (status_str, card_id, user_id)
        )
        await self._conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_job_card_by_id(card_id, user_id)

    async def update_job_card_draft(self, card_id: int, user_id: int, draft_reply: str) -> JobCardDTO | None:
        assert self._conn is not None
        cursor = await self._conn.execute(
            "UPDATE user_job_cards SET draft_reply = ? WHERE id = ? AND user_id = ?",
            (draft_reply, card_id, user_id)
        )
        await self._conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_job_card_by_id(card_id, user_id)

    # ---------------------------------------------------------------------------
    # Admin & User Management Methods
    # ---------------------------------------------------------------------------

    async def is_user_banned(self, user_id: int) -> bool:
        assert self._conn is not None
        async with self._conn.execute("SELECT is_banned FROM users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False
        return bool(row["is_banned"])

    async def get_admin_stats(self) -> AdminStatsDTO:
        assert self._conn is not None
        async with self._conn.execute("""
            SELECT 
                COUNT(*) as total_users,
                SUM(CASE WHEN subscription_status = 'active' AND (is_banned IS NULL OR is_banned = 0) THEN 1 ELSE 0 END) as active_paid,
                SUM(CASE WHEN subscription_status = 'demo' AND (is_banned IS NULL OR is_banned = 0) THEN 1 ELSE 0 END) as demo_users,
                SUM(CASE WHEN subscription_status = 'expired' AND (is_banned IS NULL OR is_banned = 0) THEN 1 ELSE 0 END) as expired_users,
                SUM(CASE WHEN is_banned = 1 THEN 1 ELSE 0 END) as banned_users
            FROM users
        """) as cursor:
            row = await cursor.fetchone()

        if not row:
            return AdminStatsDTO(
                total_users=0,
                active_paid_users=0,
                demo_users=0,
                expired_users=0,
                banned_users=0,
            )

        return AdminStatsDTO(
            total_users=row["total_users"] or 0,
            active_paid_users=row["active_paid"] or 0,
            demo_users=row["demo_users"] or 0,
            expired_users=row["expired_users"] or 0,
            banned_users=row["banned_users"] or 0,
        )

    async def get_admin_users_list(
        self, page: int = 1, limit: int = 20, search: str = "", status_filter: str = "all"
    ) -> tuple[list[AdminUserDTO], int]:
        assert self._conn is not None
        offset = (page - 1) * limit
        where_clauses: list[str] = []
        params: list[Any] = []

        if search.strip():
            s = f"%{search.strip()}%"
            where_clauses.append("(u.username LIKE ? OR u.first_name LIKE ? OR CAST(u.id AS TEXT) LIKE ?)")
            params.extend([s, s, s])

        if status_filter == "banned":
            where_clauses.append("u.is_banned = 1")
        elif status_filter in ("demo", "active", "expired"):
            where_clauses.append("(u.is_banned IS NULL OR u.is_banned = 0)")
            where_clauses.append("u.subscription_status = ?")
            params.append(status_filter)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Count query
        count_sql = f"SELECT COUNT(*) as total FROM users u {where_sql}"
        async with self._conn.execute(count_sql, params) as cursor:
            total_row = await cursor.fetchone()
            total_count = total_row["total"] if total_row else 0

        # Query items with channel count
        query_sql = f"""
            SELECT 
                u.*,
                (SELECT COUNT(*) FROM user_channels uc WHERE uc.user_id = u.id AND uc.is_enabled = 1) as channels_count
            FROM users u
            {where_sql}
            ORDER BY u.created_at DESC
            LIMIT ? OFFSET ?
        """
        queryParams = list(params) + [limit, offset]

        users: list[AdminUserDTO] = []
        async with self._conn.execute(query_sql, queryParams) as cursor:
            async for row in cursor:
                demo_until_dt = datetime.fromisoformat(row["demo_until"]) if row["demo_until"] else datetime.now(timezone.utc)
                sub_until_dt = datetime.fromisoformat(row["subscription_until"]) if row["subscription_until"] else None
                created_at_dt = datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc)

                users.append(
                    AdminUserDTO(
                        user_id=row["id"],
                        username=row["username"],
                        first_name=row["first_name"],
                        profession_id=row["profession_id"],
                        subscription_status=row["subscription_status"] or "demo",
                        demo_until=demo_until_dt,
                        subscription_until=sub_until_dt,
                        is_banned=bool(row["is_banned"]),
                        ban_reason=row["ban_reason"],
                        channels_count=row["channels_count"] or 0,
                        created_at=created_at_dt,
                    )
                )

        return users, total_count

    async def get_admin_user_details(self, user_id: int) -> AdminUserDetailDTO | None:
        assert self._conn is not None
        # User profile
        profile = await self.get_user_profile(user_id)
        if not profile:
            return None

        # Fetch extra user columns
        async with self._conn.execute("SELECT is_banned, ban_reason, created_at FROM users WHERE id = ?", (user_id,)) as cursor:
            u_row = await cursor.fetchone()

        is_banned = bool(u_row["is_banned"]) if u_row else False
        ban_reason = u_row["ban_reason"] if u_row else None
        created_at_dt = datetime.fromisoformat(u_row["created_at"]) if u_row and u_row["created_at"] else datetime.now(timezone.utc)

        # Resume / Bio summary
        bio_summary = ""
        software_stack: list[str] = []
        async with self._conn.execute("SELECT bio_summary, software_stack FROM resumes WHERE user_id = ?", (user_id,)) as cursor:
            r_row = await cursor.fetchone()
            if r_row:
                bio_summary = r_row["bio_summary"] or ""
                try:
                    software_stack = json.loads(r_row["software_stack"] or "[]")
                except Exception:
                    software_stack = []

        # Connected channels
        connected_channels: list[dict[str, Any]] = []
        async with self._conn.execute("""
            SELECT c.id, c.username, c.title, c.profession_id, uc.is_enabled
            FROM user_channels uc
            JOIN channels c ON uc.channel_id = c.id
            WHERE uc.user_id = ?
        """, (user_id,)) as cursor:
            async for ch in cursor:
                connected_channels.append({
                    "channel_id": ch["id"],
                    "username": ch["username"],
                    "title": ch["title"],
                    "profession_id": ch["profession_id"],
                    "is_enabled": bool(ch["is_enabled"]),
                })

        return AdminUserDetailDTO(
            profile=profile,
            is_banned=is_banned,
            ban_reason=ban_reason,
            bio_summary=bio_summary,
            software_stack=software_stack,
            stop_words=profile.stop_words,
            connected_channels=connected_channels,
            created_at=created_at_dt,
        )

    async def update_user_subscription(
        self, user_id: int, update_dto: AdminSubscriptionUpdateDTO
    ) -> UserProfileDTO | None:
        assert self._conn is not None
        now = datetime.now(timezone.utc)

        # Fetch current sub
        profile = await self.get_user_profile(user_id)
        if not profile:
            return None

        new_status = profile.subscription_status
        new_until = profile.subscription_until

        if update_dto.action == "add_days":
            days_to_add = update_dto.days or 30
            # If current subscription is in the future, extend from that date, otherwise from now
            base_date = new_until if (new_until and new_until > now) else now
            new_until = base_date + timedelta(days=days_to_add)
            new_status = "active"
        elif update_dto.action == "set_status":
            if update_dto.status:
                new_status = update_dto.status
        elif update_dto.action == "revoke":
            new_status = "expired"
            new_until = now

        new_until_str = new_until.isoformat() if new_until else None

        await self._conn.execute(
            "UPDATE users SET subscription_status = ?, subscription_until = ? WHERE id = ?",
            (new_status, new_until_str, user_id)
        )
        await self._conn.commit()
        return await self.get_user_profile(user_id)

    async def set_user_ban_status(self, user_id: int, update_dto: AdminBanUpdateDTO) -> bool:
        assert self._conn is not None
        cursor = await self._conn.execute(
            "UPDATE users SET is_banned = ?, ban_reason = ? WHERE id = ?",
            (1 if update_dto.is_banned else 0, update_dto.ban_reason, user_id)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    # ---------------------------------------------------------------------------
    # Pipeline Tracing & Diagnostics
    # ---------------------------------------------------------------------------

    async def log_trace(
        self,
        trace_id: str,
        event: str,
        *,
        channel: str = "",
        post_url: str = "",
        post_snippet: str = "",
        user_id: int | None = None,
        card_id: int | None = None,
        bot_username: str = "",
        bot_token_prefix: str = "",
        detail: str = "",
    ) -> None:
        """Record a pipeline trace event. Auto-prunes to keep last 500 rows."""
        assert self._conn is not None
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """INSERT INTO pipeline_trace
               (trace_id, event, channel, post_url, post_snippet, user_id, card_id,
                bot_username, bot_token_prefix, detail, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trace_id, event, channel, post_url, post_snippet[:100] if post_snippet else "",
             user_id, card_id, bot_username, bot_token_prefix, detail, now),
        )
        await self._conn.commit()
        # Auto-prune: keep only latest 500 entries
        await self._conn.execute(
            "DELETE FROM pipeline_trace WHERE id NOT IN (SELECT id FROM pipeline_trace ORDER BY id DESC LIMIT 500)"
        )
        await self._conn.commit()

    async def get_traces_by_url(self, url_fragment: str, limit: int = 20) -> list[dict]:
        """Find trace events matching a post URL fragment."""
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT * FROM pipeline_trace WHERE post_url LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{url_fragment}%", limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_traces_by_card_id(self, card_id: int, limit: int = 20) -> list[dict]:
        """Find trace events for a specific card_id."""
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT * FROM pipeline_trace WHERE card_id = ? ORDER BY id DESC LIMIT ?",
            (card_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_traces_by_trace_id(self, trace_id: str) -> list[dict]:
        """Get all events for a specific trace_id."""
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT * FROM pipeline_trace WHERE trace_id = ? ORDER BY id ASC",
            (trace_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_recent_traces(self, limit: int = 20) -> list[dict]:
        """Get most recent trace events."""
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT * FROM pipeline_trace ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

"""
Telethon MTProto Channel Listener for Vacancy Spotter SaaS.
Monitors Telegram channels and posts matched job cards to @vacancy_spott_bot.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from telethon import TelegramClient, events

from config import settings
from database import DatabaseRepository
from models import JobCardCreateDTO, JobCardStatusEnum
from matching_service import is_vacancy_post, generate_draft_reply
import bot_service

log = logging.getLogger("saas_parser")
repo = DatabaseRepository(settings.database_url)

KEYWORDS = (
    "монтаж", "монтажёр", "монтажер", "видеомонтаж", "видеограф", "видеоредактор",
    "reels", "рилс", "рилсы", "premiere", "davinci", "after effects",
    "color grading", "цветокоррекция", "цветокор", "постпродакшн", "постпродакшен",
    "motion design", "моушн", "3d", "cg", "копирайтер", "дизайнер", "smm",
)

SESSION_PATH = Path(__file__).parent.parent / "data" / "userbot_session.session"
if not SESSION_PATH.exists():
    OLD_SESSION = Path(__file__).parent.parent.parent / "vacancy-spotter" / "data" / "userbot_session.session"
    if OLD_SESSION.exists():
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(OLD_SESSION, SESSION_PATH)

client = TelegramClient(
    str(SESSION_PATH),
    settings.telegram_api_id,
    settings.telegram_api_hash.get_secret_value(),
)


# ---------------------------------------------------------------------------
# Parser Stats (in-memory, queried by /debug command)
# ---------------------------------------------------------------------------

@dataclass
class ParserStats:
    messages_seen: int = 0
    keywords_matched: int = 0
    cards_sent: int = 0
    cards_failed: int = 0
    last_activity_at: str | None = None
    last_channel: str = ""
    started_at: str = ""
    is_running: bool = False
    recent_trace_ids: list[str] = field(default_factory=list)

parser_stats = ParserStats()


def _gen_trace_id() -> str:
    """Short 8-char hex trace ID for log correlation."""
    return uuid.uuid4().hex[:8]


def _token_prefix() -> str:
    """First 10 chars of bot token for safe logging."""
    try:
        return settings.bot_token.get_secret_value()[:10]
    except Exception:
        return "unknown"


async def _safe_log_trace(trace_id: str, event: str, **kwargs) -> None:
    """Log trace event, silently ignoring DB errors."""
    try:
        if repo._conn is None:
            await repo.open()
        await repo.log_trace(trace_id, event, **kwargs)
    except Exception as exc:
        log.warning("[TRACE:%s] Failed to write trace: %s", trace_id, exc)


@client.on(events.NewMessage(incoming=True))
async def handle_new_channel_post(event: events.NewMessage.Event):
    if not event.text:
        return

    parser_stats.messages_seen += 1

    text_lower = event.text.lower()
    matched_kws = [kw for kw in KEYWORDS if kw in text_lower]
    if not matched_kws:
        return

    parser_stats.keywords_matched += 1

    chat = await event.get_chat()
    username = getattr(chat, "username", None) or ""
    title = getattr(chat, "title", None) or username or "Telegram Channel"

    if not username:
        return

    post_url = f"https://t.me/{username}/{event.id}"
    trace_id = _gen_trace_id()

    parser_stats.last_activity_at = datetime.now(timezone.utc).isoformat()
    parser_stats.last_channel = f"@{username}"
    # Keep last 10 trace_ids for /debug
    parser_stats.recent_trace_ids = [trace_id] + parser_stats.recent_trace_ids[:9]

    log.info("[TRACE:%s] 📥 received | @%s | keywords: %s | %s",
             trace_id, username, ", ".join(matched_kws), post_url)

    await _safe_log_trace(
        trace_id, "received",
        channel=f"@{username}", post_url=post_url,
        post_snippet=event.text[:100].replace("\n", " "),
        detail=f"matched keywords: {', '.join(matched_kws)}",
    )

    is_vac, vac_score, vac_triggers = is_vacancy_post(event.text)
    if not is_vac:
        snippet = event.text[:100].replace("\n", " ")
        log.info("[TRACE:%s] 💬 non_vacancy_chat | @%s | text: %s", trace_id, username, snippet)
        await _safe_log_trace(
            trace_id, "non_vacancy_chat",
            channel=f"@{username}", post_url=post_url,
            post_snippet=snippet,
            detail=f"Intent score {vac_score} below threshold",
        )
        return

    try:
        users = await repo.get_users_subscribed_to_channel(username)
        bot = bot_service.get_bot()
        bot_info = None
        try:
            bot_info = await bot.get_me()
        except Exception:
            pass
        bot_uname = f"@{bot_info.username}" if bot_info and bot_info.username else "unknown"
        token_pfx = _token_prefix()

        if not users:
            log.info("[TRACE:%s] 👤 no_subscribers | @%s", trace_id, username)
            await _safe_log_trace(
                trace_id, "no_subscribers",
                channel=f"@{username}", post_url=post_url,
                bot_username=bot_uname, bot_token_prefix=token_pfx,
                detail="No users subscribed to this channel",
            )
            return

        log.info("[TRACE:%s] 👤 users_matched | %d users for @%s",
                 trace_id, len(users), username)
        await _safe_log_trace(
            trace_id, "users_matched",
            channel=f"@{username}", post_url=post_url,
            bot_username=bot_uname, bot_token_prefix=token_pfx,
            detail=f"Matched {len(users)} user(s): {', '.join(str(u.user_id) for u in users)}",
        )

        for u in users:
            if any(sw.strip() and sw.strip().lower() in text_lower for sw in u.stop_words if sw):
                log.info("[TRACE:%s] ⛔ stop_word | user %s", trace_id, u.user_id)
                await _safe_log_trace(
                    trace_id, "stop_word_filtered",
                    channel=f"@{username}", post_url=post_url,
                    user_id=u.user_id, bot_username=bot_uname, bot_token_prefix=token_pfx,
                    detail="Filtered by user's stop-words",
                )
                continue

            draft = generate_draft_reply(u, event.text)

            card_create = JobCardCreateDTO(
                user_id=u.user_id,
                channel_title=title,
                channel_username=username,
                post_text=event.text,
                post_url=post_url,
                status=JobCardStatusEnum.NEW,
                match_score=vac_score,
                draft_reply=draft,
            )
            card = await repo.create_job_card(card_create)

            log.info("[TRACE:%s] 📋 card_created | #%s for user %s",
                     trace_id, card.id, u.user_id)
            await _safe_log_trace(
                trace_id, "card_created",
                channel=f"@{username}", post_url=post_url,
                user_id=u.user_id, card_id=card.id,
                bot_username=bot_uname, bot_token_prefix=token_pfx,
            )

            try:
                result = await bot_service.send_job_card_to_user(bot, card)
                if result:
                    parser_stats.cards_sent += 1
                    log.info("[TRACE:%s] ✅ card_sent | #%s → user %s via %s (token: %s...)",
                             trace_id, card.id, u.user_id, bot_uname, token_pfx)
                    await _safe_log_trace(
                        trace_id, "card_sent",
                        channel=f"@{username}", post_url=post_url,
                        user_id=u.user_id, card_id=card.id,
                        bot_username=bot_uname, bot_token_prefix=token_pfx,
                        detail="Message sent successfully",
                    )
                else:
                    parser_stats.cards_failed += 1
                    log.warning("[TRACE:%s] ⚠️ card_send_failed | #%s → user %s (returned None)",
                                trace_id, card.id, u.user_id)
                    await _safe_log_trace(
                        trace_id, "card_send_failed",
                        channel=f"@{username}", post_url=post_url,
                        user_id=u.user_id, card_id=card.id,
                        bot_username=bot_uname, bot_token_prefix=token_pfx,
                        detail="send_job_card_to_user returned None",
                    )
            except Exception as send_exc:
                parser_stats.cards_failed += 1
                log.error("[TRACE:%s] ❌ card_send_error | #%s → user %s: %s",
                          trace_id, card.id, u.user_id, send_exc)
                await _safe_log_trace(
                    trace_id, "card_send_error",
                    channel=f"@{username}", post_url=post_url,
                    user_id=u.user_id, card_id=card.id,
                    bot_username=bot_uname, bot_token_prefix=token_pfx,
                    detail=str(send_exc)[:200],
                )
    except Exception as exc:
        log.error("[TRACE:%s] ❌ pipeline_error | @%s: %s", trace_id, username, exc)
        await _safe_log_trace(
            trace_id, "pipeline_error",
            channel=f"@{username}", post_url=post_url,
            detail=str(exc)[:200],
        )


async def start_parser():
    await repo.open()
    parser_stats.started_at = datetime.now(timezone.utc).isoformat()
    parser_stats.is_running = True
    log.info("Starting Telethon Channel Parser using session %s...", SESSION_PATH)
    await client.start()
    log.info("Telethon Channel Parser active & listening to Telegram channels!")
    await client.run_until_disconnected()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    asyncio.run(start_parser())

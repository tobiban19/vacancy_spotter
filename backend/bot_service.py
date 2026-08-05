"""
Telegram Bot Service for Vacancy Spotter SaaS (@vacancy_spott_bot).
"""

import html
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from config import settings
from database import DatabaseRepository
from matching_service import generate_draft_reply
from models import JobCardDTO, JobCardStatusEnum

log = logging.getLogger("saas_bot")

router = Router()
repo = DatabaseRepository(settings.database_url)

USER_REGEN_WAITING: dict[int, int] = {}

_bot_instance: Bot | None = None


def get_bot() -> Bot:
    global _bot_instance
    if _bot_instance is None:
        token = settings.bot_token.get_secret_value()
        _bot_instance = Bot(token=token)
    return _bot_instance


DEFAULT_WEBAPP_URL = "https://frontend-psi-nine-2ydjpsdrfq.vercel.app"


def get_welcome_keyboard(webapp_url: str = DEFAULT_WEBAPP_URL) -> InlineKeyboardMarkup:
    if webapp_url.startswith("https://"):
        btn = InlineKeyboardButton(
            text="📱 Открыть личный кабинет",
            web_app=WebAppInfo(url=webapp_url),
        )
    else:
        btn = InlineKeyboardButton(
            text="📱 Открыть личный кабинет",
            url=webapp_url,
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn],
            [
                InlineKeyboardButton(
                    text="💳 Подписка и тарифы",
                    callback_data="menu_subscription",
                ),
                InlineKeyboardButton(
                    text="❓ Как это работает",
                    callback_data="menu_help",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Поддержка",
                    url="https://t.me/t1mocka",
                ),
            ],
        ]
    )


def get_job_card_keyboard(card_id: int, post_url: str = "") -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Отправить отклик",
                callback_data=f"approve:{card_id}",
            ),
            InlineKeyboardButton(
                text="✍️ Переписать отклик",
                callback_data=f"rewrite:{card_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔄 Перегенерировать",
                callback_data=f"regen:{card_id}",
            ),
        ],
    ]
    if post_url and (post_url.startswith("http://") or post_url.startswith("https://")):
        keyboard.append([
            InlineKeyboardButton(
                text="🔗 Перейти к вакансии",
                url=post_url,
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def send_job_card_to_user(bot: Bot, card: JobCardDTO) -> Message | None:
    escaped_post_text = html.escape(card.post_text)
    channel_name = html.escape(card.channel_title or card.channel_username)

    text = (
        f"🎯 <b>ВАКАНСИЯ #{card.id}</b>\n"
        f"📢 <b>Канал:</b> {channel_name}\n\n"
        f"📌 <b>Объявление:</b>\n"
        f"<blockquote expandable>{escaped_post_text}</blockquote>\n\n"
    )

    if card.draft_reply:
        escaped_draft = html.escape(card.draft_reply)
        text += f"✍️ <b>Готовый отклик (нажмите, чтобы скопировать):</b>\n<code>{escaped_draft}</code>\n\n"

    if card.matched_keywords:
        kw_str = html.escape(", ".join(card.matched_keywords))
        text += f"💡 <b>Ключевые совпадения:</b> {kw_str}\n"

    kb = get_job_card_keyboard(card.id, card.post_url)
    try:
        msg = await bot.send_message(
            chat_id=card.user_id,
            text=text.strip(),
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        return msg
    except Exception as exc:
        log.error("Error sending job card %s to user %s: %s", card.id, card.user_id, exc)
        return None


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not message.from_user:
        return
    tg_user = {
        "id": message.from_user.id,
        "first_name": message.from_user.first_name,
        "username": message.from_user.username,
    }
    if repo._conn is None:
        await repo.open()
    profile, is_new = await repo.get_or_create_user(tg_user)
    sub = await repo.get_subscription_status(profile.user_id)

    status_text = "Включили бесплатный PRO-доступ на 2 дня." if is_new else f"Статус: <b>{sub.status.upper()}</b> (осталось дней: {sub.days_left})"

    welcome_msg = (
        f"<b>Здравствуйте, {message.from_user.first_name}!</b>\n\n"
        f"Vacancy Spotter ищет заказы для фрилансеров в Telegram-каналах и готовит точные отклики.\n\n"
        f"📌 {status_text}\n\n"
        f"<b>Как начать работу:</b>\n"
        f"1. Нажмите <b>«📱 Открыть личный кабинет»</b> ниже.\n"
        f"2. Выберите профессию и укажите стоп-слова.\n"
        f"3. Загрузите резюме в PDF или опишите навыки.\n"
        f"4. Добавьте ссылки на проекты в портфолио.\n\n"
        f"После настройки бот начнёт присылать вам готовые карточки откликов."
    )
    try:
        await message.answer(welcome_msg, parse_mode=ParseMode.HTML, reply_markup=get_welcome_keyboard())
    except Exception as exc:
        log.error("Error sending welcome message: %s", exc)
        await message.answer(welcome_msg, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "menu_subscription")
async def process_menu_subscription(query: CallbackQuery) -> None:
    await query.answer()
    if not query.from_user:
        return
    if repo._conn is None:
        await repo.open()

    user_id = query.from_user.id
    sub = await repo.get_subscription_status(user_id)

    status_str = "Активна" if sub.is_valid and sub.status == "active" else ("Демо-доступ (2 дня)" if sub.is_valid else "Истёк")
    until_str = sub.subscription_until.strftime("%d.%m.%Y %H:%M") if sub.subscription_until else (sub.demo_until.strftime("%d.%m.%Y %H:%M") if sub.demo_until else "Не активирована")

    text = (
        f"💳 <b>Статус подписки:</b>\n\n"
        f"• Доступ: <b>{status_str}</b>\n"
        f"• Осталось дней: <b>{sub.days_left}</b>\n"
        f"• Действует до: <b>{until_str} UTC</b>\n\n"
        f"<b>Тарифы:</b>\n"
        f"• <b>7 дней</b>: 300 ₽\n"
        f"• <b>30 дней</b>: 600 ₽ (выгодно)\n\n"
        f"<i>Чтобы продлить доступ, откройте личный кабинет:</i>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Открыть личный кабинет",
                    web_app=WebAppInfo(url=DEFAULT_WEBAPP_URL),
                )
            ]
        ]
    )
    if query.message and hasattr(query.message, "answer"):
        await query.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(F.data == "menu_help")
async def process_menu_help(query: CallbackQuery) -> None:
    await query.answer()
    help_text = (
        "<b>Как работает Vacancy Spotter:</b>\n\n"
        "1. <b>Настройка профиля:</b> откройте личный кабинет, выберите профессию и укажите стоп-слова.\n\n"
        "2. <b>Загрузка резюме:</b> нажмите «Извлечь из PDF» — бот сам прочитает ваш опыт.\n\n"
        "3. <b>Проекты в портфолио:</b> прикрепите ссылки на проекты, чтобы нейросеть прикладывала их к отклику.\n\n"
        "4. <b>Отправка откликов:</b> когда появится подходящая вакансия, нажмите «Отправить отклик»."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Открыть личный кабинет",
                    web_app=WebAppInfo(url=DEFAULT_WEBAPP_URL),
                )
            ]
        ]
    )
    if query.message and hasattr(query.message, "answer"):
        await query.message.answer(help_text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.message(Command("stats"))
@router.message(F.text.lower().in_(["stats", "статистика", "стат"]))
async def cmd_stats(message: Message) -> None:
    if not message.from_user:
        return
    if repo._conn is None:
        await repo.open()
    sub = await repo.get_subscription_status(message.from_user.id)
    msg = (
        f"📊 <b>Ваш статус доступа:</b>\n\n"
        f"• Подписка: <b>{sub.status.upper()}</b>\n"
        f"• Осталось дней: <b>{sub.days_left}</b>\n"
        f"• Доступ активен: {'Да' if sub.is_valid else 'Истёк'}\n\n"
        f"<i>Продлить подписку можно в личном кабинете.</i>"
    )
    await message.answer(msg, parse_mode=ParseMode.HTML)


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_telegram_ids


@router.message(Command("debug"))
async def cmd_debug(message: Message) -> None:
    """Admin-only: show system diagnostics."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    bot = get_bot()
    try:
        bot_info = await bot.get_me()
        bot_name = f"@{bot_info.username}" if bot_info.username else "unknown"
        bot_id = str(bot_info.id) if bot_info else "?"
    except Exception:
        bot_name = "error"
        bot_id = "?"

    token_pfx = settings.bot_token.get_secret_value()[:10] + "..."

    # Parser stats (imported lazily to avoid circular imports)
    try:
        from telethon_parser import parser_stats
        parser_section = (
            f"📡 <b>Telethon Parser:</b>\n"
            f"  • Статус: {'🟢 Работает' if parser_stats.is_running else '🔴 Не запущен'}\n"
            f"  • Старт: <code>{parser_stats.started_at or 'N/A'}</code>\n"
            f"  • Последняя активность: <code>{parser_stats.last_activity_at or 'Нет'}</code>\n"
            f"  • Последний канал: {parser_stats.last_channel or 'N/A'}\n"
            f"  • Сообщений увидено: <b>{parser_stats.messages_seen}</b>\n"
            f"  • Совпадений по ключевым: <b>{parser_stats.keywords_matched}</b>\n"
            f"  • Карточек отправлено: <b>{parser_stats.cards_sent}</b>\n"
            f"  • Ошибок отправки: <b>{parser_stats.cards_failed}</b>\n"
        )
        if parser_stats.recent_trace_ids:
            traces_str = ", ".join(f"<code>{t}</code>" for t in parser_stats.recent_trace_ids[:5])
            parser_section += f"  • Последние trace_id: {traces_str}\n"
    except Exception as exc:
        parser_section = f"📡 <b>Telethon Parser:</b> ⚠️ Не удалось получить статус ({exc})\n"

    # Recent trace events from DB
    trace_section = ""
    try:
        if repo._conn is None:
            await repo.open()
        recent = await repo.get_recent_traces(limit=5)
        if recent:
            trace_section = "\n📜 <b>Последние 5 trace-событий:</b>\n"
            for t in recent:
                ts = t["created_at"][:19] if t.get("created_at") else "?"
                trace_section += (
                    f"  <code>[{t['trace_id']}]</code> {t['event']}"
                    f" | {t.get('channel', '')} | card={t.get('card_id', '-')}"
                    f" | {ts}\n"
                )
        else:
            trace_section = "\n📜 <i>Нет trace-событий в БД.</i>\n"
    except Exception:
        trace_section = "\n📜 <i>Ошибка чтения trace из БД.</i>\n"

    text = (
        f"🔧 <b>DIAGNOSTIC DEBUG</b>\n\n"
        f"🤖 <b>Бот:</b>\n"
        f"  • Username: <b>{bot_name}</b>\n"
        f"  • Bot ID: <code>{bot_id}</code>\n"
        f"  • Token: <code>{token_pfx}</code>\n\n"
        f"{parser_section}\n"
        f"{trace_section}\n"
        f"<i>Используйте /trace &lt;url или card_id&gt; для поиска конкретного поста.</i>"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("trace"))
async def cmd_trace(message: Message) -> None:
    """Admin-only: trace a specific post through the pipeline."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "🔍 <b>Использование:</b>\n\n"
            "<code>/trace https://t.me/channel/123</code> — по URL поста\n"
            "<code>/trace 42</code> — по ID карточки\n"
            "<code>/trace a1b2c3d4</code> — по trace_id\n"
            "<code>/trace last</code> — последние 10 событий",
            parse_mode=ParseMode.HTML,
        )
        return

    query = args[1].strip()

    if repo._conn is None:
        await repo.open()

    traces: list[dict] = []

    if query.lower() == "last":
        traces = await repo.get_recent_traces(limit=10)
        header = "📜 <b>Последние 10 событий:</b>"
    elif query.isdigit():
        card_id = int(query)
        traces = await repo.get_traces_by_card_id(card_id)
        if not traces:
            # Try as trace_id
            traces = await repo.get_traces_by_trace_id(query)
        header = f"📜 <b>Trace для card_id={card_id}:</b>"
    elif len(query) == 8 and all(c in "0123456789abcdef" for c in query):
        traces = await repo.get_traces_by_trace_id(query)
        header = f"📜 <b>Trace для ID {query}:</b>"
    else:
        traces = await repo.get_traces_by_url(query)
        header = f"📜 <b>Trace для URL содержащий:</b> <code>{html.escape(query[:50])}</code>"

    if not traces:
        await message.answer(
            f"🔍 Ничего не найдено по запросу: <code>{html.escape(query[:80])}</code>\n\n"
            "<i>Возможные причины:\n"
            "• Пост не проходил через парсер\n"
            "• Ключевые слова не совпали\n"
            "• Записи были очищены (хранятся последние 500)</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [header, ""]
    for t in traces:
        ts = t["created_at"][:19] if t.get("created_at") else "?"
        event_icon = {
            "received": "📥", "users_matched": "👤", "no_subscribers": "🚫",
            "stop_word_filtered": "⛔", "card_created": "📋",
            "card_sent": "✅", "card_send_failed": "⚠️",
            "card_send_error": "❌", "pipeline_error": "💥",
        }.get(t["event"], "•")

        line = f"{event_icon} <code>[{t['trace_id']}]</code> <b>{t['event']}</b>"
        if t.get("channel"):
            line += f" | {t['channel']}"
        if t.get("user_id"):
            line += f" | user={t['user_id']}"
        if t.get("card_id"):
            line += f" | card=#{t['card_id']}"
        if t.get("bot_username"):
            line += f" | bot={t['bot_username']}"
        if t.get("bot_token_prefix"):
            line += f" | token={t['bot_token_prefix']}..."
        line += f"\n  ⏰ {ts}"
        if t.get("detail"):
            detail = html.escape(t["detail"][:120])
            line += f"\n  💬 {detail}"
        if t.get("post_snippet"):
            snippet = html.escape(t["post_snippet"][:80])
            line += f"\n  📝 {snippet}..."
        lines.append(line)
        lines.append("")

    text = "\n".join(lines)
    # Telegram message limit is 4096 chars
    if len(text) > 4000:
        text = text[:4000] + "\n\n<i>... обрезано (слишком длинный ответ)</i>"
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("approve:"))
async def process_approve_job_card(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    parts = query.data.split(":", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return
    card_id = int(parts[1])
    user_id = query.from_user.id

    if repo._conn is None:
        await repo.open()

    updated = await repo.update_job_card_status(card_id, user_id, JobCardStatusEnum.APPLIED)
    if updated:
        await query.answer("Отклик одобрен и отправлен.", show_alert=True)
        if query.message and hasattr(query.message, "edit_reply_markup"):
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
    else:
        await query.answer("Карточка вакансии не найдена", show_alert=True)


@router.callback_query(F.data.startswith("rewrite:"))
async def process_rewrite_job_card(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    card_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    if repo._conn is None:
        await repo.open()

    card = await repo.get_job_card_by_id(card_id, user_id)
    if not card:
        await query.answer("Карточка не найдена", show_alert=True)
        return

    profile = await repo.get_user_profile(user_id)
    USER_REGEN_WAITING[user_id] = card_id

    draft = card.draft_reply
    if not draft or not draft.strip():
        draft = await generate_draft_reply(profile, card.post_text)

    await query.answer()

    if query.message and hasattr(query.message, "answer"):
        escaped_draft = html.escape(draft)
        await query.message.answer(
            f"📋 <b>Текущий отклик на вакансию #{card_id}:</b>\n\n"
            f"<code>{escaped_draft}</code>\n\n"
            f"✏️ <b>Напишите в ответ ваши пожелания к отклику, чтобы ИИ перегенерировал его:</b>",
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data.startswith("regen:"))
async def process_regen_job_card(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    card_id = int(query.data.split(":", 1)[1])
    user_id = query.from_user.id

    USER_REGEN_WAITING[user_id] = card_id

    await query.answer()

    if query.message and hasattr(query.message, "answer"):
        await query.message.answer(
            f"✏️ <b>Напишите ваши пожелания к отклику на вакансию #{card_id}:</b>\n\n"
            f"<i>(Например: «Сделай тон более официальным» или «Укажи, что готов начать сегодня»)</i>",
            parse_mode=ParseMode.HTML,
        )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_text_message(message: Message) -> None:
    if not message.from_user:
        return
    user_id = message.from_user.id
    if user_id in USER_REGEN_WAITING:
        card_id = USER_REGEN_WAITING.pop(user_id)
        user_instruction = (message.text or "").strip()

        try:
            if repo._conn is None:
                await repo.open()

            card = await repo.get_job_card_by_id(card_id, user_id)
            profile = await repo.get_user_profile(user_id)

            if card and profile:
                new_draft = await generate_draft_reply(profile, card.post_text, custom_instruction=user_instruction)
                await repo.update_job_card_draft(card_id, user_id, new_draft)
                card.draft_reply = new_draft

                escaped_instr = html.escape(user_instruction)
                escaped_draft = html.escape(new_draft)

                msg = (
                    f"✨ <b>Перегенерированный отклик (Вакансия #{card_id}):</b>\n\n"
                    f"💡 <i>Пожелание: {escaped_instr}</i>\n\n"
                    f"<code>{escaped_draft}</code>"
                )
                kb = get_job_card_keyboard(card_id, card.post_url)
                await message.answer(msg, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await message.answer("Не удалось найти вакансию для перегенерации.")
        except Exception as exc:
            log.error("Error regenerating job card draft for user %s, card %s: %s", user_id, card_id, exc)
            await message.answer(f"⚠️ Ошибка при перегенерации отклика: {exc}")


@router.callback_query(F.data.startswith("skip:"))
async def process_skip_job_card(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    parts = query.data.split(":", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return
    card_id = int(parts[1])
    user_id = query.from_user.id

    if repo._conn is None:
        await repo.open()

    updated = await repo.update_job_card_status(card_id, user_id, JobCardStatusEnum.REJECTED)
    if updated:
        await query.answer("Пропустили вакансию", show_alert=False)
        if query.message and hasattr(query.message, "edit_reply_markup"):
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
    else:
        await query.answer("Карточка вакансии не найдена", show_alert=True)


@router.callback_query(F.data.startswith("admin_approve:"))
async def handle_admin_approve_subscription(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    parts = query.data.split(":")
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await query.answer("Ошибка данных", show_alert=True)
        return

    target_user_id = int(parts[1])
    days = int(parts[2])

    if repo._conn is None:
        await repo.open()

    sub_status = await repo.extend_user_subscription(target_user_id, days)

    await query.answer("Подписка продлена!", show_alert=True)

    if query.message and hasattr(query.message, "edit_text"):
        try:
            until_str = sub_status.subscription_until.strftime("%d.%m.%Y %H:%M") if sub_status.subscription_until else "N/A"
            await query.message.edit_text(
                f"{query.message.text}\n\n✅ <b>ОДОБРЕНО!</b> Начислено {days} дней. Подписка активна до {until_str} UTC.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    bot = get_bot()
    congratulations_text = (
        f"🎉 <b>Ваша подписка успешно продлена!</b>\n\n"
        f"➕ Начислено: <b>{days} дней</b> доступа.\n"
        f"📅 Подписка активна до: <b>{sub_status.subscription_until.strftime('%d.%m.%Y %H:%M') if sub_status.subscription_until else 'N/A'} UTC</b>\n\n"
        f"🚀 Бот продолжает мониторить каналы и отправлять вам лучшие вакансии!"
    )
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=congratulations_text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.error("Error sending congratulatory message to user %s: %s", target_user_id, exc)


@router.callback_query(F.data.startswith("admin_reject:"))
async def handle_admin_reject_subscription(query: CallbackQuery) -> None:
    if not query.from_user or not query.data:
        return
    parts = query.data.split(":")
    if len(parts) < 2 or not parts[1].isdigit():
        await query.answer("Ошибка данных", show_alert=True)
        return

    target_user_id = int(parts[1])

    await query.answer("Запрос отклонён", show_alert=True)

    if query.message and hasattr(query.message, "edit_text"):
        try:
            await query.message.edit_text(
                f"{query.message.text}\n\n❌ <b>ОТКЛОНЕНО.</b> Платеж не подтверждён.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    bot = get_bot()
    reject_text = (
        "⚠️ <b>Ваш платеж не был подтверждён администратором.</b>\n\n"
        "Пожалуйста, проверьте правильность перевода или прикрепите корректный чек/номер транзакции."
    )
    try:
        await bot.send_message(chat_id=target_user_id, text=reject_text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        log.error("Error sending rejection message to user %s: %s", target_user_id, exc)


async def start_bot_polling() -> tuple[Bot, Dispatcher]:
    token = settings.bot_token.get_secret_value()
    bot = get_bot()
    dp = Dispatcher()
    dp.include_router(router)
    await repo.open()
    return bot, dp


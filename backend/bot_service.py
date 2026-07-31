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
    PreCheckoutQuery,
    LabeledPrice,
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

    draft = card.draft_reply
    if not draft or not draft.strip():
        profile = await repo.get_user_profile(user_id)
        draft = generate_draft_reply(profile, card.post_text)

    await query.answer("Текст отправлен ниже. Нажмите на него для копирования.", show_alert=False)

    if query.message and hasattr(query.message, "answer"):
        await query.message.answer(
            f"📋 <b>Ваш отклик (нажмите на текст, чтобы скопировать):</b>\n\n<code>{draft}</code>",
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
        user_instruction = message.text.strip()

        if repo._conn is None:
            await repo.open()

        card = await repo.get_job_card_by_id(card_id, user_id)
        profile = await repo.get_user_profile(user_id)

        if card and profile:
            new_draft = generate_draft_reply(profile, card.post_text, custom_instruction=user_instruction)
            await repo.update_job_card_draft(card_id, user_id, new_draft)
            card.draft_reply = new_draft

            msg = (
                f"✨ <b>Перегенерированный отклик (Вакансия #{card_id}):</b>\n\n"
                f"💡 <i>Пожелание: {user_instruction}</i>\n\n"
                f"<code>{new_draft}</code>"
            )
            kb = get_job_card_keyboard(card_id, card.post_url)
            await message.answer(msg, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await message.answer("Не удалось найти вакансию для перегенерации.")


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


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery) -> None:
    """Handle Telegram Stars pre-checkout validation."""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message) -> None:
    """Handle successful Telegram Stars payment."""
    if not message.from_user or not message.successful_payment:
        return

    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id

    days = 30 if ("month" in payload or "30" in payload) else 7

    if repo._conn is None:
        await repo.open()

    sub_status = await repo.extend_user_subscription(user_id, days)

    congratulations_text = (
        f"🎉 <b>Спасибо за оплату Telegram Stars!</b>\n\n"
        f"➕ Подписка продлена на <b>{days} дней</b>.\n"
        f"📅 Активна до: <b>{sub_status.subscription_until.strftime('%d.%m.%Y %H:%M') if sub_status.subscription_until else 'N/A'} UTC</b>\n\n"
        f"🚀 Наслаждайтесь авто-поиском заказов!"
    )
    await message.answer(congratulations_text, parse_mode=ParseMode.HTML)


async def send_stars_invoice(bot: Bot, chat_id: int, plan: str = "week") -> Message | None:
    """Send Telegram Stars payment invoice to user."""
    days = 7 if plan == "week" else 30
    stars_amount = 150 if plan == "week" else 300
    title = f"Подписка Vacancy Spotter ({days} дней)"
    description = f"Доступ к авто-поиску вакансий на {days} дней"
    payload = f"stars_sub_{plan}_{days}d"
    currency = "XTR"
    prices = [LabeledPrice(label=f"Подписка {days} дней", amount=stars_amount)]

    try:
        return await bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            currency=currency,
            prices=prices,
        )
    except Exception as exc:
        log.error("Failed to send stars invoice: %s", exc)
        return None


async def start_bot_polling() -> tuple[Bot, Dispatcher]:
    token = settings.bot_token.get_secret_value()
    bot = get_bot()
    dp = Dispatcher()
    dp.include_router(router)
    await repo.open()
    return bot, dp


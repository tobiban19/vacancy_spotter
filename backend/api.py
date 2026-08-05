"""
FastAPI REST API Server for Vacancy Spotter SaaS Telegram Mini App.
"""

import os
import base64
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from typing import Annotated, Literal
import jwt
import io
import logging
import pypdf
from pathlib import Path
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Header, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from aiogram.enums import ParseMode

import bot_service
from auth import verify_telegram_init_data
from config import settings
from database import DatabaseRepository
from models import (
    AdminBanUpdateDTO,
    AdminStatsDTO,
    AdminSubscriptionUpdateDTO,
    AdminUserDetailDTO,
    AdminUserDTO,
    ChannelCustomAddDTO,
    ChannelDTO,
    InitDataAuthRequest,
    JobCardCreateDTO,
    JobCardDTO,
    JobCardStatusEnum,
    PortfolioItemCreateDTO,
    PortfolioItemDTO,
    ProfessionDTO,
    SubscriptionStatusDTO,
    TokenResponse,
    UserProfileDTO,
    UserProfileUpdateDTO,
)

repo = DatabaseRepository(settings.database_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await repo.open()
    yield
    await repo.close()


app = FastAPI(
    title="Vacancy Spotter SaaS API",
    description="Multi-tenant REST API for Telegram Mini App",
    version="1.0.0",
    lifespan=lifespan,
)


def _add_cors_middleware(application: FastAPI) -> None:
    """Attach CORS middleware once, using a configured origin whitelist.

    Defaults to "*" (permissive) ONLY when CORS_ORIGINS is unset, so local
    development keeps working. In production, set CORS_ORIGINS to the
    comma-separated Mini App domains (e.g. the Vercel URL + backend origin).
    """
    if any(getattr(m, "cls", None) == CORSMiddleware for m in application.user_middleware):
        return
    origins = settings.cors_origins_list
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins is not None else ["*"],
        allow_credentials=origins is not None,
        allow_methods=["*"],
        allow_headers=["*"],
    )


_add_cors_middleware(app)

dist_dir = Path(__file__).parent.parent / "frontend" / "dist"
if dist_dir.exists():
    @app.get("/app", include_in_schema=False)
    async def serve_mini_app():
        return FileResponse(dist_dir / "index.html")



# ---------------------------------------------------------------------------
# Auth Dependency & Helper
# ---------------------------------------------------------------------------

def create_jwt_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def _decode_bearer_token(token: str) -> int | None:
    """Resolve a user id from a JWT or a valid Telegram initData signature.

    Previously this accepted a `dev_mode_<id>` fallback that let anyone become
    any user (including admins) without a valid signature — that backdoor is
    removed. Only cryptographically valid JWTs and Telegram initData are honored.
    """
    # 1. JWT
    try:
        payload = jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"])
        return int(payload["sub"])
    except Exception:
        pass

    # 2. Telegram initData (validates HMAC-SHA256 against the bot token)
    tg_user = repo.verify_telegram_init_data(token)
    if tg_user and isinstance(tg_user, dict) and tg_user.get("id"):
        return int(tg_user["id"])
    return None


async def _require_user_id(authorization: Annotated[str | None, Header()] = None) -> int:
    """Shared auth resolver used by both regular and admin dependencies."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = authorization.split(" ", 1)[1]
    user_id = _decode_bearer_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )

    if await repo.is_user_banned(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ваш аккаунт заблокирован администратором.",
        )

    return user_id


async def get_current_user_id(authorization: Annotated[str | None, Header()] = None) -> int:
    return await _require_user_id(authorization)


async def get_admin_user_id(authorization: Annotated[str | None, Header()] = None) -> int:
    user_id = await _require_user_id(authorization)
    admin_ids = settings.admin_telegram_ids
    if admin_ids and user_id not in admin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Admin privileges required",
        )
    return user_id



# ---------------------------------------------------------------------------
# Auth Router & Endpoints
# ---------------------------------------------------------------------------

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/verify")
async def verify_auth(req: InitDataAuthRequest):
    """Verify Telegram Mini App initData string with HMAC SHA256."""
    verified = verify_telegram_init_data(req.init_data, settings.bot_token.get_secret_value())
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Telegram initData signature",
        )
    return {"valid": True, "data": verified}


app.include_router(auth_router)


@app.post("/api/auth/tma", response_model=TokenResponse)
async def auth_tma(req: InitDataAuthRequest):
    """Authenticate via Telegram Mini App initData string."""
    tg_user = repo.verify_telegram_init_data(req.init_data)
    if not tg_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Telegram initData signature",
        )

    profile, is_new = await repo.get_or_create_user(tg_user)
    token = create_jwt_token(profile.user_id)
    return TokenResponse(
        access_token=token,
        user_id=profile.user_id,
        first_name=profile.first_name,
        is_new_user=is_new,
    )


# ---------------------------------------------------------------------------
# User Profile Endpoints
# ---------------------------------------------------------------------------

profile_router = APIRouter(prefix="/api/profile", tags=["profile"])


@profile_router.get("", response_model=UserProfileDTO)
async def get_profile(user_id: Annotated[int, Depends(get_current_user_id)]):
    tg_user = {"id": user_id, "first_name": "User"}
    profile, _ = await repo.get_or_create_user(tg_user)
    return profile


@profile_router.put("", response_model=UserProfileDTO)
async def update_profile(
    dto: UserProfileUpdateDTO,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    return await repo.update_user_profile(user_id, dto)


@profile_router.post("/parse_pdf")
async def parse_resume_pdf(
    file: UploadFile = File(...),
    user_id: Annotated[int, Depends(get_current_user_id)] = None,
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Только файлы формата PDF")
    
    content = await file.read()
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        text_pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)
        extracted_text = "\n".join(text_pages).strip()
        if not extracted_text:
            raise HTTPException(status_code=400, detail="Не удалось извлечь текст из PDF. Возможно, это скан-изображение.")
        
        cleaned = "\n".join([line.strip() for line in extracted_text.splitlines() if line.strip()])
        return {"extracted_text": cleaned[:2000]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения PDF: {str(e)}")


app.include_router(profile_router)


# ---------------------------------------------------------------------------
# Portfolio Endpoints
# ---------------------------------------------------------------------------

portfolio_router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@portfolio_router.get("", response_model=list[PortfolioItemDTO])
async def get_portfolio(user_id: Annotated[int, Depends(get_current_user_id)]):
    return await repo.get_portfolio(user_id)


@portfolio_router.post("", response_model=PortfolioItemDTO)
async def add_portfolio_item(
    dto: PortfolioItemCreateDTO,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    return await repo.add_portfolio_item(user_id, dto)


@portfolio_router.put("/{item_id}", response_model=PortfolioItemDTO)
async def update_portfolio_item(
    item_id: int,
    dto: PortfolioItemCreateDTO,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    updated = await repo.update_portfolio_item(user_id, item_id, dto)
    if not updated:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    return updated


@portfolio_router.delete("/{item_id}")
async def delete_portfolio_item(
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    deleted = await repo.delete_portfolio_item(user_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    return {"status": "success", "deleted_id": item_id}


app.include_router(portfolio_router)


# ---------------------------------------------------------------------------
# Professions & Channels Endpoints
# ---------------------------------------------------------------------------

channels_router = APIRouter(prefix="/api/channels", tags=["channels"])


@channels_router.get("", response_model=list[ChannelDTO])
async def get_channels(user_id: Annotated[int, Depends(get_current_user_id)]):
    tg_user = {"id": user_id, "first_name": "User"}
    profile, _ = await repo.get_or_create_user(tg_user)
    return await repo.get_user_channels(user_id, profile.profession_id)


class ToggleChannelDTO(BaseModel):
    channel_id: int
    is_enabled: bool


@channels_router.post("/toggle")
async def toggle_channel(
    dto: ToggleChannelDTO,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    await repo.toggle_user_channel(user_id, dto.channel_id, dto.is_enabled)
    return {"status": "success", "channel_id": dto.channel_id, "is_enabled": dto.is_enabled}


@channels_router.post("/custom", response_model=ChannelDTO)
async def add_custom_channel(
    dto: ChannelCustomAddDTO,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    tg_user = {"id": user_id, "first_name": "User"}
    profile, _ = await repo.get_or_create_user(tg_user)
    return await repo.add_custom_channel(user_id, profile.profession_id, dto.username_or_link)


app.include_router(channels_router)


professions_router = APIRouter(prefix="/api/professions", tags=["professions"])


@professions_router.get("", response_model=list[ProfessionDTO])
async def get_professions():
    return await repo.get_professions()


app.include_router(professions_router)


subscription_router = APIRouter(prefix="/api/subscription", tags=["subscription"])


class SubscriptionRequestCardDTO(BaseModel):
    plan: Literal["week", "month"]
    receipt_info: str = ""
    receipt_file_b64: str | None = None
    receipt_filename: str | None = None


@subscription_router.get("", response_model=SubscriptionStatusDTO)
async def get_subscription(user_id: Annotated[int, Depends(get_current_user_id)]):
    return await repo.get_subscription_status(user_id)


@subscription_router.post("/request_card")
async def request_subscription_card(
    dto: SubscriptionRequestCardDTO,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    if dto.plan not in ("week", "month"):
        raise HTTPException(status_code=400, detail="Invalid subscription plan")

    days = 7 if dto.plan == "week" else 30
    profile, _ = await repo.get_or_create_user({"id": user_id, "first_name": "User"})

    bot = bot_service.get_bot()
    admin_id = getattr(settings, "admin_chat_id", 965000782)

    plan_label = "Неделя (7 дней - 300₽)" if dto.plan == "week" else "Месяц (30 дней - 600₽)"
    user_info = f"{profile.first_name}"
    if profile.username:
        user_info += f" (@{profile.username})"
    user_info += f" [ID: <code>{user_id}</code>]"

    receipt_display = dto.receipt_info.strip() if dto.receipt_info else "<i>Текстовое описание не указано</i>"
    if dto.receipt_filename:
        receipt_display += f"\n📎 <b>Файл чека:</b> {dto.receipt_filename}"

    text = (
        f"💳 <b>Запрос на продление подписки!</b>\n\n"
        f"👤 <b>Пользователь:</b> {user_info}\n"
        f"📦 <b>Тариф:</b> {plan_label}\n"
        f"🧾 <b>Чек / Данные перевода:</b>\n{receipt_display}\n\n"
        f"Нажмите кнопку ниже для подтверждения или отклонения:"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Одобрить {days} дней",
                    callback_data=f"admin_approve:{user_id}:{days}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить запрос",
                    callback_data=f"admin_reject:{user_id}",
                )
            ],
        ]
    )

    receipt_file = None
    if dto.receipt_file_b64 and dto.receipt_filename:
        try:
            b64_data = dto.receipt_file_b64
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            file_bytes = base64.b64decode(b64_data)
            receipt_file = BufferedInputFile(file_bytes, filename=dto.receipt_filename)
        except Exception as exc:
            logging.getLogger("fastapi").error("Failed to decode receipt_file_b64: %s", exc)

    try:
        if receipt_file and dto.receipt_filename:
            fn_lower = dto.receipt_filename.lower()
            is_image = any(fn_lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"))
            if is_image:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=receipt_file,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            else:
                await bot.send_document(
                    chat_id=admin_id,
                    document=receipt_file,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
        else:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
    except Exception as exc:
        logging.getLogger("fastapi").error("Failed to send admin subscription alert: %s", exc)

    return {
        "status": "success",
        "message": "Subscription card request sent to admin",
        "user_id": user_id,
        "plan": dto.plan,
        "days": days,
    }


app.include_router(subscription_router)


# ---------------------------------------------------------------------------
# Jobs Ingest & Interactive Cards Endpoints
# ---------------------------------------------------------------------------

class IncomingJobDTO(BaseModel):
    channel_username: str
    post_text: str
    post_url: str = ""
    channel_title: str = ""


jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@jobs_router.post("/incoming")
async def process_incoming_job(
    req: IncomingJobDTO,
    x_webhook_secret: Annotated[str | None, Header()] = None,
):
    """
    Ingest endpoint for incoming Telegram channel posts/jobs.
    Matches subscribed users, checks stop-words, creates user_job_cards, and sends Telegram cards.

    Protected: when JOBS_WEBHOOK_SECRET is configured, callers MUST pass the
    matching `X-Webhook-Secret` header. This prevents anonymous abuse of the
    endpoint to spam users with arbitrary job cards.
    """
    expected = settings.jobs_webhook_secret.get_secret_value()
    if expected and x_webhook_secret != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    users = await repo.get_users_subscribed_to_channel(req.channel_username)
    created_cards = []
    
    bot = bot_service.get_bot()

    for u in users:
        # Check stop words filter (case-insensitive)
        post_lower = req.post_text.lower()
        if any(sw.strip() and sw.strip().lower() in post_lower for sw in u.stop_words if sw):
            continue

        clean_ch = req.channel_username.strip().replace("https://t.me/", "").replace("@", "")
        ch_title = req.channel_title or f"@{clean_ch}"

        card_create = JobCardCreateDTO(
            user_id=u.user_id,
            channel_title=ch_title,
            channel_username=clean_ch,
            post_text=req.post_text,
            post_url=req.post_url,
            status=JobCardStatusEnum.NEW,
            match_score=1.0,
        )
        card = await repo.create_job_card(card_create)
        created_cards.append(card)

        try:
            await bot_service.send_job_card_to_user(bot, card)
        except Exception:
            pass

    return {
        "status": "success",
        "users_matched": len(users),
        "cards_created": len(created_cards),
        "card_ids": [c.id for c in created_cards],
    }


# ---------------------------------------------------------------------------
# Job Cards Router (vacancies & draft replies in the Mini App)
# ---------------------------------------------------------------------------

from matching_service import generate_draft_reply

cards_router = APIRouter(prefix="/api/cards", tags=["cards"])


class JobCardStatusUpdateDTO(BaseModel):
    status: JobCardStatusEnum


@cards_router.get("", response_model=list[JobCardDTO])
async def list_user_cards(
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user_id: int = Depends(get_current_user_id),
):
    """List the current user's job cards, optionally filtered by status."""
    return await repo.get_user_job_cards(user_id, status=status_filter, limit=limit, offset=offset)


@cards_router.put("/{card_id}/status", response_model=JobCardDTO)
async def update_card_status(
    card_id: int,
    dto: JobCardStatusUpdateDTO,
    user_id: int = Depends(get_current_user_id),
):
    """Update a job card status (new / saved / applied / rejected / hidden)."""
    updated = await repo.update_job_card_status(card_id, user_id, dto.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Job card not found")
    return updated


class JobCardRegenDTO(BaseModel):
    custom_instruction: str = ""


@cards_router.post("/{card_id}/regenerate", response_model=JobCardDTO)
async def regenerate_card_draft(
    card_id: int,
    dto: JobCardRegenDTO,
    user_id: int = Depends(get_current_user_id),
):
    """Regenerate the draft reply for a job card using the user's profile and an
    optional custom instruction (e.g. "make the tone more formal")."""
    card = await repo.get_job_card_by_id(card_id, user_id)
    if not card:
        raise HTTPException(status_code=404, detail="Job card not found")

    profile = await repo.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    new_draft = await generate_draft_reply(profile, card.post_text, custom_instruction=dto.custom_instruction)
    updated = await repo.update_job_card_draft(card_id, user_id, new_draft)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update draft")
    return updated


app.include_router(cards_router)


# ---------------------------------------------------------------------------
# Admin & User Management Router
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


@admin_router.get("/check")
async def check_admin_status(user_id: int = Depends(get_admin_user_id)):
    return {"is_admin": True, "user_id": user_id}


@admin_router.get("/stats", response_model=AdminStatsDTO)
async def get_admin_stats(user_id: int = Depends(get_admin_user_id)):
    return await repo.get_admin_stats()


@admin_router.get("/users")
async def get_admin_users(
    page: int = 1,
    limit: int = 20,
    search: str = "",
    status: str = "all",
    user_id: int = Depends(get_admin_user_id),
):
    users, total = await repo.get_admin_users_list(page=page, limit=limit, search=search, status_filter=status)
    return {
        "items": users,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 1,
    }


@admin_router.get("/users/{target_user_id}", response_model=AdminUserDetailDTO)
async def get_admin_user_details(
    target_user_id: int,
    user_id: int = Depends(get_admin_user_id),
):
    details = await repo.get_admin_user_details(target_user_id)
    if not details:
        raise HTTPException(status_code=404, detail="User not found")
    return details


@admin_router.post("/users/{target_user_id}/subscription", response_model=UserProfileDTO)
async def update_admin_user_subscription(
    target_user_id: int,
    req: AdminSubscriptionUpdateDTO,
    user_id: int = Depends(get_admin_user_id),
):
    updated = await repo.update_user_subscription(target_user_id, req)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@admin_router.post("/users/{target_user_id}/ban")
async def set_admin_user_ban(
    target_user_id: int,
    req: AdminBanUpdateDTO,
    user_id: int = Depends(get_admin_user_id),
):
    success = await repo.set_user_ban_status(target_user_id, req)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "is_banned": req.is_banned, "ban_reason": req.ban_reason}


app.include_router(admin_router)
app.include_router(jobs_router)

@app.middleware("http")
async def add_anti_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path in ["/app", "/app/", "/app/index.html"]:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

from fastapi.staticfiles import StaticFiles

dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(dist_dir):
    app.mount("/app", StaticFiles(directory=dist_dir, html=True), name="frontend_app")


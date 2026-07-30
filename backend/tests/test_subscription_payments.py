"""
Unit tests for Subscription Extension API, Manual Admin Approvals, and Telegram Stars Payments.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import api
import bot_service
from api import app, create_jwt_token
from database import DatabaseRepository


@pytest_asyncio.fixture
async def async_client(tmp_path):
    test_db = tmp_path / "test_sub_payments.sqlite3"
    test_repo = DatabaseRepository(test_db)
    await test_repo.open()

    original_repo = api.repo
    original_bot_repo = bot_service.repo

    api.repo = test_repo
    bot_service.repo = test_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    await test_repo.close()
    api.repo = original_repo
    bot_service.repo = original_bot_repo


@pytest.mark.asyncio
async def test_extend_user_subscription_db(tmp_path):
    test_db = tmp_path / "test_db_sub.sqlite3"
    repo = DatabaseRepository(test_db)
    await repo.open()

    user_id = 9001
    user_dict = {"id": user_id, "first_name": "ТестПодписка", "username": "test_sub"}

    # 1. Create initial user (1-day demo)
    profile, is_new = await repo.get_or_create_user(user_dict)
    assert profile.subscription_status == "demo"

    sub_initial = await repo.get_subscription_status(user_id)
    assert sub_initial.status == "demo"
    assert sub_initial.days_left == 2

    # 2. Extend subscription by 7 days
    sub_ext1 = await repo.extend_user_subscription(user_id, 7)
    assert sub_ext1.status == "active"
    assert sub_ext1.is_valid is True
    assert sub_ext1.subscription_until is not None
    assert sub_ext1.days_left >= 7

    until_1 = sub_ext1.subscription_until

    # 3. Extend subscription by 30 days more -> max(now, existing_until) + 30 days
    sub_ext2 = await repo.extend_user_subscription(user_id, 30)
    assert sub_ext2.status == "active"
    until_2 = sub_ext2.subscription_until
    assert until_2 is not None

    # Difference between until_2 and until_1 should be ~30 days
    days_diff = round((until_2 - until_1).total_seconds() / 86400)
    assert days_diff == 30

    await repo.close()


@pytest.mark.asyncio
async def test_post_subscription_request_card_api(async_client: AsyncClient):
    user_id = 9002
    token = create_jwt_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    mock_bot = AsyncMock()

    with patch.object(bot_service, "get_bot", return_value=mock_bot):
        # 1. Valid request "week"
        resp_week = await async_client.post(
            "/api/subscription/request_card",
            json={"plan": "week"},
            headers=headers,
        )
        assert resp_week.status_code == 200
        data_week = resp_week.json()
        assert data_week["status"] == "success"
        assert data_week["plan"] == "week"
        assert data_week["days"] == 7

        mock_bot.send_message.assert_called()
        call_args = mock_bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 965000782
        kb = call_args.kwargs["reply_markup"]
        assert any("admin_approve:9002:7" in str(btn.callback_data) for row in kb.inline_keyboard for btn in row)

        # 2. Valid request "month"
        mock_bot.reset_mock()
        resp_month = await async_client.post(
            "/api/subscription/request_card",
            json={"plan": "month"},
            headers=headers,
        )
        assert resp_month.status_code == 200
        data_month = resp_month.json()
        assert data_month["plan"] == "month"
        assert data_month["days"] == 30

        call_args_m = mock_bot.send_message.call_args
        kb_m = call_args_m.kwargs["reply_markup"]
        assert any("admin_approve:9002:30" in str(btn.callback_data) for row in kb_m.inline_keyboard for btn in row)

        # 3. Invalid plan
        resp_inv = await async_client.post(
            "/api/subscription/request_card",
            json={"plan": "year"},
            headers=headers,
        )
        assert resp_inv.status_code == 422 or resp_inv.status_code == 400


@pytest.mark.asyncio
async def test_admin_approve_callback_query(async_client: AsyncClient):
    target_user_id = 9003
    # Seed user in DB
    await api.repo.get_or_create_user({"id": target_user_id, "first_name": "АдминТест"})

    mock_query = AsyncMock()
    mock_query.from_user.id = 965000782
    mock_query.data = f"admin_approve:{target_user_id}:7"
    mock_query.message = AsyncMock()

    mock_bot = AsyncMock()

    with patch.object(bot_service, "get_bot", return_value=mock_bot):
        await bot_service.handle_admin_approve_subscription(mock_query)

        # Check callback answer
        mock_query.answer.assert_called_with("Подписка продлена!", show_alert=True)

        # Check DB update
        sub = await api.repo.get_subscription_status(target_user_id)
        assert sub.status == "active"
        assert sub.is_valid is True

        # Check congratulatory message to user
        mock_bot.send_message.assert_called_once()
        sent_call = mock_bot.send_message.call_args
        assert sent_call.kwargs["chat_id"] == target_user_id
        assert "успешно продлена" in sent_call.kwargs["text"]


@pytest.mark.asyncio
async def test_telegram_stars_handlers(async_client: AsyncClient):
    user_id = 9004
    await api.repo.get_or_create_user({"id": user_id, "first_name": "StarsUser"})

    # 1. PreCheckoutQuery
    mock_pre_checkout = AsyncMock()
    await bot_service.process_pre_checkout_query(mock_pre_checkout)
    mock_pre_checkout.answer.assert_called_with(ok=True)

    # 2. SuccessfulPayment
    mock_msg = AsyncMock()
    mock_msg.from_user.id = user_id
    mock_msg.successful_payment.invoice_payload = "stars_sub_month_30d"

    await bot_service.process_successful_payment(mock_msg)

    sub = await api.repo.get_subscription_status(user_id)
    assert sub.status == "active"
    assert sub.is_valid is True
    mock_msg.answer.assert_called_once()
    assert "Спасибо за оплату Telegram Stars!" in mock_msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_menu_subscription_and_help_callbacks(async_client: AsyncClient):
    user_id = 9005
    await api.repo.get_or_create_user({"id": user_id, "first_name": "MenuTestUser"})

    # Test menu_subscription
    mock_query_sub = AsyncMock()
    mock_query_sub.from_user.id = user_id
    mock_query_sub.data = "menu_subscription"
    mock_query_sub.message = AsyncMock()

    await bot_service.process_menu_subscription(mock_query_sub)
    mock_query_sub.answer.assert_called_once()
    mock_query_sub.message.answer.assert_called_once()
    assert "Управление подпиской" in mock_query_sub.message.answer.call_args.args[0]

    # Test menu_help
    mock_query_help = AsyncMock()
    mock_query_help.from_user.id = user_id
    mock_query_help.data = "menu_help"
    mock_query_help.message = AsyncMock()

    await bot_service.process_menu_help(mock_query_help)
    mock_query_help.answer.assert_called_once()
    mock_query_help.message.answer.assert_called_once()
    assert "Инструкция по работе" in mock_query_help.message.answer.call_args.args[0]


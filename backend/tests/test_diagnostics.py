"""
Unit tests for Pipeline Tracing & Diagnostics (/debug, /trace, database.log_trace).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import bot_service
from database import DatabaseRepository


@pytest_asyncio.fixture
async def diag_repo(tmp_path):
    test_db = tmp_path / "test_diag.sqlite3"
    repo = DatabaseRepository(test_db)
    await repo.open()
    yield repo
    await repo.close()


@pytest.mark.asyncio
async def test_log_trace_crud_and_auto_prune(diag_repo):
    """Test log_trace, retrieval by url, card_id, trace_id, and auto-pruning."""
    trace_id = "abc12345"
    post_url = "https://t.me/testchannel/99"

    # Log 3 events for trace_id
    await diag_repo.log_trace(
        trace_id, "received",
        channel="@testchannel", post_url=post_url, post_snippet="Test post snippet",
        bot_username="@vacancy_spott_bot", bot_token_prefix="8773545660"
    )
    await diag_repo.log_trace(
        trace_id, "card_created",
        channel="@testchannel", post_url=post_url, user_id=965000782, card_id=42,
        bot_username="@vacancy_spott_bot", bot_token_prefix="8773545660"
    )
    await diag_repo.log_trace(
        trace_id, "card_sent",
        channel="@testchannel", post_url=post_url, user_id=965000782, card_id=42,
        bot_username="@vacancy_spott_bot", bot_token_prefix="8773545660", detail="Sent OK"
    )

    # Retrieval tests
    by_trace = await diag_repo.get_traces_by_trace_id(trace_id)
    assert len(by_trace) == 3
    assert by_trace[0]["event"] == "received"
    assert by_trace[1]["event"] == "card_created"
    assert by_trace[2]["event"] == "card_sent"

    by_url = await diag_repo.get_traces_by_url("testchannel/99")
    assert len(by_url) == 3

    by_card = await diag_repo.get_traces_by_card_id(42)
    assert len(by_card) == 2

    recent = await diag_repo.get_recent_traces(limit=5)
    assert len(recent) == 3
    assert recent[0]["event"] == "card_sent"


@pytest.mark.asyncio
async def test_cmd_debug_admin_only(diag_repo):
    """Test /debug command returns diagnostic details for admin, ignored for non-admin."""
    orig_repo = bot_service.repo
    bot_service.repo = diag_repo

    try:
        mock_msg = AsyncMock()
        mock_msg.from_user.id = 965000782  # Admin ID

        mock_bot = AsyncMock()
        mock_bot_info = MagicMock()
        mock_bot_info.id = 8773545660
        mock_bot_info.username = "vacancy_spott_bot"
        mock_bot.get_me.return_value = mock_bot_info

        with pytest.MonkeyPatch.context() as m:
            m.setattr(bot_service, "get_bot", lambda: mock_bot)
            await bot_service.cmd_debug(mock_msg)

        mock_msg.answer.assert_called_once()
        text = mock_msg.answer.call_args[0][0]
        assert "DIAGNOSTIC DEBUG" in text
        assert "@vacancy_spott_bot" in text
        assert "8773545660" in text

        # Test non-admin access
        mock_non_admin = AsyncMock()
        mock_non_admin.from_user.id = 111222333
        await bot_service.cmd_debug(mock_non_admin)
        mock_non_admin.answer.assert_not_called()

    finally:
        bot_service.repo = orig_repo


@pytest.mark.asyncio
async def test_cmd_trace_query(diag_repo):
    """Test /trace command searching trace events."""
    orig_repo = bot_service.repo
    bot_service.repo = diag_repo

    try:
        await diag_repo.log_trace(
            "trc12345", "received",
            channel="@editors_video", post_url="https://t.me/editors_video/500",
            card_id=77, detail="Matched 1 keyword"
        )

        mock_msg = AsyncMock()
        mock_msg.from_user.id = 965000782  # Admin

        # Query by card_id 77
        mock_msg.text = "/trace 77"
        await bot_service.cmd_trace(mock_msg)

        mock_msg.answer.assert_called_once()
        text = mock_msg.answer.call_args[0][0]
        assert "Trace для card_id=77" in text
        assert "received" in text
        assert "@editors_video" in text

    finally:
        bot_service.repo = orig_repo

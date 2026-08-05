"""
Unit tests for Vacancy Spotter SaaS Backend.
"""

import asyncio
from pathlib import Path
import pytest
from database import DatabaseRepository
from models import (
    PortfolioItemCreateDTO,
    UserProfileUpdateDTO,
)

@pytest.mark.asyncio
async def test_multi_tenant_backend():

    test_db = Path("data/test_saas.sqlite3")
    if test_db.exists():
        test_db.unlink()

    repo = DatabaseRepository(test_db)
    await repo.open()

    # 1. Create User 1 (Video Editor)
    u1_dict = {"id": 1001, "first_name": "Алексей", "username": "alex_video"}
    prof1, is_new1 = await repo.get_or_create_user(u1_dict)
    assert is_new1 is True
    assert prof1.user_id == 1001
    assert prof1.profession_id == "video_editor"
    assert prof1.subscription_status == "demo"

    # 2. Update User 1 Profile & Resume
    upd1 = UserProfileUpdateDTO(
        experience_years=3,
        stop_words=["Adobe", "бартер"],
        software_stack=["DaVinci Resolve", "Cavalry"],
        bio_summary="Видеомонтажёр с фокусом на DaVinci и рилсы."
    )
    prof1_updated = await repo.update_user_profile(1001, upd1)
    assert prof1_updated.experience_years == 3
    assert "Adobe" in prof1_updated.stop_words
    assert "DaVinci Resolve" in prof1_updated.software_stack

    # 3. Add Portfolio Item for User 1
    p_dto = PortfolioItemCreateDTO(
        title="Showreel 2026",
        url="https://youtube.com/watch?v=example1",
        category="reels",
        orientation="vertical",
        description="Подборка лучших динамичных рилсов.",
        tags=["reels", "davinci", "sound_design"]
    )
    p_item = await repo.add_portfolio_item(1001, p_dto)
    assert p_item.id is not None
    assert p_item.user_id == 1001

    items1 = await repo.get_portfolio(1001)
    assert len(items1) == 1

    # 4. Create User 2 (Motion Designer) -> Check Isolation!
    u2_dict = {"id": 1002, "first_name": "Мария", "username": "maria_motion"}
    prof2, is_new2 = await repo.get_or_create_user(u2_dict)
    assert prof2.user_id == 1002

    items2 = await repo.get_portfolio(1002)
    assert len(items2) == 0  # Isolation check: User 2 has 0 portfolio items!

    # 5. Check Channels per Profession
    channels1 = await repo.get_user_channels(1001, "video_editor")
    assert len(channels1) > 0
    assert any("editors_video" in c.username for c in channels1)

    # Add custom channel for User 1
    custom_ch = await repo.add_custom_channel(1001, "video_editor", "@my_private_jobs")
    assert custom_ch.username == "my_private_jobs"

    # 6. Subscription status check
    sub = await repo.get_subscription_status(1001)
    assert sub.status == "demo"
    assert sub.is_valid is True
    assert sub.days_left == 2

    await repo.close()
    if test_db.exists():
        test_db.unlink()
    print("SUCCESS: All backend multi-tenant unit tests passed!")

if __name__ == "__main__":
    asyncio.run(run_multi_tenant_test())

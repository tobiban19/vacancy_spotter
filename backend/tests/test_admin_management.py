import pytest
from datetime import datetime, timezone
import pytest_asyncio
from database import DatabaseRepository
from models import AdminSubscriptionUpdateDTO, AdminBanUpdateDTO


@pytest_asyncio.fixture
async def test_repo(tmp_path):
    db_file = tmp_path / "test_admin.sqlite3"
    repo = DatabaseRepository(db_file)
    await repo.open()
    yield repo
    await repo.close()


@pytest.mark.asyncio
async def test_admin_user_management(test_repo):
    # 1. Provision test users
    u1, _ = await test_repo.get_or_create_user({"id": 1001, "first_name": "Alice", "username": "alice_test"})
    u2, _ = await test_repo.get_or_create_user({"id": 1002, "first_name": "Bob", "username": "bob_test"})

    # 2. Test initial stats
    stats = await test_repo.get_admin_stats()
    assert stats.total_users == 2
    assert stats.demo_users == 2
    assert stats.banned_users == 0

    # 3. Test get admin users list
    users, total = await test_repo.get_admin_users_list(page=1, limit=10)
    assert total == 2
    assert len(users) == 2

    # 4. Test subscription extension for Alice (+30 days)
    updated_alice = await test_repo.update_user_subscription(
        1001, AdminSubscriptionUpdateDTO(action="add_days", days=30)
    )
    assert updated_alice is not None
    assert updated_alice.subscription_status == "active"
    assert updated_alice.subscription_until is not None

    stats_after_sub = await test_repo.get_admin_stats()
    assert stats_after_sub.active_paid_users == 1
    assert stats_after_sub.demo_users == 1

    # 5. Test user banning for Bob
    is_banned_before = await test_repo.is_user_banned(1002)
    assert is_banned_before is False

    ban_success = await test_repo.set_user_ban_status(
        1002, AdminBanUpdateDTO(is_banned=True, ban_reason="Spamming")
    )
    assert ban_success is True

    is_banned_after = await test_repo.is_user_banned(1002)
    assert is_banned_after is True

    stats_after_ban = await test_repo.get_admin_stats()
    assert stats_after_ban.banned_users == 1

    # 6. Test user details fetching
    details_alice = await test_repo.get_admin_user_details(1001)
    assert details_alice is not None
    assert details_alice.profile.first_name == "Alice"
    assert details_alice.is_banned is False

    details_bob = await test_repo.get_admin_user_details(1002)
    assert details_bob is not None
    assert details_bob.is_banned is True
    assert details_bob.ban_reason == "Spamming"

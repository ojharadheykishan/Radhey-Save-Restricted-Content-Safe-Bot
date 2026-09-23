import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from safe_repo.core.mongo import plans_db


def test_15_day_plan_is_reported_separately(tmp_path, monkeypatch):
    monkeypatch.setattr(plans_db, "STORAGE", str(tmp_path / "plans.json"))

    async def scenario():
        await plans_db.add_premium(
            123,
            datetime.now(timezone.utc) + timedelta(days=15),
            plan_type="15_days_trial",
        )
        users = await plans_db.get_15_day_users()
        assert users[0]["user_id"] == 123
        assert users[0]["plan_type"] == "15_days_trial"

    asyncio.run(scenario())


def test_old_time_limited_records_remain_compatible(tmp_path, monkeypatch):
    monkeypatch.setattr(plans_db, "STORAGE", str(tmp_path / "plans.json"))

    async def scenario():
        await plans_db.add_premium(
            456,
            datetime.now(timezone.utc) + timedelta(days=3),
        )
        users = await plans_db.get_time_limited_users()
        assert users[0]["user_id"] == 456
        assert users[0]["plan_type"] == "time_limited"
        assert await plans_db.get_15_day_users() == []


def test_one_day_trial_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(plans_db, "STORAGE", str(tmp_path / "plans.json"))

    async def scenario():
        await plans_db.add_premium(
            789,
            datetime.now(timezone.utc) + timedelta(days=1),
            plan_type="1_day_trial",
        )
        users = await plans_db.get_1_day_users()
        assert users[0]["user_id"] == 789

    asyncio.run(scenario())

    asyncio.run(scenario())
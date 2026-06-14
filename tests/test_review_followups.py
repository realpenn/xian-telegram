"""评审 followup 修复的回归测试。"""
import pytest
import pytest_asyncio

from handlers import common
from models import db


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "followups.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_cleanup_removes_consumed_and_expired_tokens(temp_db):
    now = 100000
    # 全新未消费：保留
    await db.execute(
        "INSERT INTO callback_tokens(token, user_id, action, created_at) VALUES('fresh',1,'a',?)",
        (now,))
    # 过期未消费：清理
    await db.execute(
        "INSERT INTO callback_tokens(token, user_id, action, created_at) VALUES('expired',1,'a',?)",
        (now - common.TOKEN_TTL_SECONDS - 1,))
    # 已消费（即便很新）：清理
    await db.execute(
        "INSERT INTO callback_tokens(token, user_id, action, created_at, consumed_at) "
        "VALUES('used',1,'a',?,?)",
        (now, now))

    await common.cleanup_callback_tokens(now)

    rows = await db.fetchall("SELECT token FROM callback_tokens")
    assert {row["token"] for row in rows} == {"fresh"}

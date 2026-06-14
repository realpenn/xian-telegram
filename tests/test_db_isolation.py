"""读-写隔离回归测试：独立只读连接应读已提交快照，不脏读、不死锁。"""
import pytest
import pytest_asyncio

from models import db


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    await db.init_db(str(tmp_path / "isolation.db"))
    try:
        yield
    finally:
        await db.close_db()


@pytest.mark.asyncio
async def test_reads_see_committed_snapshot_not_open_txn(temp_db):
    await db.execute(
        "INSERT INTO users(tg_user_id, username, created_at) VALUES(1, 'old', 0)")

    async with db.transaction() as conn:
        await conn.execute("UPDATE users SET username='new' WHERE tg_user_id=1")
        # 写事务尚未提交：只读连接应看到旧快照，且不与写锁死锁。
        row = await db.fetchone("SELECT username FROM users WHERE tg_user_id=1")
        assert row["username"] == "old"

    # 提交后，后续读取可见新值。
    row = await db.fetchone("SELECT username FROM users WHERE tg_user_id=1")
    assert row["username"] == "new"


@pytest.mark.asyncio
async def test_committed_writes_visible_to_reads(temp_db):
    await db.execute(
        "INSERT INTO users(tg_user_id, username, created_at) VALUES(2, 'a', 0)")
    await db.execute("UPDATE users SET username='b' WHERE tg_user_id=2")
    row = await db.fetchone("SELECT username FROM users WHERE tg_user_id=2")
    assert row["username"] == "b"

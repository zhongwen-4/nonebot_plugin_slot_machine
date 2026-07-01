from dataclasses import dataclass
from decimal import Decimal

import aiosqlite

from nonebot_plugin_slot_machine.constants import DATABASE_PATH


@dataclass(frozen=True)
class Suspension:
    account: str
    reason: str
    suspended_until: int
    created_at: int


async def initialize_risk_database() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_transfer_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_account TEXT NOT NULL,
                receiver_account TEXT NOT NULL,
                amount TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_suspensions (
                account TEXT PRIMARY KEY,
                reason TEXT NOT NULL,
                suspended_until INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        await db.commit()


async def record_transfer(
    sender_account: str,
    receiver_account: str,
    amount: Decimal,
    created_at: int,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO risk_transfer_records (
                sender_account, receiver_account, amount, created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (sender_account, receiver_account, str(amount), created_at),
        )
        await db.commit()


async def get_sender_transfer_total(
    sender_account: str,
    receiver_account: str,
    since: int,
) -> Decimal:
    async with (
        aiosqlite.connect(DATABASE_PATH) as db,
        db.execute(
            """
            SELECT amount
            FROM risk_transfer_records
            WHERE sender_account = ?
              AND receiver_account = ?
              AND created_at >= ?
            """,
            (sender_account, receiver_account, since),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return sum((Decimal(row[0]) for row in rows), Decimal(0))


async def get_receiver_sender_count(receiver_account: str, since: int) -> int:
    async with (
        aiosqlite.connect(DATABASE_PATH) as db,
        db.execute(
            """
            SELECT COUNT(DISTINCT sender_account)
            FROM risk_transfer_records
            WHERE receiver_account = ?
              AND created_at >= ?
            """,
            (receiver_account, since),
        ) as cursor,
    ):
        row = await cursor.fetchone()
    return int(row[0] if row is not None else 0)


async def upsert_suspension(
    account: str,
    reason: str,
    suspended_until: int,
    created_at: int,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO risk_suspensions (
                account, reason, suspended_until, created_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(account) DO UPDATE SET
                reason = excluded.reason,
                suspended_until = MAX(
                    risk_suspensions.suspended_until,
                    excluded.suspended_until
                ),
                created_at = excluded.created_at
            """,
            (account, reason, suspended_until, created_at),
        )
        await db.commit()


async def get_active_suspension(account: str, current_time: int) -> Suspension | None:
    async with (
        aiosqlite.connect(DATABASE_PATH) as db,
        db.execute(
            """
            SELECT account, reason, suspended_until, created_at
            FROM risk_suspensions
            WHERE account = ?
              AND suspended_until > ?
            """,
            (account, current_time),
        ) as cursor,
    ):
        row = await cursor.fetchone()

    if row is None:
        return None

    return Suspension(
        account=row[0],
        reason=row[1],
        suspended_until=row[2],
        created_at=row[3],
    )

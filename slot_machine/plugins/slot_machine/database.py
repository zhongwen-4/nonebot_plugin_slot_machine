from dataclasses import dataclass
from decimal import Decimal

import aiosqlite

from .algorithm import BetConfig, calculate_total_bet
from .constants import DATABASE_PATH, REGISTRATION_REWARD


@dataclass(frozen=True)
class UserData:
    account: str
    coins: Decimal
    spin_count: int
    win_count: int
    total_payout: Decimal


async def initialize_database() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS slot_bet_settings (
                account TEXT PRIMARY KEY,
                bet_size TEXT NOT NULL,
                multiplier INTEGER NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS slot_users (
                account TEXT PRIMARY KEY,
                coins TEXT NOT NULL,
                spin_count INTEGER NOT NULL DEFAULT 0,
                win_count INTEGER NOT NULL DEFAULT 0,
                total_payout TEXT NOT NULL DEFAULT '0'
            )
            """
        )
        await ensure_user_stats_columns(db)
        await db.commit()


async def ensure_user_stats_columns(db: aiosqlite.Connection) -> None:
    columns = {
        row[1]
        for row in await db.execute_fetchall("PRAGMA table_info(slot_users)")
    }
    if "win_count" not in columns:
        await db.execute(
            "ALTER TABLE slot_users ADD COLUMN win_count INTEGER NOT NULL DEFAULT 0"
        )
    if "total_payout" not in columns:
        await db.execute(
            "ALTER TABLE slot_users ADD COLUMN total_payout TEXT NOT NULL DEFAULT '0'"
        )


async def register_user(account: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO slot_users (account, coins, spin_count)
            VALUES (?, ?, 0)
            """,
            (account, str(REGISTRATION_REWARD)),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_user(account: str) -> UserData | None:
    async with (
        aiosqlite.connect(DATABASE_PATH) as db,
        db.execute(
            """
            SELECT account, coins, spin_count, win_count, total_payout
            FROM slot_users
            WHERE account = ?
            """,
            (account,),
        ) as cursor,
    ):
        row = await cursor.fetchone()

    if row is None:
        return None

    return UserData(
        account=row[0],
        coins=Decimal(row[1]),
        spin_count=row[2],
        win_count=row[3],
        total_payout=Decimal(row[4]),
    )


async def get_bet_setting(account: str) -> BetConfig | None:
    async with (
        aiosqlite.connect(DATABASE_PATH) as db,
        db.execute(
            """
            SELECT bet_size, multiplier
            FROM slot_bet_settings
            WHERE account = ?
            """,
            (account,),
        ) as cursor,
    ):
        row = await cursor.fetchone()

    if row is None:
        return None

    bet_size = Decimal(row[0])
    multiplier = row[1]
    return BetConfig(
        bet_size=bet_size,
        multiplier=multiplier,
        total_bet=calculate_total_bet(bet_size, multiplier),
    )


async def upsert_bet_setting(account: str, bet_config: BetConfig) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO slot_bet_settings (account, bet_size, multiplier)
            VALUES (?, ?, ?)
            ON CONFLICT(account) DO UPDATE SET
                bet_size = excluded.bet_size,
                multiplier = excluded.multiplier
            """,
            (account, str(bet_config.bet_size), bet_config.multiplier),
        )
        await db.commit()


async def apply_spin_result(
    account: str, total_bet: Decimal, total_payout: Decimal
) -> UserData:
    user = await get_user(account)
    if user is None:
        msg = "user not registered"
        raise LookupError(msg)

    remaining_coins = user.coins - total_bet
    if remaining_coins < 0:
        msg = "insufficient coins"
        raise ValueError(msg)

    final_coins = remaining_coins + total_payout
    win_increment = int(total_payout > 0)
    updated_total_payout = user.total_payout + total_payout

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE slot_users
            SET
                coins = ?,
                spin_count = spin_count + 1,
                win_count = win_count + ?,
                total_payout = ?
            WHERE account = ?
            """,
            (str(final_coins), win_increment, str(updated_total_payout), account),
        )
        await db.commit()

    return UserData(
        account=account,
        coins=final_coins,
        spin_count=user.spin_count + 1,
        win_count=user.win_count + win_increment,
        total_payout=updated_total_payout,
    )


async def add_user_coins(account: str, amount: Decimal) -> UserData:
    user = await get_user(account)
    if user is None:
        msg = "user not registered"
        raise LookupError(msg)

    final_coins = user.coins + amount
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE slot_users
            SET coins = ?
            WHERE account = ?
            """,
            (str(final_coins), account),
        )
        await db.commit()

    return UserData(
        account=account,
        coins=final_coins,
        spin_count=user.spin_count,
        win_count=user.win_count,
        total_payout=user.total_payout,
    )


async def transfer_user_coins(
    sender_account: str,
    receiver_account: str,
    amount: Decimal,
) -> tuple[UserData, UserData]:
    if amount <= 0:
        msg = "transfer amount must be positive"
        raise ValueError(msg)
    if sender_account == receiver_account:
        msg = "cannot transfer to self"
        raise ValueError(msg)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            sender = await fetch_user_for_update(db, sender_account)
            receiver = await fetch_user_for_update(db, receiver_account)
            sender, receiver = ensure_transfer_users_exist(sender, receiver)
            ensure_transfer_balance(sender, amount)

            updated_sender = UserData(
                account=sender.account,
                coins=sender.coins - amount,
                spin_count=sender.spin_count,
                win_count=sender.win_count,
                total_payout=sender.total_payout,
            )
            updated_receiver = UserData(
                account=receiver.account,
                coins=receiver.coins + amount,
                spin_count=receiver.spin_count,
                win_count=receiver.win_count,
                total_payout=receiver.total_payout,
            )
            await db.execute(
                """
                UPDATE slot_users
                SET coins = ?
                WHERE account = ?
                """,
                (str(updated_sender.coins), updated_sender.account),
            )
            await db.execute(
                """
                UPDATE slot_users
                SET coins = ?
                WHERE account = ?
                """,
                (str(updated_receiver.coins), updated_receiver.account),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return updated_sender, updated_receiver


def ensure_transfer_users_exist(
    sender: UserData | None,
    receiver: UserData | None,
) -> tuple[UserData, UserData]:
    if sender is None or receiver is None:
        msg = "user not registered"
        raise LookupError(msg)
    return sender, receiver


def ensure_transfer_balance(sender: UserData, amount: Decimal) -> None:
    if sender.coins < amount:
        msg = "insufficient coins"
        raise ValueError(msg)


async def fetch_user_for_update(
    db: aiosqlite.Connection,
    account: str,
) -> UserData | None:
    async with db.execute(
        """
        SELECT account, coins, spin_count, win_count, total_payout
        FROM slot_users
        WHERE account = ?
        """,
        (account,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    return UserData(
        account=row[0],
        coins=Decimal(row[1]),
        spin_count=row[2],
        win_count=row[3],
        total_payout=Decimal(row[4]),
    )

from dataclasses import dataclass

import aiosqlite

from nonebot_plugin_slot_machine.constants import DATABASE_PATH


@dataclass(frozen=True)
class ScrewWorkState:
    account: str
    stamina: int
    updated_at: int
    started_at: int | None
    mode: str


async def initialize_screw_work_database() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS screw_work_states (
                account TEXT PRIMARY KEY,
                stamina INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                started_at INTEGER,
                mode TEXT NOT NULL DEFAULT '普通'
            )
            """
        )
        await ensure_screw_work_mode_column(db)
        await db.commit()


async def ensure_screw_work_mode_column(db: aiosqlite.Connection) -> None:
    columns = {
        row[1]
        for row in await db.execute_fetchall("PRAGMA table_info(screw_work_states)")
    }
    if "mode" not in columns:
        await db.execute(
            "ALTER TABLE screw_work_states ADD COLUMN mode TEXT NOT NULL DEFAULT '普通'"
        )


async def get_screw_work_state(
    account: str,
    current_time: int,
) -> ScrewWorkState:
    await initialize_screw_work_database()
    async with (
        aiosqlite.connect(DATABASE_PATH) as db,
        db.execute(
            """
            SELECT account, stamina, updated_at, started_at, mode
            FROM screw_work_states
            WHERE account = ?
            """,
            (account,),
        ) as cursor,
    ):
        row = await cursor.fetchone()

    if row is not None:
        return ScrewWorkState(
            account=row[0],
            stamina=row[1],
            updated_at=row[2],
            started_at=row[3],
            mode=row[4],
        )

    state = ScrewWorkState(
        account=account,
        stamina=100,
        updated_at=current_time,
        started_at=None,
        mode="普通",
    )
    await save_screw_work_state(state)
    return state


async def save_screw_work_state(state: ScrewWorkState) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO screw_work_states (
                account, stamina, updated_at, started_at, mode
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account) DO UPDATE SET
                stamina = excluded.stamina,
                updated_at = excluded.updated_at,
                started_at = excluded.started_at,
                mode = excluded.mode
            """,
            (
                state.account,
                state.stamina,
                state.updated_at,
                state.started_at,
                state.mode,
            ),
        )
        await db.commit()

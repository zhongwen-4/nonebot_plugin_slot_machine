from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import aiosqlite
from nonebot import get_driver, on_command
from nonebot.adapters.milky import Message
from nonebot.adapters.milky.event import MessageEvent
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata

from slot_machine.plugins.slot_machine.constants import DATABASE_PATH
from slot_machine.plugins.slot_machine.database import add_user_coins, get_user
from slot_machine.plugins.slot_machine.utils import format_decimal

__plugin_meta__ = PluginMetadata(
    name="screw_work",
    description="打螺丝赚金币。",
    usage=(
        "开始打螺丝 [普通/韭菜/牛马/卷王]：开始工作\n"
        "停止打螺丝：停止工作并结算金币\n"
        "打螺丝状态：查看体力和工作状态"
    ),
)

start_screw_work = on_command("开始打螺丝", block=True)
stop_screw_work = on_command("停止打螺丝", block=True)
screw_work_status = on_command("打螺丝状态", aliases={"螺丝状态"}, block=True)


@dataclass(frozen=True)
class ScrewWorkMode:
    name: str
    coins_per_minute: int
    stamina_cost_per_minute: int


@dataclass(frozen=True)
class ScrewWorkState:
    account: str
    stamina: int
    updated_at: int
    started_at: int | None
    mode: str


@get_driver().on_startup
async def startup_screw_work() -> None:
    await initialize_screw_work_database()


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


def get_screw_work_modes() -> dict[str, ScrewWorkMode]:
    return {
        "普通": ScrewWorkMode("普通", 10, 1),
        "韭菜": ScrewWorkMode("韭菜", 20, 5),
        "牛马": ScrewWorkMode("牛马", 30, 10),
        "卷王": ScrewWorkMode("卷王", 40, 15),
    }


def parse_screw_work_mode(raw_mode: str) -> ScrewWorkMode | None:
    mode_name = raw_mode.strip() or "普通"
    return get_screw_work_modes().get(mode_name)


def format_screw_work_modes() -> str:
    return "、".join(
        f"{mode.name}({mode.coins_per_minute}金币/分钟，"
        f"{mode.stamina_cost_per_minute}体力/分钟)"
        for mode in get_screw_work_modes().values()
    )


def now_timestamp() -> int:
    return int(datetime.now(UTC).timestamp())


async def get_screw_work_state(account: str) -> ScrewWorkState:
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

    current_time = now_timestamp()
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


def settle_screw_work_state(
    state: ScrewWorkState,
    current_time: int,
) -> tuple[ScrewWorkState, Decimal, int]:
    elapsed = max(current_time - state.updated_at, 0)
    earned_minutes = 0
    stamina = state.stamina

    if state.started_at is None:
        stamina = min(100, stamina + elapsed // 30)
        return (
            ScrewWorkState(
                account=state.account,
                stamina=stamina,
                updated_at=current_time,
                started_at=None,
                mode=state.mode,
            ),
            Decimal(0),
            0,
        )

    mode = get_screw_work_modes().get(state.mode, get_screw_work_modes()["普通"])
    work_minutes = elapsed // 60
    affordable_minutes = stamina // mode.stamina_cost_per_minute
    earned_minutes = min(work_minutes, affordable_minutes)
    stamina -= earned_minutes * mode.stamina_cost_per_minute

    remaining_elapsed = elapsed - earned_minutes * 60
    if earned_minutes < work_minutes:
        stamina = min(100, stamina + remaining_elapsed // 30)
        started_at = None
    else:
        started_at = state.started_at

    return (
        ScrewWorkState(
            account=state.account,
            stamina=stamina,
            updated_at=current_time,
            started_at=started_at,
            mode=mode.name,
        ),
        Decimal(earned_minutes * mode.coins_per_minute),
        earned_minutes,
    )


async def settle_account(account: str) -> tuple[ScrewWorkState, Decimal, int]:
    state = await get_screw_work_state(account)
    settled_state, earned_coins, earned_minutes = settle_screw_work_state(
        state,
        now_timestamp(),
    )
    await save_screw_work_state(settled_state)
    if earned_coins:
        await add_user_coins(account, earned_coins)
    return settled_state, earned_coins, earned_minutes


@start_screw_work.handle()
async def handle_start_screw_work(
    event: MessageEvent,
    args: Message = CommandArg(),
) -> None:
    account = event.get_user_id()
    user = await get_user(account)
    if user is None:
        await start_screw_work.finish("你还没有注册。\n请先发送：注册老虎机")

    selected_mode = parse_screw_work_mode(args.extract_plain_text())
    if selected_mode is None:
        await start_screw_work.finish(
            "未知打螺丝模式。\n"
            f"可用模式：{format_screw_work_modes()}"
        )
        return

    state, earned_coins, earned_minutes = await settle_account(account)
    if state.started_at is not None:
        await start_screw_work.finish(
            "你已经在打螺丝了。\n"
            f"当前模式：{state.mode}\n"
            f"当前体力：{state.stamina}/100\n"
            f"刚结算：{earned_minutes} 分钟，获得 {format_decimal(earned_coins)} 金币"
        )

    if state.stamina < selected_mode.stamina_cost_per_minute:
        await start_screw_work.finish(
            "体力不足，先休息一下吧。\n"
            f"当前体力：{state.stamina}/100\n"
            f"{selected_mode.name}模式每分钟需要 "
            f"{selected_mode.stamina_cost_per_minute} 点体力"
        )

    current_time = now_timestamp()
    await save_screw_work_state(
        ScrewWorkState(
            account=account,
            stamina=state.stamina,
            updated_at=current_time,
            started_at=current_time,
            mode=selected_mode.name,
        )
    )
    await start_screw_work.finish(
        "开始打螺丝。\n"
        f"模式：{selected_mode.name}\n"
        f"收益：每分钟 {selected_mode.coins_per_minute} 金币\n"
        f"消耗：每分钟 {selected_mode.stamina_cost_per_minute} 点体力\n"
        f"当前体力：{state.stamina}/100"
    )


@stop_screw_work.handle()
async def handle_stop_screw_work(event: MessageEvent) -> None:
    account = event.get_user_id()
    user = await get_user(account)
    if user is None:
        await stop_screw_work.finish("你还没有注册。\n请先发送：注册老虎机")

    state, earned_coins, earned_minutes = await settle_account(account)
    await save_screw_work_state(
        ScrewWorkState(
            account=account,
            stamina=state.stamina,
            updated_at=now_timestamp(),
            started_at=None,
            mode=state.mode,
        )
    )
    updated_user = await get_user(account)
    if updated_user is None:
        await stop_screw_work.finish("账号数据异常，请稍后再试。")
        return
    await stop_screw_work.finish(
        "已停止打螺丝。\n"
        f"模式：{state.mode}\n"
        f"本次结算：{earned_minutes} 分钟\n"
        f"获得金币：{format_decimal(earned_coins)}\n"
        f"当前体力：{state.stamina}/100\n"
        f"当前金币：{format_decimal(updated_user.coins)}"
    )


@screw_work_status.handle()
async def handle_screw_work_status(event: MessageEvent) -> None:
    account = event.get_user_id()
    user = await get_user(account)
    if user is None:
        await screw_work_status.finish("你还没有注册。\n请先发送：注册老虎机")

    state, earned_coins, earned_minutes = await settle_account(account)
    updated_user = await get_user(account)
    if updated_user is None:
        await screw_work_status.finish("账号数据异常，请稍后再试。")
        return
    status = "工作中" if state.started_at is not None else "休息中"
    mode = get_screw_work_modes().get(state.mode, get_screw_work_modes()["普通"])
    await screw_work_status.finish(
        "打螺丝状态\n"
        f"状态：{status}\n"
        f"模式：{mode.name}\n"
        f"收益：{mode.coins_per_minute} 金币/分钟\n"
        f"消耗：{mode.stamina_cost_per_minute} 体力/分钟\n"
        f"体力：{state.stamina}/100\n"
        f"刚结算：{earned_minutes} 分钟，获得 {format_decimal(earned_coins)} 金币\n"
        f"当前金币：{format_decimal(updated_user.coins)}"
    )

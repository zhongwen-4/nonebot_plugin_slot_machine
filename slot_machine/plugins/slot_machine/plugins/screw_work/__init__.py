from decimal import Decimal

from nonebot import get_driver, on_command
from nonebot.adapters.milky import Message
from nonebot.adapters.milky.event import MessageEvent
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata

from slot_machine.plugins.slot_machine.database import add_user_coins, get_user
from slot_machine.plugins.slot_machine.utils import format_decimal

from .database import (
    ScrewWorkState,
    get_screw_work_state,
    initialize_screw_work_database,
    save_screw_work_state,
)
from .utils import (
    format_screw_work_modes,
    get_screw_work_modes,
    now_timestamp,
    parse_screw_work_args,
    settle_instant_screw_work,
    settle_screw_work_state,
)

__plugin_meta__ = PluginMetadata(
    name="screw_work",
    description="打螺丝赚金币。",
    usage=(
        "开始打螺丝 <分钟>：按普通模式立即结算\n"
        "开始打螺丝 <普通/韭菜/牛马/卷王> <分钟>：按指定模式立即结算\n"
        "停止打螺丝：停止工作并结算金币\n"
        "打螺丝状态：查看体力和工作状态"
    ),
)

start_screw_work = on_command("开始打螺丝", block=True)
stop_screw_work = on_command("停止打螺丝", block=True)
screw_work_status = on_command("打螺丝状态", aliases={"螺丝状态"}, block=True)


@get_driver().on_startup
async def startup_screw_work() -> None:
    await initialize_screw_work_database()


async def settle_account(account: str) -> tuple[ScrewWorkState, Decimal, int]:
    current_time = now_timestamp()
    state = await get_screw_work_state(account, current_time)
    settled_state, earned_coins, earned_minutes = settle_screw_work_state(
        state,
        current_time,
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

    selected_mode, work_minutes = parse_screw_work_args(args.extract_plain_text())
    if selected_mode is None:
        await start_screw_work.finish(
            "未知打螺丝模式。\n"
            f"可用模式：{format_screw_work_modes()}"
        )
        return
    if work_minutes is None:
        await start_screw_work.finish(
            "请输入要打螺丝的分钟数。\n"
            "示例：开始打螺丝 10\n"
            "示例：开始打螺丝 牛马 10"
        )
        return

    state, earned_coins, earned_minutes = await settle_account(account)
    if state.stamina < selected_mode.stamina_cost_per_minute:
        await start_screw_work.finish(
            "体力不足，先休息一下吧。\n"
            f"当前体力：{state.stamina}/100\n"
            f"{selected_mode.name}模式每分钟需要 "
            f"{selected_mode.stamina_cost_per_minute} 点体力"
        )

    current_time = now_timestamp()
    final_state, instant_coins, actual_minutes = settle_instant_screw_work(
        state,
        selected_mode,
        work_minutes,
        current_time,
    )
    await save_screw_work_state(final_state)
    if instant_coins:
        await add_user_coins(account, instant_coins)

    updated_user = await get_user(account)
    if updated_user is None:
        await start_screw_work.finish("账号数据异常，请稍后再试。")
        return

    await start_screw_work.finish(
        "打螺丝完成。\n"
        f"模式：{selected_mode.name}\n"
        f"计划时间：{work_minutes} 分钟\n"
        f"实际结算：{actual_minutes} 分钟\n"
        f"获得金币：{format_decimal(instant_coins)}\n"
        f"恢复结算：{earned_minutes} 分钟，获得 {format_decimal(earned_coins)} 金币\n"
        f"当前体力：{final_state.stamina}/100\n"
        f"当前金币：{format_decimal(updated_user.coins)}"
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

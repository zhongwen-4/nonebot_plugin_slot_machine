import asyncio
from decimal import Decimal, InvalidOperation
from pathlib import Path

from nonebot import get_driver, require, logger, on_command

require("nonebot_plugin_alconna")
from nonebot.adapters.milky import MessageSegment
from nonebot.adapters.milky.event import MessageEvent
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, on_alconna

from .algorithm import (
    BetConfigError,
    CascadeResult,
    calculate_allowed_win_probability,
    format_bet_summary,
    parse_bet_config,
    resolve_controlled_spin,
)
from .constants import REGISTRATION_REWARD
from .database import (
    apply_spin_result,
    get_bet_setting,
    get_user,
    initialize_database,
    register_user,
    transfer_user_coins,
    upsert_bet_setting,
)
from .utils import (
    GeneratedSpinImage,
    SpinMessageContext,
    build_forward_message,
    draw_spin_result_image,
    format_decimal,
)

__plugin_meta__ = PluginMetadata(
    name="slot_machine",
    description="一个老虎机游戏插件",
    usage=(
        "注册老虎机/注册：领取初始金币\n"
        "设置投注 <投注大小> <投注倍数>：保存投注设置\n"
        "查询老虎机/查询：查看账号和投注信息\n"
        "开始旋转：开始抽奖"
    ),
    supported_adapters={"~milky"},
    type="application",
    homepage="https://github.com/zhongwen-4/nonebot_plugin_slot_machine"
)

slot_register = on_command(
    "注册老虎机",
    aliases={"注册"},
    block=True,
)
slot_setting = on_alconna(
    Alconna(
        "设置投注",
        Args["bet_size", str]["multiplier", int],
        meta=CommandMeta(description="设置老虎机投注大小和投注倍数"),
    ),
    aliases={"setslot"},
    block=True,
)
slot_transfer = on_alconna(
    Alconna(
        "转账",
        Args["receiver_account", str]["amount", str],
        meta=CommandMeta(description="向其他老虎机账号转账金币"),
    ),
    block=True,
)
slot_query = on_command(
    "查询老虎机",
    aliases={"查询"},
    block=True,
)
slot_machine = on_command(
    "开始旋转",
    block=True,
)

@get_driver().on_startup
async def startup_slot_machine() -> None:
    await initialize_database()


async def send_spin_result(event: MessageEvent, context: SpinMessageContext) -> None:
    images: list[GeneratedSpinImage] = []
    try:
        images = list(
            await asyncio.gather(
                *(
                    draw_spin_result_image(
                        context=context,
                        cascade=cascade,
                        cascade_index=index,
                    )
                    for index, cascade in enumerate(context.all_cascades, start=1)
                )
            )
        )

        if len(images) <= 3:  # noqa: PLR2004
            for image in images[:-1]:
                await slot_machine.send(MessageSegment.image(raw=image.data))
            await slot_machine.finish(MessageSegment.image(raw=images[-1].data))

        await slot_machine.finish(build_forward_message(event, context, images))
    finally:
        for image in images:
            image.path.unlink(missing_ok=True)


async def send_miss_result(context: SpinMessageContext, board: list[list[str]]) -> None:
    image = await draw_spin_result_image(
        context,
        CascadeResult(
            board=board,
            highlighted_positions=frozenset(),
            bonus_multiplier=1,
            payout=Decimal(0),
        ),
    )
    try:
        await slot_machine.finish(MessageSegment.image(raw=image.data))
    finally:
        image.path.unlink(missing_ok=True)


@slot_register.handle()
async def handle_slot_register(event: MessageEvent) -> None:
    account = event.get_user_id()
    registered = await register_user(account)
    user = await get_user(account)

    if user is None:
        await slot_register.finish("注册失败，请稍后再试。")

    if not registered:
        await slot_register.finish(
            "你已经注册过了。\n"
            f"账号：{account}\n"
            f"当前金币：{format_decimal(user.coins)}\n"
            f"抽奖次数：{user.spin_count}"
        )

    await slot_register.finish(
        "注册成功。\n"
        f"账号：{account}\n"
        f"赠送金币：{format_decimal(REGISTRATION_REWARD)}\n"
        f"当前金币：{format_decimal(user.coins)}"
    )


@slot_setting.handle()
async def handle_slot_setting(
    event: MessageEvent,
    bet_size: str,
    multiplier: int,
) -> None:
    account = event.get_user_id()
    user = await get_user(account)

    if user is None:
        await slot_setting.finish("你还没有注册。\n请先发送：注册老虎机")

    try:
        bet_config = parse_bet_config(f"{bet_size} {multiplier}")
    except BetConfigError:
        await slot_setting.finish(
            "请输入：设置投注 <投注大小> <投注倍数>，例如：设置投注 0.2 5\n"
            "投注大小只能是 0.02、0.2 或 1，投注倍数只能是 1 到 10 的整数。"
        )

    await upsert_bet_setting(account, bet_config)
    await slot_setting.finish(f"已保存你的投注设置。\n{format_bet_summary(bet_config)}")


@slot_transfer.handle()
async def handle_slot_transfer(
    event: MessageEvent,
    receiver_account: str,
    amount: str,
) -> None:
    sender_account = event.get_user_id()
    sender = await get_user(sender_account)
    if sender is None:
        await slot_transfer.finish("你还没有注册。\n请先发送：注册老虎机")

    try:
        transfer_amount = Decimal(amount)
    except InvalidOperation:
        await slot_transfer.finish("请输入正确金额，例如：转账 123456 10")

    if transfer_amount <= 0:
        await slot_transfer.finish("转账金额必须大于 0。")

    receiver = await get_user(receiver_account)
    if receiver is None:
        await slot_transfer.finish("对方还没有注册老虎机账号。")

    if sender_account == receiver_account:
        await slot_transfer.finish("不能给自己转账。")

    if sender.coins < transfer_amount:
        await slot_transfer.finish(
            "金币不足，无法转账。\n"
            f"当前金币：{format_decimal(sender.coins)}\n"
            f"转账金额：{format_decimal(transfer_amount)}"
        )

    updated_sender, updated_receiver = await transfer_user_coins(
        sender_account,
        receiver_account,
        transfer_amount,
    )
    await slot_transfer.finish(
        "转账成功。\n"
        f"收款账号：{receiver_account}\n"
        f"转账金额：{format_decimal(transfer_amount)} 金币\n"
        f"你的剩余金币：{format_decimal(updated_sender.coins)}\n"
        f"对方当前金币：{format_decimal(updated_receiver.coins)}"
    )


@slot_query.handle()
async def handle_slot_query(event: MessageEvent) -> None:
    account = event.get_user_id()
    user = await get_user(account)

    if user is None:
        await slot_query.finish("你还没有注册。\n请先发送：注册老虎机")

    bet_config = await get_bet_setting(account)
    bet_text = (
        format_bet_summary(bet_config)
        if bet_config is not None
        else "尚未设置投注"
    )
    await slot_query.finish(
        "老虎机账号信息\n"
        f"账号：{account}\n"
        f"当前金币：{format_decimal(user.coins)}\n"
        f"抽奖次数：{user.spin_count}\n"
        f"中奖次数：{user.win_count}\n"
        f"累计获得：{format_decimal(user.total_payout)} 金币\n\n"
        f"当前投注：\n{bet_text}"
    )


@slot_machine.handle()
async def handle_slot_machine(event: MessageEvent) -> None:
    account = event.get_user_id()
    user = await get_user(account)

    if user is None:
        await slot_machine.finish("你还没有注册。\n请先发送：注册老虎机")

    bet_config = await get_bet_setting(account)
    if bet_config is None:
        await slot_machine.finish(
            "你还没有设置投注。\n"
            "请先发送：设置投注 <投注大小> <投注倍数>\n"
            "例如：设置投注 0.2 5"
        )

    if user.coins < bet_config.total_bet:
        await slot_machine.finish(
            "金币不足，无法抽奖。\n"
            f"当前金币：{format_decimal(user.coins)}\n"
            f"本次需要：{format_decimal(bet_config.total_bet)}"
        )

    allowed_probability = calculate_allowed_win_probability(
        user.coins,
        user.win_count,
        user.total_payout,
    )
    logger.info(
        f"老虎机抽奖概率 | 账号：{account} | "
        f"金币：{format_decimal(user.coins)} | "
        f"中奖次数：{user.win_count} | "
        f"累计获得：{format_decimal(user.total_payout)} | "
        f"本次概率：{allowed_probability:.2%}"
    )

    spin_result = resolve_controlled_spin(
        bet_config,
        user.coins,
        user.win_count,
        user.total_payout,
    )
    updated_user = await apply_spin_result(
        account, bet_config.total_bet, spin_result.total_payout
    )
    context = SpinMessageContext(
        account=account,
        total_bet=format_decimal(bet_config.total_bet),
        total_payout=format_decimal(spin_result.total_payout),
        remaining_coins=format_decimal(updated_user.coins),
        all_cascades=list(spin_result.cascades),
    )

    if not spin_result.cascades:
        await send_miss_result(context, spin_result.final_board)

    await send_spin_result(event, context)

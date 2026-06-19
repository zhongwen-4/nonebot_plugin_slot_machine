from nonebot import get_driver, on_command
from nonebot.adapters.milky import Message, MessageSegment
from nonebot.adapters.milky.event import MessageEvent
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata

from .algorithm import (
    BetConfigError,
    build_board_columns,
    format_bet_summary,
    format_cascade_summary,
    format_match_list,
    parse_bet_config,
    resolve_spin,
)
from .constants import REGISTRATION_REWARD
from .database import (
    apply_spin_result,
    get_bet_setting,
    get_user,
    initialize_database,
    register_user,
    upsert_bet_setting,
)
from .utils import (
    SpinMessageContext,
    build_forward_message,
    format_decimal,
    render_spin_result_image,
)

FORWARD_THRESHOLD = 3

__plugin_meta__ = PluginMetadata(
    name="slot_machine",
    description="A simple 5x6 slot machine game.",
    usage=(
        '发送 "注册老虎机" 领取初始金币，'
        '发送 "设置投注 <投注大小> <投注倍数>" 保存设置，'
        '发送 "老虎机" 进行抽取。'
    ),
)

slot_register = on_command("注册老虎机", aliases={"注册"}, block=True)
slot_setting = on_command("设置投注", aliases={"setslot"}, block=True)
slot_machine = on_command("老虎机", aliases={"slot", "slots"}, block=True)


@get_driver().on_startup
async def startup_slot_machine() -> None:
    await initialize_database()


async def send_spin_result(event: MessageEvent, context: SpinMessageContext) -> None:
    latest_cascade = context.latest_cascade
    summary_image = await render_spin_result_image(
        context=context,
        columns=build_board_columns(
            latest_cascade.board, latest_cascade.highlighted_positions
        ),
        matches=format_match_list(
            latest_cascade.matches, latest_cascade.bonus_multiplier
        ),
        current_multiplier=latest_cascade.bonus_multiplier,
    )

    if len(context.cascade_sections) <= FORWARD_THRESHOLD:
        await slot_machine.finish(MessageSegment.image(raw=summary_image))

    cascade_images = []
    for index, cascade in enumerate(context.all_cascades, start=1):
        cascade_images.append(
            await render_spin_result_image(
                context=context,
                columns=build_board_columns(
                    cascade.board, cascade.highlighted_positions
                ),
                matches=format_match_list(
                    cascade.matches, cascade.bonus_multiplier
                ),
                current_multiplier=cascade.bonus_multiplier,
                cascades=[context.cascade_sections[index - 1]],
            )
        )

    await slot_machine.send(MessageSegment.image(raw=summary_image))
    await slot_machine.finish(
        build_forward_message(
            event,
            context,
            summary_image=summary_image,
            cascade_images=cascade_images,
        )
    )


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
    event: MessageEvent, args: Message = CommandArg()
) -> None:
    raw_args = args.extract_plain_text().strip()
    account = event.get_user_id()
    user = await get_user(account)

    if user is None:
        await slot_setting.finish("你还没有注册。\n请先发送：注册老虎机")

    try:
        bet_config = parse_bet_config(raw_args)
    except BetConfigError:
        await slot_setting.finish(
            "请输入：设置投注 <投注大小> <投注倍数>，例如：设置投注 0.2 5\n"
            "投注大小只能是 0.02、0.2 或 1，投注倍数只能是 1 到 10 的整数。"
        )

    await upsert_bet_setting(account, bet_config)
    await slot_setting.finish(f"已保存你的投注设置。\n{format_bet_summary(bet_config)}")


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

    spin_result = resolve_spin(bet_config)
    updated_user = await apply_spin_result(
        account, bet_config.total_bet, spin_result.total_payout
    )

    if not spin_result.cascades:
        await slot_machine.finish(
            "老虎机结果：\n"
            f"账号：{account}\n"
            f"{format_bet_summary(bet_config)}\n"
            "总派奖：0 金币\n"
            f"剩余金币：{format_decimal(updated_user.coins)}\n"
            f"抽奖次数：{updated_user.spin_count}\n\n"
            "本次未中奖。"
        )

    cascade_sections = [
        format_cascade_summary(index, cascade)
        for index, cascade in enumerate(spin_result.cascades, start=1)
    ]
    await send_spin_result(
        event,
        SpinMessageContext(
            account=account,
            bet_summary=format_bet_summary(bet_config),
            total_payout=format_decimal(spin_result.total_payout),
            remaining_coins=format_decimal(updated_user.coins),
            spin_count=updated_user.spin_count,
            cascade_sections=cascade_sections,
            latest_cascade=spin_result.cascades[-1],
            all_cascades=list(spin_result.cascades),
        ),
    )

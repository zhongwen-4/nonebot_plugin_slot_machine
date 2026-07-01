from nonebot import get_driver, on_command
from nonebot.adapters.milky.event import MessageEvent
from nonebot.plugin import PluginMetadata

from .database import initialize_risk_database
from .utils import get_suspension_message

__plugin_meta__ = PluginMetadata(
    name="老虎机风控",
    description="检测异常转账并封禁可疑账号一天。",
    usage="风控状态：查看当前账号是否被风控封号",
    homepage=(
        "https://github.com/zhongwen-4/nonebot_plugin_slot_machine/tree/main/"
        "nonebot_plugin_slot_machine/plugins/risk_control"
    ),
    type="application",
    supported_adapters={"~milky"},
)

risk_status = on_command("风控状态", block=True)


@get_driver().on_startup
async def startup_risk_control() -> None:
    await initialize_risk_database()


@risk_status.handle()
async def handle_risk_status(event: MessageEvent) -> None:
    account = event.get_user_id()
    message = await get_suspension_message(account)
    if message is not None:
        await risk_status.finish(message)

    await risk_status.finish("你的账号当前未被风控封号。")

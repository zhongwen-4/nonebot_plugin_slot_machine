from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from .database import (
    get_active_suspension,
    get_receiver_sender_count,
    get_sender_transfer_total,
    record_transfer,
    upsert_suspension,
)

TRANSFER_WINDOW_SECONDS = 600
SUSPENSION_SECONDS = 86400
LARGE_TRANSFER_THRESHOLD = Decimal(100)
RECEIVER_SENDER_THRESHOLD = 3


@dataclass(frozen=True)
class RiskDecision:
    suspended_accounts: tuple[str, ...]
    reason: str


def now_timestamp() -> int:
    return int(datetime.now(UTC).timestamp())


def format_remaining_time(seconds: int) -> str:
    minutes = max(seconds, 0) // 60
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} 小时 {minutes} 分钟"
    return f"{minutes} 分钟"


async def get_suspension_message(account: str) -> str | None:
    current_time = now_timestamp()
    suspension = await get_active_suspension(account, current_time)
    if suspension is None:
        return None

    remaining = format_remaining_time(suspension.suspended_until - current_time)
    return (
        "你的账号已被风控封号。\n"
        f"原因：{suspension.reason}\n"
        f"剩余时间：{remaining}"
    )


async def record_and_check_transfer_risk(
    sender_account: str,
    receiver_account: str,
    amount: Decimal,
) -> RiskDecision | None:
    current_time = now_timestamp()
    await record_transfer(
        sender_account,
        receiver_account,
        amount,
        current_time,
    )

    since = current_time - TRANSFER_WINDOW_SECONDS
    sender_total = await get_sender_transfer_total(
        sender_account,
        receiver_account,
        since,
    )
    if sender_total >= LARGE_TRANSFER_THRESHOLD:
        reason = "短时间内向同一账号大量转账"
        await upsert_suspension(
            sender_account,
            reason,
            current_time + SUSPENSION_SECONDS,
            current_time,
        )
        return RiskDecision((sender_account,), reason)

    sender_count = await get_receiver_sender_count(receiver_account, since)
    if sender_count >= RECEIVER_SENDER_THRESHOLD:
        reason = "短时间内多个账号向同一账号汇款"
        await upsert_suspension(
            receiver_account,
            reason,
            current_time + SUSPENSION_SECONDS,
            current_time,
        )
        return RiskDecision((receiver_account,), reason)

    return None

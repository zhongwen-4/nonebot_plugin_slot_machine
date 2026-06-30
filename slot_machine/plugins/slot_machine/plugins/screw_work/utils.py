from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from .database import ScrewWorkState


@dataclass(frozen=True)
class ScrewWorkMode:
    name: str
    coins_per_minute: int
    stamina_cost_per_minute: int


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


def settle_screw_work_state(
    state: ScrewWorkState,
    current_time: int,
) -> tuple[ScrewWorkState, Decimal, int]:
    elapsed = max(current_time - state.updated_at, 0)
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

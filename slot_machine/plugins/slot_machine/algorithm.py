from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from random import choice

from .constants import (
    ARG_PARTS_COUNT,
    BASE_BET,
    BET_SIZES,
    COLUMNS,
    MAX_MULTIPLIER,
    MIN_MULTIPLIER,
    PAYLINE_COLUMNS,
    ROWS,
    SYMBOLS,
    WILD_SYMBOL,
)
from .utils import format_decimal

PAYOUT_TABLE = {
    "A": {3: 50, 4: 100, 5: 150},
    "B": {3: 30, 4: 60, 5: 100},
    "C": {3: 20, 4: 40, 5: 80},
    "D": {3: 20, 4: 40, 5: 80},
    "E": {3: 10, 4: 25, 5: 60},
    "F": {3: 10, 4: 25, 5: 60},
    "G": {3: 8, 4: 15, 5: 30},
    "H": {3: 8, 4: 15, 5: 30},
}
MAX_BONUS_MULTIPLIER = 1024


class BetConfigError(ValueError):
    pass


@dataclass(frozen=True)
class BetConfig:
    bet_size: Decimal
    multiplier: int
    total_bet: Decimal


@dataclass(frozen=True)
class WinMatch:
    symbol: str
    columns: int
    payout_points: int
    hit_positions: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class CascadeResult:
    board: list[list[str]]
    highlighted_positions: frozenset[tuple[int, int]]
    bonus_multiplier: int
    payout: Decimal


@dataclass(frozen=True)
class SpinResult:
    final_board: list[list[str]]
    cascades: tuple[CascadeResult, ...]
    total_payout: Decimal


def generate_board() -> list[list[str]]:
    return [[choice(SYMBOLS) for _ in range(COLUMNS)] for _ in range(ROWS)]


def calculate_total_bet(bet_size: Decimal, multiplier: int) -> Decimal:
    return bet_size * Decimal(multiplier) * Decimal(BASE_BET)


def parse_bet_size(raw_value: str) -> Decimal:
    try:
        bet_size = Decimal(raw_value)
    except InvalidOperation as exc:
        raise BetConfigError from exc

    if bet_size not in BET_SIZES:
        raise BetConfigError
    return bet_size


def parse_multiplier(raw_value: str) -> int:
    try:
        multiplier = int(raw_value)
    except ValueError as exc:
        raise BetConfigError from exc

    if not MIN_MULTIPLIER <= multiplier <= MAX_MULTIPLIER:
        raise BetConfigError
    return multiplier


def parse_bet_config(raw_args: str) -> BetConfig:
    parts = raw_args.split()
    if len(parts) != ARG_PARTS_COUNT:
        raise BetConfigError

    bet_size = parse_bet_size(parts[0])
    multiplier = parse_multiplier(parts[1])
    total_bet = calculate_total_bet(bet_size, multiplier)
    return BetConfig(
        bet_size=bet_size,
        multiplier=multiplier,
        total_bet=total_bet,
    )


def format_bet_summary(bet_config: BetConfig) -> str:
    return (
        f"投注大小：{format_decimal(bet_config.bet_size)} 金币\n"
        f"投注倍数：{bet_config.multiplier} 倍\n"
        f"基础投注：{BASE_BET} 点\n"
        f"投注总额：{format_decimal(bet_config.total_bet)} 金币"
    )


def find_matches(board: list[list[str]]) -> list[WinMatch]:
    matches: list[WinMatch] = []

    for symbol in SYMBOLS:
        if symbol == WILD_SYMBOL:
            continue

        matched_columns = 0
        hit_positions: list[tuple[int, int]] = []

        for column_index in range(COLUMNS):
            column_hit = find_column_hit(board, column_index, symbol)
            if column_hit is None:
                break
            matched_columns += 1
            hit_positions.append(column_hit)

        if matched_columns >= PAYLINE_COLUMNS:
            payout_columns = min(matched_columns, max(PAYOUT_TABLE[symbol]))
            matches.append(
                WinMatch(
                    symbol=symbol,
                    columns=matched_columns,
                    payout_points=PAYOUT_TABLE[symbol][payout_columns],
                    hit_positions=tuple(hit_positions),
                )
            )

    return matches


def find_column_hit(
    board: list[list[str]], column_index: int, symbol: str
) -> tuple[int, int] | None:
    for row_index in range(ROWS):
        if board[row_index][column_index] == symbol:
            return (row_index, column_index)

    for row_index in range(ROWS):
        if board[row_index][column_index] == WILD_SYMBOL:
            return (row_index, column_index)

    return None


def collapse_board(
    board: list[list[str]], positions_to_remove: set[tuple[int, int]]
) -> list[list[str]]:
    columns: list[list[str]] = []

    for column_index in range(COLUMNS):
        survivors = [
            board[row_index][column_index]
            for row_index in range(ROWS)
            if (row_index, column_index) not in positions_to_remove
        ]
        refill_count = ROWS - len(survivors)
        columns.append([choice(SYMBOLS) for _ in range(refill_count)] + survivors)

    return [
        [columns[column_index][row_index] for column_index in range(COLUMNS)]
        for row_index in range(ROWS)
    ]


def calculate_match_payout(
    bet_config: BetConfig, payout_points: int, bonus_multiplier: int
) -> Decimal:
    return (
        bet_config.bet_size
        * Decimal(bet_config.multiplier)
        * Decimal(payout_points)
        * Decimal(bonus_multiplier)
    )


def resolve_spin(bet_config: BetConfig) -> SpinResult:
    working_board = generate_board()
    cascades: list[CascadeResult] = []
    total_payout = Decimal(0)
    bonus_multiplier = 1

    while True:
        matches = find_matches(working_board)
        if not matches:
            break

        highlighted_positions = {
            position
            for match in matches
            for position in match.hit_positions
        }
        cascade_payout = sum(
            calculate_match_payout(bet_config, match.payout_points, bonus_multiplier)
            for match in matches
        )
        total_payout += cascade_payout

        cascades.append(
            CascadeResult(
                board=[row[:] for row in working_board],
                highlighted_positions=frozenset(highlighted_positions),
                bonus_multiplier=bonus_multiplier,
                payout=Decimal(cascade_payout),
            )
        )

        working_board = collapse_board(working_board, highlighted_positions)
        bonus_multiplier = min(bonus_multiplier * 2, MAX_BONUS_MULTIPLIER)

    return SpinResult(
        final_board=[row[:] for row in working_board],
        cascades=tuple(cascades),
        total_payout=total_payout,
    )

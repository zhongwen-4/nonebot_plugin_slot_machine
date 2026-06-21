from decimal import Decimal
from pathlib import Path
from typing import Final

from nonebot import require

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store

ROWS: Final[int] = 5
COLUMNS: Final[int] = 6
BASE_BET: Final[int] = 10
WILD_SYMBOL: Final[str] = "W"
TREASURE_SYMBOL: Final[str] = "S"
SYMBOLS: Final[tuple[str, ...]] = (
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    WILD_SYMBOL,
    TREASURE_SYMBOL,
)
PAYOUT_TABLE: Final[dict[str, dict[int, int]]] = {
    "A": {3: 50, 4: 100, 5: 150},
    "B": {3: 30, 4: 60, 5: 100},
    "C": {3: 20, 4: 40, 5: 80},
    "D": {3: 20, 4: 40, 5: 80},
    "E": {3: 10, 4: 25, 5: 60},
    "F": {3: 10, 4: 25, 5: 60},
    "G": {3: 8, 4: 15, 5: 30},
    "H": {3: 8, 4: 15, 5: 30},
}
REGISTRATION_REWARD: Final[Decimal] = Decimal(100)
DATABASE_PATH = store.get_plugin_data_file("slot_machine.db")
BASE_IMAGE_PATH: Final[Path] = Path(__file__).resolve().parent / "image" / "image.png"
GENERATED_IMAGE_DIR: Final[Path] = store.get_plugin_cache_dir() / "images"
GRID_LEFT: Final[int] = 381
GRID_TOP: Final[int] = 226
GRID_CELL_WIDTH: Final[int] = 96
GRID_CELL_HEIGHT: Final[int] = 68
GRID_CELL_GAP_X: Final[int] = 15
GRID_CELL_GAP_Y: Final[int] = 8

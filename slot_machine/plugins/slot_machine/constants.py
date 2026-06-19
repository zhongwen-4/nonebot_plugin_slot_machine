from decimal import Decimal
from pathlib import Path
from typing import Final

from nonebot import require

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store

ROWS: Final[int] = 5
COLUMNS: Final[int] = 6
PAYLINE_COLUMNS: Final[int] = 3
ARG_PARTS_COUNT: Final[int] = 2
CELL_WIDTH: Final[int] = 3
BASE_BET: Final[int] = 10
WILD_SYMBOL: Final[str] = "W"
SYMBOLS: Final[tuple[str, ...]] = ("A", "B", "C", "D", "E", "F", "G", "H", WILD_SYMBOL)
BET_SIZES: Final[tuple[Decimal, ...]] = (
    Decimal("0.02"),
    Decimal("0.2"),
    Decimal(1),
)
MIN_MULTIPLIER: Final[int] = 1
MAX_MULTIPLIER: Final[int] = 10
REGISTRATION_REWARD: Final[Decimal] = Decimal(100)
DATABASE_PATH = store.get_plugin_data_file("slot_machine.db")
TEMPLATE_PATH: Final[Path] = Path(__file__).resolve().parent / "templates"
BASE_IMAGE_PATH: Final[Path] = Path(__file__).resolve().parent / "image" / "image.png"
GENERATED_IMAGE_DIR: Final[Path] = store.get_plugin_data_dir() / "images"
GRID_LEFT: Final[int] = 381
GRID_TOP: Final[int] = 226
GRID_CELL_WIDTH: Final[int] = 96
GRID_CELL_HEIGHT: Final[int] = 68
GRID_CELL_GAP_X: Final[int] = 15
GRID_CELL_GAP_Y: Final[int] = 8

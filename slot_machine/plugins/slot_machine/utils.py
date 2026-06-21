from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from time import time
from typing import TYPE_CHECKING

from nonebot.adapters.milky import Message, MessageSegment
from nonebot.adapters.milky.event import MessageEvent
from PIL import Image, ImageDraw, ImageFont

from .constants import (
    BASE_IMAGE_PATH,
    COLUMNS,
    GENERATED_IMAGE_DIR,
    GRID_CELL_GAP_X,
    GRID_CELL_GAP_Y,
    GRID_CELL_HEIGHT,
    GRID_CELL_WIDTH,
    GRID_LEFT,
    GRID_TOP,
    ROWS,
    TREASURE_SYMBOL,
    WILD_SYMBOL,
)

if TYPE_CHECKING:
    from .algorithm import CascadeResult


@dataclass(frozen=True)
class SpinMessageContext:
    account: str
    total_bet: str
    total_payout: str
    remaining_coins: str
    all_cascades: list["CascadeResult"]


@dataclass(frozen=True)
class GeneratedSpinImage:
    path: Path
    data: bytes


def format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def get_sender_name(event: MessageEvent) -> str:
    if event.data.group_member is not None and event.data.group_member.card:
        return event.data.group_member.card
    if event.data.group_member is not None:
        return event.data.group_member.nickname
    if event.data.friend is not None and event.data.friend.remark:
        return event.data.friend.remark
    if event.data.friend is not None:
        return event.data.friend.nickname
    return "老虎机"


def build_forward_message(
    event: MessageEvent,
    context: SpinMessageContext,
    images: list[GeneratedSpinImage],
) -> Message:
    sender_name = get_sender_name(event)
    sender_id = int(context.account)
    nodes = [
        MessageSegment.node(
            sender_id,
            sender_name,
            Message(MessageSegment.image(raw=image.data)),
        )
        for image in images
    ]
    return Message(
        MessageSegment.forward(
            messages=nodes,
            title="老虎机中奖详情",
            preview=[
                f"账号：{context.account}",
                f"总派彩：{context.total_payout} 金币",
                f"剩余金币：{context.remaining_coins}",
                f"记录数量：{len(images)}",
            ],
            summary=f"共 {len(images)} 条记录",
            prompt="点击查看老虎机中奖详情",
        )
    )


async def draw_spin_result_image(
    context: SpinMessageContext,
    cascade: "CascadeResult",
    cascade_index: int | None = None,
) -> GeneratedSpinImage:
    image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    overlay_draw = ImageDraw.Draw(overlay)
    symbol_font = load_font(54)
    special_font = load_font(46)
    info_font = load_multiplier_font(44)
    footer_font = load_multiplier_font(20)

    for row_index, row in enumerate(cascade.board[:ROWS]):
        for column_index, symbol in enumerate(row[:COLUMNS]):
            box = get_cell_box(row_index, column_index)
            highlighted = (row_index, column_index) in cascade.highlighted_positions
            if highlighted:
                draw_highlight(overlay_draw, box)
            draw_symbol(
                draw,
                box,
                symbol,
                (
                    special_font
                    if symbol in (WILD_SYMBOL, TREASURE_SYMBOL)
                    else symbol_font
                ),
                highlighted=highlighted,
            )

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)
    draw_header(draw, cascade, info_font)
    draw_footer(draw, context, cascade, footer_font)

    GENERATED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (
        GENERATED_IMAGE_DIR
        / f"slot_{context.account}_{int(time() * 1000)}_{cascade_index or 0}.png"
    )
    image = image.convert("RGB")
    image.save(output_path, "PNG")

    buffer = BytesIO()
    image.save(buffer, "PNG")
    return GeneratedSpinImage(path=output_path, data=buffer.getvalue())


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_paths = (
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    )
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_multiplier_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_paths = (
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    )
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def get_cell_box(row_index: int, column_index: int) -> tuple[int, int, int, int]:
    left = GRID_LEFT + column_index * (GRID_CELL_WIDTH + GRID_CELL_GAP_X)
    top = GRID_TOP + row_index * (GRID_CELL_HEIGHT + GRID_CELL_GAP_Y)
    return left, top, left + GRID_CELL_WIDTH, top + GRID_CELL_HEIGHT


def draw_highlight(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(
        (left - 4, top - 4, right + 4, bottom + 4),
        radius=10,
        fill=(255, 211, 64, 90),
        outline=(255, 247, 153, 235),
        width=4,
    )
    draw.rounded_rectangle(
        (left + 5, top + 5, right - 5, bottom - 5),
        radius=8,
        outline=(255, 122, 36, 230),
        width=2,
    )


def draw_symbol(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    symbol: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    *,
    highlighted: bool,
) -> None:
    left, top, right, bottom = box
    text_box = draw.textbbox((0, 0), symbol, font=font, stroke_width=3)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    x = left + (right - left - text_width) / 2
    y = top + (bottom - top - text_height) / 2 - 5
    fill = get_symbol_fill(symbol)
    stroke = (95, 20, 0) if highlighted else (25, 0, 0)
    draw.text(
        (x, y),
        symbol,
        font=font,
        fill=fill,
        stroke_width=3,
        stroke_fill=stroke,
    )


def get_symbol_fill(symbol: str) -> tuple[int, int, int]:
    if symbol == WILD_SYMBOL:
        return (80, 235, 255)
    if symbol == TREASURE_SYMBOL:
        return (110, 255, 130)
    return (255, 235, 128)


def draw_header(
    draw: ImageDraw.ImageDraw,
    cascade: "CascadeResult",
    info_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    text = f"x{cascade.bonus_multiplier}"
    box = draw.textbbox((0, 0), text, font=info_font)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    x = 704 + (168 - text_width) / 2
    y = 128 + (58 - text_height) / 2 - box[1]
    draw.text((x, y), text, font=info_font, fill=(92, 28, 0))


def draw_footer(
    draw: ImageDraw.ImageDraw,
    context: SpinMessageContext,
    cascade: "CascadeResult",
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    text = (
        f"投注总额：{context.total_bet} 金币  "
        f"本次中奖：{format_decimal(cascade.payout)} 金币  "
        f"总共获得：{context.total_payout} 金币"
    )
    if cascade.awarded_free_spins:
        text = f"{text}  免费抽奖：+{cascade.awarded_free_spins} 次"
    if cascade.free_spin_index is not None:
        text = f"免费第 {cascade.free_spin_index} 次  {text}"

    draw.text(
        (458, 733),
        text,
        font=font,
        fill=(255, 228, 140),
        stroke_width=2,
        stroke_fill=(50, 0, 0),
    )

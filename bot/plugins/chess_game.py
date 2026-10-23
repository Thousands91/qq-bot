# -*- coding: utf-8 -*-
"""对棋 —— 群里下国际象棋（沙特兰兹皮）

开局：对棋 [@某人]（不 @ 则由下一位发言的人执黑）
走子：走 e4 / Nf3 / O-O（SAN）或 e2e4（UCI）
其他：认输 / 悔棋 / 结束棋局 / 棋局（看当前盘面）
每群同时一局，10 分钟没人动棋则下一手判负（懒判定，下次交互时结算）。
"""
import base64
import io
import time

import chess
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.params import CommandArg
from nonebot.typing import T_State
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

from pathlib import Path

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "DejaVuSans.ttf"
try:
    FONT = ImageFont.truetype(str(FONT_PATH), 46)
    FONT_SMALL = ImageFont.truetype(str(FONT_PATH), 18)
except OSError:
    FONT = FONT_SMALL = None

PIECE_CHARS = {
    chess.PAWN: "♟", chess.KNIGHT: "♞", chess.BISHOP: "♝",
    chess.ROOK: "♜", chess.QUEEN: "♛", chess.KING: "♚",
}
CELL = 72
MARGIN = 30
LIGHT = (240, 217, 181)
DARK = (181, 136, 99)
HL = (246, 246, 105)
SIZE = MARGIN * 2 + CELL * 8


def render_board(board: chess.Board) -> bytes:
    """渲染棋盘 PNG。视角：白方在下。"""
    img = Image.new("RGB", (SIZE, SIZE), (60, 44, 32))
    draw = ImageDraw.Draw(img)

    last = board.peek() if board.move_stack else None

    for rank in range(8):          # rank 7 在上
        for file in range(8):
            x = MARGIN + file * CELL
            y = MARGIN + rank * CELL
            sq = chess.square(file, 7 - rank)
            color = LIGHT if (file + rank) % 2 == 0 else DARK
            if last is not None and sq in (last.from_square, last.to_square):
                color = HL
            draw.rectangle([x, y, x + CELL, y + CELL], fill=color)

            piece = board.piece_at(sq)
            if piece:
                ch = PIECE_CHARS[piece.piece_type]
                # 白棋用白字黑描边，黑棋用黑字白描边
                fill = (255, 255, 255) if piece.color == chess.WHITE else (20, 20, 20)
                stroke = (20, 20, 20) if piece.color == chess.WHITE else (245, 245, 245)
                bbox = draw.textbbox((0, 0), ch, font=FONT)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text(
                    (x + (CELL - w) / 2 - bbox[0], y + (CELL - h) / 2 - bbox[1]),
                    ch, font=FONT, fill=fill, stroke_width=2, stroke_fill=stroke,
                )

    # 坐标标注
    for i in range(8):
        draw.text((MARGIN + i * CELL + CELL / 2 - 5, 6), "abcdefgh"[i],
                  font=FONT_SMALL, fill=(230, 220, 200))
        draw.text((MARGIN + i * CELL + CELL / 2 - 5, SIZE - 22), "abcdefgh"[i],
                  font=FONT_SMALL, fill=(230, 220, 200))
        draw.text((4, MARGIN + i * CELL + CELL / 2 - 10), str(8 - i),
                  font=FONT_SMALL, fill=(230, 220, 200))
        draw.text((SIZE - 16, MARGIN + i * CELL + CELL / 2 - 10), str(8 - i),
                  font=FONT_SMALL, fill=(230, 220, 200))

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def board_image_msg(board: chess.Board) -> Message:
    b64 = base64.b64encode(render_board(board)).decode()
    return Message(f"[CQ:image,file=base64://{b64}]")

# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------

GAMES: dict[int, dict] = {}   # group_id -> game
TIMEOUT = 10 * 60


def new_game(white_id: int, black_id: int) -> dict:
    return {
        "board": chess.Board(),
        "white": white_id,
        "black": black_id,
        "pending": None,        # 等待被 @ 者接下的 user_id
        "last_move_ts": time.time(),
        "history": [],          # 用于悔棋
    }


def game_over_text(board: chess.Board) -> str | None:
    if board.is_checkmate():
        return "将死。{}赢了，这局到这里。".format(
            "白方" if board.turn == chess.BLACK else "黑方")
    if board.is_stalemate():
        return "逼和，谁也没赢。"
    if board.is_insufficient_material():
        return "子力不足，和棋。"
    if board.is_fifty_moves():
        return "五十回合无进展，和棋。"
    if board.is_repetition(3):
        return "三次重复局面，和棋。"
    return None

# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------

start_cmd = on_command("对棋", priority=20, block=True)
move_cmd = on_command("走", priority=20, block=True)
view_cmd = on_command("棋局", priority=20, block=True)
resign_cmd = on_command("认输", priority=20, block=True)
undo_cmd = on_command("悔棋", priority=20, block=True)
end_cmd = on_command("结束棋局", aliases={"不下了"}, priority=20, block=True)


def gid_of(event: MessageEvent) -> int:
    return getattr(event, "group_id", 0) or event.user_id


async def _timeout_check(group_id: int) -> str | None:
    """懒判超时：超过 10 分钟没动棋，轮到谁走谁判负。"""
    g = GAMES.get(group_id)
    if not g or g["pending"]:
        return None
    if time.time() - g["last_move_ts"] <= TIMEOUT:
        return None
    loser = g["white"] if g["board"].turn == chess.WHITE else g["black"]
    del GAMES[group_id]
    return f"棋盘摆了十分钟没人落子，{at(loser)} 认负吧。这局散了。"


def at(user_id: int) -> str:
    return f"[CQ:at,qq={user_id}]"


INTRO = (
    "棋盘上，白在下方，列从左到右 a→h，行从下到上 1→8。\n"
    "走棋发：走 e4、走 Nf3、走 O-O（王车易位），或直接 走 e2e4。\n"
    "另有：棋局（看盘）、悔棋、认输、结束棋局。"
)


@start_cmd.handle()
async def _(bot, event: MessageEvent, state: T_State, arg: Message = CommandArg()):
    group_id = gid_of(event)
    if group_id in GAMES:
        await start_cmd.finish("棋盘已经摆上了，先下完这局。发「棋局」看盘。")
    at_seg = None
    for seg in arg:
        if seg.type == "at":
            at_seg = seg
            break
    if at_seg is None and event.message:
        for seg in event.message:
            if seg.type == "at" and str(seg.data.get("qq")) != str(event.self_id):
                at_seg = seg
                break

    if at_seg:
        opp = int(at_seg.data["qq"])
        if opp == event.user_id:
            await start_cmd.finish("自己跟自己下？您左手跟右手猜拳去吧。")
        g = new_game(event.user_id, opp)
        g["last_move_ts"] = time.time()
        GAMES[group_id] = g
        await start_cmd.finish(
            at(g["black"]) + " 执黑。" + at(g["white"]) + " 先走。\n" + INTRO
            + board_image_msg(g["board"])
        )
    else:
        g = new_game(event.user_id, None)
        g["pending"] = True
        GAMES[group_id] = g
        await start_cmd.finish(
            "棋盘摆上了，白方是" + at(event.user_id) +
            "。下一位说话的人执黑，报个「走 e4」之类的就算应下了。\n" + INTRO
        )


@view_cmd.handle()
async def _(bot, event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g or g["pending"]:
        await view_cmd.finish("桌上没有下到一半的棋。发「对棋」开局。")
    timeout_msg = await _timeout_check(group_id)
    if timeout_msg:
        await view_cmd.finish(timeout_msg)
    await view_cmd.finish(board_image_msg(g["board"]))


@move_cmd.handle()
async def _(bot, event: MessageEvent, arg: Message = CommandArg()):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g:
        await move_cmd.finish("没有摆着的棋。发「对棋」开局。")
    timeout_msg = await _timeout_check(group_id)
    if timeout_msg:
        await move_cmd.finish(timeout_msg)

    # 等待黑方认领：这条消息只算认领，不再尝试走子
    if g["pending"]:
        g["black"] = event.user_id
        g["pending"] = None
        await move_cmd.finish(
            "您执黑。" + at(g["white"]) + " 先走。")

    text = arg.extract_plain_text().strip()
    if not text:
        await move_cmd.finish("走哪？写个着法，比如「走 e4」。")

    board = g["board"]
    turn_uid = g["white"] if board.turn == chess.WHITE else g["black"]
    if event.user_id != turn_uid:
        who = "白方" if board.turn == chess.WHITE else "黑方"
        await move_cmd.finish("还没轮到您，这手是" + who + "的。")

    move = None
    try:
        move = board.parse_san(text)          # SAN：e4 / Nf3 / O-O
    except ValueError:
        try:
            move = chess.Move.from_uci(text.lower())   # UCI：e2e4
            if move not in board.legal_moves:
                move = None
        except ValueError:
            move = None
    if move is None:
        await move_cmd.finish("这步棋棋盘上走不通，换个着法。")

    g["history"].append((board.fen(), g["last_move_ts"]))
    board.push(move)
    g["last_move_ts"] = time.time()

    over = game_over_text(board)
    if over:
        del GAMES[group_id]
        await move_cmd.finish(board_image_msg(board) + over)
    elif board.is_check():
        await move_cmd.finish(
            board_image_msg(board)
            + "将军。该" + ("白方" if board.turn == chess.WHITE else "黑方") + "走。")
    else:
        await move_cmd.finish(
            board_image_msg(board)
            + "该" + ("白方" if board.turn == chess.WHITE else "黑方") + "走。")


@resign_cmd.handle()
async def _(bot, event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g or g["pending"]:
        await resign_cmd.finish("没有进行中的棋局。")
    if event.user_id not in (g["white"], g["black"]):
        await resign_cmd.finish("这盘棋没您的份，认什么输。")
    del GAMES[group_id]
    await resign_cmd.finish(at(event.user_id) + " 投子认负。这局到这里。")


@undo_cmd.handle()
async def _(bot, event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g or g["pending"] or not g["history"]:
        await undo_cmd.finish("没什么可悔的。")
    if event.user_id not in (g["white"], g["black"]):
        await undo_cmd.finish("这盘棋没您的份。")
    fen, ts = g["history"].pop()
    g["board"] = chess.Board(fen)
    g["last_move_ts"] = time.time()
    await undo_cmd.finish(board_image_msg(g["board"]) + "悔了一步，落子无悔下不为例。")


@end_cmd.handle()
async def _(bot, event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g:
        await end_cmd.finish("本来就没有棋局。")
    if event.user_id not in (g["white"], g["black"]) and g["pending"] is None:
        await end_cmd.finish("棋是别人的，别替人收。")
    del GAMES[group_id]
    await end_cmd.finish("棋收了。想下了再发「对棋」。")

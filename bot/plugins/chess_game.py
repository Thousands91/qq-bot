# -*- coding: utf-8 -*-
"""国际象棋 —— 群里下棋

开局：@机器人 说「对棋」，并 @ 一位对手（对手执黑，自己执白先走）
走子：走 e4 / Nf3 / O-O（SAN）或 e2e4（UCI）
其他：棋局（看盘）、悔棋（一步）、认输、结束棋局
每群同时一局，10 分钟没人动棋则下一手判负（下次交互时懒结算）。
"""
import base64
import io
import time
from pathlib import Path

import chess
from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.params import CommandArg
from nonebot.rule import Rule
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

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
                fill = (255, 255, 255) if piece.color == chess.WHITE else (20, 20, 20)
                stroke = (20, 20, 20) if piece.color == chess.WHITE else (245, 245, 245)
                bbox = draw.textbbox((0, 0), ch, font=FONT)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text(
                    (x + (CELL - w) / 2 - bbox[0], y + (CELL - h) / 2 - bbox[1]),
                    ch, font=FONT, fill=fill, stroke_width=2, stroke_fill=stroke,
                )

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

GAMES: dict[int, dict] = {}
TIMEOUT = 10 * 60


def new_game(white_id: int, black_id: int) -> dict:
    return {
        "board": chess.Board(),
        "white": white_id,
        "black": black_id,
        "last_move_ts": time.time(),
        "history": [],
    }


def gid_of(event: MessageEvent) -> int:
    return getattr(event, "group_id", 0) or event.user_id


def at(user_id: int) -> str:
    return f"[CQ:at,qq={user_id}]"


def game_over_text(board: chess.Board) -> str | None:
    if board.is_checkmate():
        return "将死，{}获胜！".format("白方" if board.turn == chess.BLACK else "黑方")
    if board.is_stalemate():
        return "逼和，平局。"
    if board.is_insufficient_material():
        return "子力不足，平局。"
    if board.is_fifty_moves():
        return "五十回合无进展，平局。"
    if board.is_repetition(3):
        return "三次重复局面，平局。"
    return None


def _timeout_text(group_id: int) -> str | None:
    g = GAMES.get(group_id)
    if not g:
        return None
    if time.time() - g["last_move_ts"] <= TIMEOUT:
        return None
    loser = g["white"] if g["board"].turn == chess.WHITE else g["black"]
    del GAMES[group_id]
    return f"超过 10 分钟没人落子，{at(loser)} 判负，本局结束。"

# ---------------------------------------------------------------------------
# 开局：@机器人 + 「对棋」，并 @ 一位对手
# ---------------------------------------------------------------------------

INTRO = (
    "白在下、黑在上。列从左到右 a→h，行从下到上 1→8。\n"
    "走棋发：走 e4、走 Nf3、走 O-O（王车易位），也可以走 e2e4。\n"
    "查盘面发「棋局」，另有悔棋、认输、结束棋局。"
)


async def _is_start(bot, event, state) -> bool:
    if not isinstance(event, MessageEvent):
        return False
    text = event.get_plaintext().strip()
    # @机器人后，bot 自己的 at 段已被框架剥掉，to_me 即代表 @过我
    if text not in ("对棋", "下棋"):
        return False
    return bool(getattr(event, "to_me", False))


start_cmd = on_message(rule=Rule(_is_start), priority=15, block=True)


@start_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    if group_id in GAMES:
        await start_cmd.finish("已经在下棋了，发「棋局」看盘面。")

    # 找对手：消息里除机器人外的第一个 @
    opp = None
    for seg in event.message:
        if seg.type == "at":
            qq = str(seg.data.get("qq"))
            if qq not in (str(event.self_id), str(event.user_id)):
                opp = int(qq)
                break
    if opp is None:
        await start_cmd.finish(
            "想下棋的话，@我 说「对棋」并 @ 一位对手。对手执黑，你执白先走。")

    g = new_game(event.user_id, opp)
    GAMES[group_id] = g
    await start_cmd.finish(
        "国际象棋开局。" + at(g["white"]) + " 执白先走，" + at(g["black"]) + " 执黑。\n"
        + INTRO + board_image_msg(g["board"]))

# ---------------------------------------------------------------------------
# 走子 / 看盘 / 悔棋 / 认输 / 结束
# ---------------------------------------------------------------------------

move_cmd = on_command("走", priority=20, block=True)
view_cmd = on_command("棋局", priority=20, block=True)
resign_cmd = on_command("认输", priority=20, block=True)
undo_cmd = on_command("悔棋", priority=20, block=True)
end_cmd = on_command("结束棋局", aliases={"不下了"}, priority=20, block=True)


@view_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g:
        await view_cmd.finish("现在没有棋局。")
    t = _timeout_text(group_id)
    if t:
        await view_cmd.finish(t)
    await view_cmd.finish(board_image_msg(g["board"]))


@move_cmd.handle()
async def _(event: MessageEvent, arg: Message = CommandArg()):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g:
        await move_cmd.finish("现在没有棋局。")
    t = _timeout_text(group_id)
    if t:
        await move_cmd.finish(t)

    text = arg.extract_plain_text().strip()
    if not text:
        await move_cmd.finish("走哪？例如：走 e4。")

    board = g["board"]
    turn_uid = g["white"] if board.turn == chess.WHITE else g["black"]
    if event.user_id != turn_uid:
        await move_cmd.finish("还没轮到你，这手是" +
                              ("白方" if board.turn == chess.WHITE else "黑方") + "的。")

    move = None
    try:
        move = board.parse_san(text)                     # e4 / Nf3 / O-O
    except ValueError:
        try:
            move = chess.Move.from_uci(text.lower())     # e2e4
            if move not in board.legal_moves:
                move = None
        except ValueError:
            move = None
    if move is None:
        await move_cmd.finish("这步走不通，换个着法。")

    g["history"].append((board.fen(), g["last_move_ts"]))
    board.push(move)
    g["last_move_ts"] = time.time()

    over = game_over_text(board)
    if over:
        del GAMES[group_id]
        await move_cmd.finish(board_image_msg(board) + over)
    elif board.is_check():
        await move_cmd.finish(
            board_image_msg(board) + "将军！该" +
            ("白方" if board.turn == chess.WHITE else "黑方") + "走。")
    else:
        await move_cmd.finish(
            board_image_msg(board) + "该" +
            ("白方" if board.turn == chess.WHITE else "黑方") + "走。")


@resign_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g:
        await resign_cmd.finish("现在没有棋局。")
    if event.user_id not in (g["white"], g["black"]):
        await resign_cmd.finish("这盘棋和你无关。")
    del GAMES[group_id]
    await resign_cmd.finish(at(event.user_id) + " 认输，本局结束。")


@undo_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g or not g["history"]:
        await undo_cmd.finish("现在没有可悔的棋。")
    if event.user_id not in (g["white"], g["black"]):
        await undo_cmd.finish("这盘棋和你无关。")
    fen, ts = g["history"].pop()
    g["board"] = chess.Board(fen)
    g["last_move_ts"] = time.time()
    await undo_cmd.finish(board_image_msg(g["board"]) + "悔了一步。")


@end_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g:
        await end_cmd.finish("现在没有棋局。")
    if event.user_id not in (g["white"], g["black"]):
        await end_cmd.finish("这盘棋和你无关。")
    del GAMES[group_id]
    await end_cmd.finish("棋局已结束。想再下就 @我 说「对棋」。")

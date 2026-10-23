# -*- coding: utf-8 -*-
"""国际象棋 —— 群里下棋

开局：第一位玩家 @机器人 说「国际象棋」占白方，第二位玩家 @机器人 说「国际象棋」接黑方，然后开下
走子：走 e4 / Nf3 / O-O（SAN）或 e2e4（UCI）
其他：悔棋（需对手同意）、认输、结束棋局
每群同时一局；超过 10 分钟没人落子，轮到谁走谁判负（下次交互时懒结算）。
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


def new_game(white_id: int) -> dict:
    return {
        "board": chess.Board(),
        "white": white_id,
        "black": None,          # 等第二位玩家来接
        "last_move_ts": time.time(),
        "history": [],
        "pending_undo": None,   # 请求悔棋的一方
    }


def gid_of(event: MessageEvent) -> int:
    return getattr(event, "group_id", 0) or event.user_id


def at(user_id: int) -> str:
    return f"[CQ:at,qq={user_id}]"


def side_name(board: chess.Board) -> str:
    return "白方" if board.turn == chess.WHITE else "黑方"


def game_over_text(board: chess.Board) -> str | None:
    if board.is_checkmate():
        return "将死，{}获胜！这盘棋收进账本里——赢得干净，输得也体面。".format(
            "白方" if board.turn == chess.BLACK else "黑方")
    if board.is_stalemate():
        return "逼和，平局。谁也没赢谁，账就两清了。"
    if board.is_insufficient_material():
        return "子力不足，平局。剩下的子谁也吃不动谁。"
    if board.is_fifty_moves():
        return "五十回合无进展，平局。僵成这样，不如都回去喝茶。"
    if board.is_repetition(3):
        return "三次重复局面，平局。翻来覆去走同一条路，生意要黄的。"
    return None


def _timeout_text(group_id: int) -> str | None:
    g = GAMES.get(group_id)
    if not g:
        return None
    if time.time() - g["last_move_ts"] <= TIMEOUT:
        return None
    if g["black"] is None:
        del GAMES[group_id]
        return "等了十分钟也没人来接棋，棋盘先收了。想下再 @我。"
    loser = g["white"] if g["board"].turn == chess.WHITE else g["black"]
    del GAMES[group_id]
    return (f"超过 10 分钟没人落子，{at(loser)} 判负，本局结束。"
            "店里的规矩：落子就得想着它。")

# ---------------------------------------------------------------------------
# 开局：两位玩家先后 @机器人 说「国际象棋」
# ---------------------------------------------------------------------------

INTRO = (
    "先说走法：「走 e4」的意思是把 e 列第 4 格的兵走到 e4 那个格——"
    "列从左到右是 a 到 h，行从下到上是 1 到 8，白方在下面。\n"
    "走马就是「走 Nf3」，王车易位是「走 O-O」。每走一步，我都把新棋盘画给您。\n"
    "不想下了可以「认输」或「结束棋局」；悔棋得对方点头才算数。"
)


async def _is_start(bot, event, state) -> bool:
    if not isinstance(event, MessageEvent):
        return False
    text = event.get_plaintext().strip()
    if text != "国际象棋":
        return False
    # @机器人后，bot 自己的 at 段已被框架剥掉，to_me 即代表 @过我
    return bool(getattr(event, "to_me", False))


start_cmd = on_message(rule=Rule(_is_start), priority=15, block=True)


@start_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)

    if g and g["black"] is not None:
        await start_cmd.finish(
            "棋盘上正下着呢，没空摆第二盘。要看牌面，翻上一步的图就行。")

    if g and g["black"] is None:
        # 第二位玩家接黑方
        if event.user_id == g["white"]:
            await start_cmd.finish(
                "您已经占下白棋了，黑棋得让别人来——去 @我 报「国际象棋」的事，交给您想下的人。")
        g["black"] = event.user_id
        g["last_move_ts"] = time.time()
        await start_cmd.finish(
            at(g["black"]) + " 来了正好，黑棋给您留着。\n"
            + at(g["white"]) + " 执白先行，下吧。\n" + INTRO
            + board_image_msg(g["board"]))

    # 第一位玩家占白方
    GAMES[group_id] = new_game(event.user_id)
    await start_cmd.finish(
        "棋盘摆好了。" + at(event.user_id) + " 执白。\n"
        "想下的人 @我 说一声「国际象棋」，黑棋就是他的。")

# ---------------------------------------------------------------------------
# 走子 / 悔棋 / 认输 / 结束
# ---------------------------------------------------------------------------

move_cmd = on_command("走", priority=20, block=True)
resign_cmd = on_command("认输", priority=20, block=True)
undo_cmd = on_command("悔棋", priority=20, block=True)
agree_undo_cmd = on_command("同意悔棋", priority=20, block=True)
end_cmd = on_command("结束棋局", aliases={"不下了"}, priority=20, block=True)


@move_cmd.handle()
async def _(event: MessageEvent, arg: Message = CommandArg()):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g:
        await move_cmd.finish("柜上没有摆着的棋。想下的话，@我 说「国际象棋」。")
    if g["black"] is None:
        await move_cmd.finish("还差一位执黑的，让他来 @我 报「国际象棋」。")
    t = _timeout_text(group_id)
    if t:
        await move_cmd.finish(t)

    text = arg.extract_plain_text().strip()
    if not text:
        await move_cmd.finish("走哪？比如「走 e4」，就是把 e 列第 4 格的子走到 e4。")

    board = g["board"]
    turn_uid = g["white"] if board.turn == chess.WHITE else g["black"]
    if event.user_id != turn_uid:
        await move_cmd.finish("别急，这手轮到" + side_name(board) + "走。")

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
        await move_cmd.finish("这步棋在盘上走不通，换个着法试试。")

    g["history"].append((board.fen(), g["last_move_ts"]))
    board.push(move)
    g["last_move_ts"] = time.time()
    g["pending_undo"] = None

    over = game_over_text(board)
    if over:
        del GAMES[group_id]
        await move_cmd.finish(board_image_msg(board) + over)
    elif board.is_check():
        await move_cmd.finish(
            board_image_msg(board) + "将军！轮到" + side_name(board) + "了。")
    else:
        await move_cmd.finish(
            board_image_msg(board) + "轮到" + side_name(board) + "。")


@resign_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g or g["black"] is None:
        await resign_cmd.finish("没有下到一半的棋，认什么输。")
    if event.user_id not in (g["white"], g["black"]):
        await resign_cmd.finish("这盘棋没您的份。")
    del GAMES[group_id]
    await resign_cmd.finish(
        at(event.user_id) + " 投子认负。棋和账一样，认了就翻篇，再来就是新的一局。")


@undo_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g or g["black"] is None:
        await undo_cmd.finish("没有摆着的棋。")
    if event.user_id not in (g["white"], g["black"]):
        await undo_cmd.finish("这盘棋没您的份。")
    if not g["history"]:
        await undo_cmd.finish("一手都还没走，悔什么。")
    if g["pending_undo"] and g["pending_undo"] != event.user_id:
        await undo_cmd.finish("已经有人在等对方点头了，您发「同意悔棋」或「结束棋局」都行。")
    g["pending_undo"] = event.user_id
    other = g["black"] if event.user_id == g["white"] else g["white"]
    await undo_cmd.finish(
        at(event.user_id) + " 想悔一步。" + at(other) + " 点头就发「同意悔棋」。"
        "按正经比赛的规矩这棋落了就不能悔，店里休闲，您俩商量着来。")


@agree_undo_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g or not g["pending_undo"]:
        await agree_undo_cmd.finish("没人悔棋，点哪门子头。")
    if event.user_id == g["pending_undo"]:
        await agree_undo_cmd.finish("自己不能答应自己，等对手发「同意悔棋」。")
    if event.user_id not in (g["white"], g["black"]):
        await agree_undo_cmd.finish("这盘棋没您的份。")
    fen, ts = g["history"].pop()
    g["board"] = chess.Board(fen)
    g["last_move_ts"] = time.time()
    g["pending_undo"] = None
    await agree_undo_cmd.finish(
        board_image_msg(g["board"]) + "悔了一步，接着来。下不为例啊。")


@end_cmd.handle()
async def _(event: MessageEvent):
    group_id = gid_of(event)
    g = GAMES.get(group_id)
    if not g:
        await end_cmd.finish("本来就没有棋局。")
    if g["black"] is None:
        if event.user_id != g["white"]:
            await end_cmd.finish("棋还没凑齐人，您急什么。")
    elif event.user_id not in (g["white"], g["black"]):
        await end_cmd.finish("棋是别人下的，别替人收。")
    del GAMES[group_id]
    await end_cmd.finish("棋收了。想下随时 @我 说「国际象棋」。")

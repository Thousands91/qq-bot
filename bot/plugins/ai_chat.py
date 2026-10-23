"""
AI 智能问答 —— 阿萨尔人格（《苏丹的游戏》书店老板）
@机器人 + 问题 → 以阿萨尔的身份作答

支持 OpenAI 兼容协议，可换国内服务：
- 硅基流动 https://cloud.siliconflow.cn (推荐，注册送额度)
- DeepSeek https://platform.deepseek.com
- 智谱 BigModel https://bigmodel.cn
- 字节豆包 https://www.volcengine.com/product/doubao
- 月之暗面 https://platform.moonshot.cn
"""
import os
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List

from nonebot import on_message
from nonebot.rule import command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, PrivateMessageEvent
from nonebot.typing import T_State

# 引入人格设定（bot/persona）
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from persona import AZAR_PERSONA
except ImportError:
    AZAR_PERSONA = "你扮演《苏丹的游戏》书店老板阿萨尔，博学、矜持、说话文雅简短。"

ENABLE = os.getenv("ENABLE_AI_CHAT", "true").lower() == "true"
API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
MODEL = os.getenv("OPENAI_MODEL", "Qwen/Qwen2.5-7B-Instruct")
MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "300"))
CONTEXT_LEN = int(os.getenv("AI_CONTEXT_LENGTH", "6"))
TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.85"))

# 对话上下文（按 (群号, 用户QQ) 缓存）
HISTORY: Dict[tuple, Deque[dict]] = defaultdict(lambda: deque(maxlen=CONTEXT_LEN))

# 群聊场合的补充约束
GROUP_HINT = (
    "\n\n## 当前场合（务必遵守）\n"
    "你在一个群里，有人直接问你话。\n"
    "**默认只说一句话**。对方问得多、或事情复杂，可以说两句；"
    "最多三句，绝不可再多。\n"
    "不铺垫、不总结、不分点、不用小标题、不要反问收尾。\n"
    "群友说话随便，你不必纠正，但要保持书商的身份。\n"
    "**不要主动科普苏丹卡、七日之期、百科全书**——那是你的底子，不是你的口头禅。"
    "只有对方问起，或者正好能说明一件事时，才提一句。\n"
    "讲起城里的谁，讲一件具体的小事，比讲他的身份有用。\n"
    "\n"
    "## 说话的腔调（务必遵守）\n"
    "- 日常闲聊就正常接话，问候就好好问候，别硬塞卡牌、折卡这些词。\n"
    "- 只有话题本身沾到这个世界（卡牌、王城、城中的人和事）时，才以当事人、"
    "旁观者的口吻聊，细节取自你的人设，像住在这里的人随口讲，不是介绍设定。\n"
    "- 听来的事要标明是听来的：「这话是听来的，我没亲见，不写进册子。」\n"
    "- 有人问危险的事（折卡、弑君、逃亡），你不入局，也不出主意，可以转述别人怎么做。\n"
    "- 语气克制、带点自嘲的清醒，不热血不中二，不卖惨。"
)

SYSTEM_PROMPT = AZAR_PERSONA + GROUP_HINT

# ============ 吃 / 喝：模型容易把"吃什么"答成菜单，这里兜一层 ============
# 识别到这类问法，就从原作清单里随机抽一样，塞进提示里让模型顺着说。
EAT_WORDS = (
    "吃什么", "吃啥", "吃点什么", "吃点啥", "吃哪个", "吃的", "点吃的", "来点吃",
    "推荐吃", "有什么吃", "有啥吃", "吃推荐", "饿了", "好饿", "早饭", "午饭", "晚饭", "夜宵", "宵夜",
)
DRINK_WORDS = (
    "喝什么", "喝啥", "喝点什么", "喝点啥", "喝哪个", "喝的", "点喝的", "来点喝",
    "推荐喝", "有什么喝", "有啥喝", "喝推荐", "渴了", "好渴",
)

# 吃食两张表：现世的多，原作的少（原作那些是点缀，不是主菜）
# —— 现世的：按门类分组，想加东西直接往对应组里塞
FOODS_REAL = [
    # 面条
    "一碗牛肉面", "手擀炸酱面", "葱油拌面", "西红柿鸡蛋打卤面", "兰州拉面",
    "武汉热干面", "重庆小面", "一碗担担面", "山西刀削面", "biangbiang面",
    "油泼面", "阳春面", "一碗片儿川", "雪菜肉丝面", "一碗炝锅面",
    "新疆拌面", "岐山臊子面", "一碗云吞面", "牛杂面", "一碗牛腩粉",
    "螺蛳粉", "桂林米粉", "常德米粉", "一碗过桥米线", "砂锅米线",
    "一份炒河粉", "干炒牛河", "一份炒米粉", "一份炒面", "一份凉皮",
    "一碗酸辣粉", "一份肠粉",
    # 包子饺子饼
    "一碗馄饨", "鲜肉小笼包", "生煎包", "韭菜猪肉饺子", "三鲜锅贴",
    "一屉蒸饺", "一个肉包", "一个菜包", "一屉叉烧包", "一屉烧麦",
    "一个糖三角", "一份锅贴", "一个肉夹馍", "一个腊汁肉夹馍",
    "煎饼果子", "一个手抓饼", "一份鸡蛋灌饼", "几个烧饼", "一个葱油饼",
    "一份千层饼", "一个馅饼", "一份肉饼", "一个韭菜盒子", "一份春卷",
    "一份油条", "一个炸糕", "一个麻团",
    # 米饭
    "蛋炒饭", "扬州炒饭", "一份煲仔饭", "一份腊味饭", "黄焖鸡米饭",
    "一份卤肉饭", "猪脚饭", "一份盖浇饭", "一份炒饭",
    "一份手抓饭", "一份寿司", "一份饭团", "一份石锅拌饭",
    # 粥
    "皮蛋瘦肉粥", "小米粥配咸菜", "一锅白粥", "一碗八宝粥",
    "一碗南瓜粥", "一碗红枣粥", "一碗海鲜粥", "一碗粥配榨菜",
    # 硬菜 · 猪
    "红烧肉", "糖醋里脊", "回锅肉", "梅菜扣肉", "粉蒸肉",
    "红烧狮子头", "椒盐排骨", "酱大骨", "土豆烧排骨", "红烧猪蹄",
    "一份东坡肉", "一份蒜泥白肉", "一份锅包肉", "一份溜肉段",
    "炒猪肝", "一份肥肠", "一份毛血旺", "一份九转大肠",
    # 硬菜 · 牛羊
    "小炒黄牛肉", "番茄炖牛腩", "一锅羊蝎子", "涮羊肉", "一份手把肉",
    "一份牛肉锅", "一份牛排", "一份烤肉", "一份羊肉泡馍",
    "一份水盆羊肉", "一份羊汤", "土豆炖牛肉", "一份孜然羊肉",
    # 硬菜 · 鸡鸭鹅
    "宫保鸡丁", "白切鸡", "盐焗鸡", "可乐鸡翅", "辣子鸡",
    "大盘鸡", "一份黄焖鸡", "一份啤酒鸭", "一份烤鸭", "一份烧鹅",
    "一份卤鸭", "一份口水鸡", "一份文昌鸡", "一份鸡汤",
    # 硬菜 · 鱼虾
    "水煮鱼", "酸菜鱼", "一份烤鱼", "一盘糖醋鲤鱼", "一份干烧鱼",
    "清蒸鲈鱼", "一份红烧带鱼", "一份水煮肉片", "麻辣香锅",
    "一份小龙虾", "一份油焖大虾", "一份清蒸虾", "一份花甲",
    "一份炒蛤蜊", "一份生蚝", "一份鱿鱼", "铁板鱿鱼", "一份炸虾",
    # 硬菜 · 其他
    "一份红烧狗肉", "一份烤羊腿", "一份烤乳猪", "一份火腿",
    "一份香肠", "一份腊肉", "一份培根", "一份酱牛肉",
    # 素菜
    "一盘清炒时蔬", "蒜蓉西兰花", "凉拌黄瓜", "一份拍黄瓜", "拌木耳",
    "炒土豆丝", "地三鲜", "干煸豆角", "一盘小葱拌豆腐",
    "一盘麻婆豆腐", "一份家常豆腐", "一份虎皮青椒", "一份油焖茄子",
    "蒜蓉粉丝蒸扇贝", "一份炒空心菜", "一份炒青菜", "一份炒菠菜",
    "一份凉拌海带", "一份醋溜白菜", "一份炒蘑菇", "一份香菇油菜",
    # 汤
    "一碗紫菜蛋花汤", "番茄蛋汤", "排骨玉米汤", "一盅鸡汤", "一锅酸辣汤",
    "一碗冬瓜汤", "一碗萝卜汤", "一碗罗宋汤", "一锅老鸭汤",
    "一锅菌汤", "一碗胡辣汤", "一碗羊杂汤",
    # 火锅烧烤
    "一锅火锅", "一锅麻辣烫", "一锅冒菜", "一锅串串", "一份烤串",
    "一份烧烤", "一份铁板烧", "一锅东北乱炖", "一锅铁锅炖",
    # 街边速食
    "一份炸鸡", "汉堡薯条", "一份披萨", "一个热狗", "一份三明治",
    "一份沙拉", "一份卷饼", "一份薯条", "一份炸串", "一份炸鸡柳",
    "一份手抓饼加蛋", "一个烤红薯", "煮玉米", "一碗关东煮",
    "一份臭豆腐", "一碗豆腐脑", "一份炸豆腐", "一份烤冷面",
    "一份章鱼小丸子", "一份铁板豆腐", "一份鸡蛋仔", "一份鱼蛋",
    "一份凉面", "一份冰粉", "一份酸辣凉粉",
    # 异国菜
    "一份咖喱", "一份意面", "一份千层面", "一份披萨角", "一份汉堡",
    "一份墨西哥卷", "一份塔可", "一份冬阴功汤", "一份越南河粉",
    "一份韩式炸鸡", "一份部队锅", "一份泰式炒粉", "一份寿喜锅",
    "一份天妇罗", "一份拉面", "一份咖喱饭", "一份泡菜锅",
    # 点心甜品
    "一块桂花糕", "一碗双皮奶", "一份糖水", "一份刨冰", "一个冰淇淋",
    "一块芝士蛋糕", "一块巧克力", "一份提拉米苏", "一份布丁",
    "一份蛋挞", "一份泡芙", "一份甜甜圈", "一份华夫饼", "一份松饼",
    "一碗红豆沙", "一碗芝麻糊", "一份叉烧酥", "一份月饼",
    "一份汤圆", "一份粽子", "一份年糕", "一块桃酥",
    # 水果坚果
    "几颗草莓", "一盘切好的西瓜", "两个橘子", "一个苹果", "一根香蕉",
    "一串葡萄", "半个哈密瓜", "几个荔枝", "一个石榴", "几个山竹",
    "几个芒果", "几个猕猴桃", "一把樱桃", "一个梨", "一个柚子",
    "一碗现熬的银耳羹",
    # 干粮零嘴
    "一块干面包", "一块硬饼", "一把坚果", "一份肉脯", "一包饼干",
    "一份薯片", "一把瓜子", "一份锅巴", "一碗泡面",
]

# —— 原作里的：36 道大餐 + 俺寻思那一栏的面疙瘩
FOODS_GAME = [
    "国王烤肉", "饼夹一切", "蜂蜜蛋饼", "禽肉炒蘑菇", "老派花园大餐",
    "仙人掌蛋糕", "熏狮子全餐", "手抓鳄鱼饭", "烤全驼", "荒野一锅炖",
    "草药炖大雁", "生命布丁", "圣餐饼", "精力套餐",
    "八宝犀牛", "驴肉火烧", "游猎沙威玛", "辣子鸡丁", "香烤肥鸽",
    "泉水牛肉", "空壳酿肉", "眼球花馕", "咬人馍", "美味家常菜",
    "特制佳肴", "妙妙糊糊", "盐烤牛心", "油炸河鲜", "细鳞鱼干",
    "麻辣蛇脖", "稀有的肉干", "黑街面疙瘩",
]

FOODS = FOODS_REAL + FOODS_GAME

# 饮品同理
DRINKS_REAL = [
    # 茶
    "一杯热茶", "一杯凉白开", "一壶普洱", "一杯龙井", "一杯菊花茶",
    "一杯铁观音", "一杯大红袍", "一杯茉莉花茶", "一壶奶茶", "一杯抹茶",
    "一杯柠檬茶", "一杯蜂蜜柚子茶", "一杯罗汉果茶", "一杯大麦茶",
    "一杯薄荷茶", "一杯乌龙茶", "一杯白茶", "一壶砖茶",
    # 咖啡
    "一杯冰美式", "一杯拿铁", "一杯卡布奇诺", "一杯摩卡", "一杯手冲",
    "一杯浓缩", "一杯澳白", "一杯冷萃", "一杯速溶咖啡",
    # 汽水果汁
    "一罐可乐", "一瓶冰汽水", "一罐雪碧", "一瓶苏打水", "一瓶能量饮料",
    "一杯柠檬水", "一杯鲜榨橙汁", "一杯西瓜汁", "一杯苹果汁",
    "一杯葡萄汁", "一杯甘蔗汁", "一杯椰子水", "一杯芒果汁",
    "一杯番茄汁", "一杯酸梅汤", "一杯绿豆汤", "一杯乌梅汁",
    # 奶制品
    "一杯热牛奶", "一杯酸奶", "一杯豆浆", "一杯豆奶", "一杯杏仁露",
    "一杯热可可", "一杯奶昔", "一杯奶茶",
    # 酒
    "一罐啤酒", "一瓶精酿", "一小杯白酒", "一杯米酒", "一杯黄酒",
    "一杯红酒", "一杯威士忌", "一杯伏特加", "一杯清酒", "一杯梅酒",
    "一杯鸡尾酒", "一杯金汤力", "一杯朗姆", "一杯龙舌兰",
    # 其他
    "一杯姜茶", "一杯温水", "一杯冰糖雪梨", "一杯热蜂蜜水",
]

DRINKS_GAME = [
    "奈费勒的无名窖藏", "烈焰之酒", "骷髅泡酒", "暗夜之饮", "杀人汽水",
    "魅魔奶茶", "一壶淡茶",
]

DRINKS = DRINKS_REAL + DRINKS_GAME

_pick_cache: Dict[tuple, list] = {}


def pick_food_or_drink(text: str, key: tuple) -> str:
    """看问的是吃还是喝，抽一样；同一句话重复问不会抽到同一个。

    现世的家常东西占大头，原作的吃食只占一小撮——书里那些菜是点缀，
    不能让人问一句"吃什么"，十回有八回端出烤全驼来。
    """
    import random

    is_drink = any(w in text for w in DRINK_WORDS)
    is_eat = any(w in text for w in EAT_WORDS)
    if not (is_drink or is_eat):
        return ""

    if is_drink:
        real, game = DRINKS_REAL, DRINKS_GAME
    else:
        real, game = FOODS_REAL, FOODS_GAME

    # 最近抽过的三样先躲开，免得"骷髅泡酒"连着端上来三次
    recent = _pick_cache.get(key, [])
    choice = ""
    for _ in range(12):
        # 四分之一的机会翻到书里那一栏
        pool = game if random.random() < 0.25 else real
        choice = random.choice(pool)
        if choice not in recent:
            break
    _pick_cache[key] = (recent + [choice])[-3:]
    return choice

ai_chat = on_message(priority=99, block=False)


@ai_chat.handle()
async def _(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, state: T_State):
    if not ENABLE:
        return

    private = isinstance(event, PrivateMessageEvent)
    # 私聊里每条消息都算"对它说"；群聊里只认 @
    if not private and not event.is_tome():
        return

    # 没配 Key：群里 @ 了要吭一声（否则像机器人死了）；
    # 私聊则保持沉默——每句话都回"没添油"太烦人
    if not API_KEY:
        if not private:
            await ai_chat.finish(
                Message("（他把书合上）我这会儿说不了话——柜上还没给灯添油。先翻翻别的吧。")
            )
        return

    text = event.get_plaintext().strip()
    if not text:
        await ai_chat.finish(Message("我在。您有什么要说给我听？📖"))

    # 斜杠命令交给专门插件处理
    if text.startswith(("/", "!", "！")):
        return

    # 私聊没有群号，记忆桶用 0 占位
    key = (getattr(event, "group_id", 0), event.user_id)
    msgs: List[dict] = HISTORY[key]

    # 问吃/喝的：先抽好一样，塞进这一轮的提示里，免得模型报菜单。
    # 注意 hint 只发给模型，不进 HISTORY——否则后面每轮都带着"（提醒：…）"，
    # 模型会一直以为对方还在点菜。
    picked = pick_food_or_drink(text, key)
    if picked:
        hint = f"{text}\n\n（提醒：对方是让你挑一样。这一样就定作「{picked}」，直接说它，别报菜单。）"
        to_model = list(msgs) + [{"role": "user", "content": hint}]
    else:
        to_model = list(msgs) + [{"role": "user", "content": text}]

    # finish() 是靠抛 FinishedException 结束的，不能包在 try 里，
    # 否则会被下面的 except 截下来再补一句"灯灭了"。
    try:
        answer = await call_llm(to_model)
    except Exception as e:
        await ai_chat.finish(Message(f"（书页翻到一半，灯灭了）{type(e).__name__}\n请检查 API Key 或网络"))
        return

    # 硬性截断：最多三句（模型不听话时兜底）。
    # 先进历史再截断的话，历史里存的是"用户没看见的那半句"，
    # 后面追问时模型会以为自己说过——所以先截断，存和发用同一份。
    answer = trim_to_sentences(answer, max_sentences=3)

    msgs.append({"role": "user", "content": text})
    msgs.append({"role": "assistant", "content": answer})

    await ai_chat.finish(Message(answer))


def trim_to_sentences(text: str, max_sentences: int = 3) -> str:
    """按中文/英文句末标点切句，超出部分丢弃。"""
    import re

    text = text.strip()
    if not text:
        return text

    # 按句末标点切分（保留标点）
    parts = re.findall(r"[^。！？!?…\n]+[。！？!?…]*", text)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) <= max_sentences:
        return text

    kept = "".join(parts[:max_sentences])
    # 补一个句号，避免结尾悬空
    if kept and kept[-1] not in "。！？!?…":
        kept += "。"
    return kept


async def call_llm(messages: List[dict]) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    resp = await client.chat.completions.create(
        model=MODEL,
        messages=full_messages,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    return (resp.choices[0].message.content or "").strip()


# 清空对话记忆
clear = on_message(command("清空记忆", "重置记忆"), priority=10, block=True)


@clear.handle()
async def _(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    HISTORY.pop((getattr(event, "group_id", 0), event.user_id), None)
    await clear.finish("记忆已清空，重新谈吧。")


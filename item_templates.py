"""
item_templates.py - 物品模板库(纯函数,无 PyQt5 依赖)

职责:
- 从 JSON 文件加载模板(用户后续提供数据)
- 加载后存入内存 dict,运行时不再读盘
- 提供 get_template(item_id) / make_item_from_template(...) 给 GUI 调用

设计约束(用户 2026-06-19 拍板):
- 模板数据从 JSON 加载,但运行时只放内存,不写回 JSON
- 用户负责提供模板数据文件(后续单独约定路径)
- 未知 ID 拒绝新增,不允许编造模板
"""
import json
from pathlib import Path
from typing import Optional


# 内存模板 dict: { item_id(str 8位) -> template_dict }
_TEMPLATES: dict = {}

# 模板加载状态(防重复加载报错)
_LOADED: bool = False


# 41 字段 equipInfo 默认全 0 模板(供 make_item_from_template 深拷贝填充)
_EQUIP_INFO_BLANK = {
    'starEmpty': 0, 'star': 0, 'typeLv': 0,
    'req_lev': 0, 'req_str': 0, 'req_dex': 0,
    'req_luk': 0, 'req_int': 0,
    'pdd': 0, 'bdr': 0.0, 'igpddr': 0.0, 'mdd': 0.0,
    'req_jobs': [], 'action': [], 'action2': [],
    'bullet': 0, 'type': 0, 'classification': 0,
    'attackSpeed': 0, '_str': 0, '_dex': 0, '_luk': 0,
    '_int': 0, '_maxHP': 0, '_maxMP': 0,
    'attack': 0, 'magicPower': 0, 'defense': 0,
    'moveSpeed': 0, 'jumpForce': 0, 'allProp': 0.0,
    'tuc': 0, 'fixTimes': 0, 'goldenHammer': 0,
    'platinumHammer': 0, 'knockback': 0, 'bdR': 0,
    'imdR': 0, 'setItemID': '', 'mhpR': 0, 'mmpR': 0,
}


def load_from_json(path: Path) -> int:
    """
    从 JSON 文件加载模板到内存。

    JSON 格式:
        {
            "01372228": { "name": "...", "type": 4, "price": ..., "equipInfo": {...} },
            "02000005": { "name": "超级药水", "type": 2, ... },
            ...
        }

    返回加载的模板数。
    重复调用会清空旧模板后重新加载(用于 GUI 启动时单次加载)。
    """
    global _LOADED
    _TEMPLATES.clear()
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f'模板 JSON 顶层必须是 dict,实际是 {type(data).__name__}')
    for item_id, tpl in data.items():
        if not isinstance(item_id, str) or len(item_id) != 8:
            raise ValueError(f'模板 key 必须是 8 位字符串 ID,实际是 {item_id!r}')
        if not isinstance(tpl, dict):
            raise ValueError(f'模板 {item_id} 必须是 dict,实际是 {type(tpl).__name__}')
        _TEMPLATES[item_id] = tpl
    _LOADED = True
    return len(_TEMPLATES)


def load_inline_dict(templates: dict) -> int:
    """
    直接从 Python dict 加载模板(供单测 / 临时调试用,不依赖文件)。
    返回加载数。
    """
    _TEMPLATES.clear()
    for item_id, tpl in templates.items():
        if not isinstance(item_id, str) or len(item_id) != 8:
            raise ValueError(f'模板 key 必须是 8 位字符串 ID,实际是 {item_id!r}')
        _TEMPLATES[item_id] = tpl
    return len(_TEMPLATES)


def get_template(item_id: str) -> Optional[dict]:
    """按 ID 查模板,未找到返回 None。绝不抛异常。"""
    return _TEMPLATES.get(item_id)


def known_ids() -> list:
    """返回所有已知 ID 列表(供 GUI 下拉提示用)"""
    return sorted(_TEMPLATES.keys())


def count() -> int:
    """已加载模板数(供 GUI 状态栏显示)"""
    return len(_TEMPLATES)


def make_item_from_template(item_id: str, num: int = 1, slot_max: int = 999) -> Optional[dict]:
    """
    根据 ID 生成一个新物品 dict(含 num 和默认字段)。

    返回:
        - 找到模板:返回深拷贝后的新物品 dict,带 num/nowNum/position=-1(占位)
        - 找不到:返回 None

    异常:
        - num < 0 或 num > slot_max 抛 ValueError

    设计要点:
        - 深拷贝防止外部修改污染模板
        - equipInfo 字段如果模板里有就用模板的,没有就用全 0 默认
        - 不自动算 position(留给 caller 处理,避免位置冲突)
    """
    tpl = _TEMPLATES.get(item_id)
    if tpl is None:
        return None
    if num < 0:
        raise ValueError(f'num 不能为负: {num}')
    if num > slot_max:
        raise ValueError(f'num 超过上限 {slot_max}: {num}')

    # 浅拷贝顶层字段
    out = dict(tpl)
    # 深拷贝嵌套结构(避免外部改 out 影响模板)
    out['id'] = item_id
    out['num'] = num
    out['nowNum'] = num
    out['position'] = -1  # 占位,caller 必须改
    if 'equipInfo' in out and isinstance(out['equipInfo'], dict):
        out['equipInfo'] = dict(out['equipInfo'])
    else:
        out['equipInfo'] = dict(_EQUIP_INFO_BLANK)
    return out


def next_available_position(container: list) -> int:
    """
    在给定容器列表里找未用的最小 position(从 0 开始)。
    容器空时返回 0。

    注意:用户不能手动编辑 position(skill 设计稿 §2.2 明确),
    新增装备时由本函数自动算。
    """
    used = {it.get('position', -1) for it in container if isinstance(it, dict)}
    pos = 0
    while pos in used:
        pos += 1
    return pos
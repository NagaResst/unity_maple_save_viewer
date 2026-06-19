"""
item_db.py - 物品名称数据库(纯函数,无 PyQt5 依赖)

职责:
- 启动时从 items.json 加载到内存 {id: name} 字典
- 提供 get_name(item_id) 给 GUI 调用查中文名
- 加载失败绝不抛异常(主功能不能因为物品数据缺失而崩)

设计约束(用户 2026-06-19 拍板):
- 只加载 8 位 ID(过滤掉 3 位任务/NPC 物品)
- 只存 {id: name} 一对字段(不加载 items.json 的 24 个完整字段,省内存)
- 加载失败时 get_name() 返回 None,GUI 端显示 ID 占位
- 不写回 JSON(用户规则:"不要直接以 json 形式落盘")
"""
import json
from pathlib import Path
from typing import Optional


# 内存数据库:{ 8位ID -> 中文名 }
_DB: dict = {}

# 加载状态标志(防止 GUI 启动时反复调)
_LOADED: bool = False
_LOAD_ERROR: str = ''
_LOADED_COUNT: int = 0


def load_from_json(path: Path) -> int:
    """
    从 items.json 加载到内存。

    行为:
    - 成功:返回加载的物品数(只算 8 位 ID),_LOADED=True
    - 失败:返回 0,_LOADED=False,_LOAD_ERROR=错误信息
    - 绝不抛异常(主功能容错)

    JSON 格式(items.json 是 list of dict):
        [
            {"ID": "01302000", "NAME": "剑", ...},
            {"ID": "01302002", "NAME": "海盗剑", ...},
            ...
        ]
    """
    global _LOADED, _LOAD_ERROR, _LOADED_COUNT
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            _LOAD_ERROR = f'items.json 顶层不是 list,是 {type(data).__name__}'
            _LOADED = False
            _LOADED_COUNT = 0
            return 0

        _DB.clear()
        for it in data:
            if not isinstance(it, dict):
                continue
            item_id = it.get('ID')
            name = it.get('NAME')
            # 只存 8 位 ID(过滤掉 3 位任务物品)
            if isinstance(item_id, str) and len(item_id) == 8 and isinstance(name, str):
                _DB[item_id] = name

        _LOADED = True
        _LOAD_ERROR = ''
        _LOADED_COUNT = len(_DB)
        return _LOADED_COUNT
    except Exception as e:
        _LOAD_ERROR = f'{type(e).__name__}: {e}'
        _LOADED = False
        _LOADED_COUNT = 0
        _DB.clear()
        return 0


def get_name(item_id: str) -> Optional[str]:
    """
    按 ID 查中文名。未找到或未加载返回 None。

    调用方必须能处理 None(Q1 A 选 "未命中只显示 ID"):
        name = get_item_name(it['id'])
        display = name if name else it['id']
    """
    return _DB.get(item_id)


def is_loaded() -> bool:
    """是否成功加载过(给状态栏/日志用)"""
    return _LOADED


def load_error() -> str:
    """加载失败时的错误信息(空字符串=无错误)"""
    return _LOAD_ERROR


def count() -> int:
    """已加载物品数"""
    return _LOADED_COUNT


def _reset_for_test():
    """测试用:清空内存数据库。仅供单测,不要在产品代码里调。"""
    global _LOADED, _LOAD_ERROR, _LOADED_COUNT
    _DB.clear()
    _LOADED = False
    _LOAD_ERROR = ''
    _LOADED_COUNT = 0
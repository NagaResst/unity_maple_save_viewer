"""
item_db.py - 物品名称数据库(纯函数,无 PyQt5 依赖)

职责:
- 启动时加载物品数据到内存 {id: name} 字典
- 提供 get_name(item_id) 给 GUI 调用查中文名
- 加载失败绝不抛异常(主功能不能因为物品数据缺失而崩)

数据来源(2026-06-19 用户拍板):
- 用 Python 模块 item_data.py(由 gen_data.py 从 items.json 生成)
- 直接 import,无 JSON 解析开销,git diff 可读

设计约束:
- 只加载 8 位 ID(过滤掉 3 位任务/NPC 物品)
- 只存 {id: name} 一对字段(不加载 items.json 的 24 个完整字段,省内存)
- 加载失败时 get_name() 返回 None,GUI 端显示 ID 占位
- 不写回 JSON(用户规则:"不要直接以 json 形式落盘")
"""
from typing import Optional


# 内存数据库:{ 8位ID(str) -> 中文名(str) }
_DB: dict = {}

# 加载状态标志(防止 GUI 启动时反复调)
_LOADED: bool = False
_LOAD_ERROR: str = ''
_LOADED_COUNT: int = 0


def load_from_dict(items_dict: dict, source_name: str = '<inline>') -> int:
    """
    从 Python dict 加载(主路径,2026-06-19 新增)。

    期望格式(跟 item_data.ITEMS 一致):
        {
            '01302000': {'NAME': '剑', 'TYPE': '1', 'EQUIPTYPE': '17'},
            ...
        }

    行为:
    - 成功:返回条目数,_LOADED=True
    - 失败:返回 0,_LOADED=False,_LOAD_ERROR=错误信息(但绝不抛异常)

    只采纳 8 位字符串 key + 含 NAME 字符串 value 的条目,其他跳过。
    """
    global _LOADED, _LOAD_ERROR, _LOADED_COUNT
    try:
        if not isinstance(items_dict, dict):
            _LOAD_ERROR = f'{source_name} 不是 dict,是 {type(items_dict).__name__}'
            _LOADED = False
            _LOADED_COUNT = 0
            return 0

        _DB.clear()
        for item_id, v in items_dict.items():
            if not isinstance(item_id, str) or len(item_id) != 8:
                continue
            if isinstance(v, dict) and isinstance(v.get('NAME'), str):
                _DB[item_id] = v['NAME']
            elif isinstance(v, str):  # 兼容纯字符串 dict(如测试场景)
                _DB[item_id] = v

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
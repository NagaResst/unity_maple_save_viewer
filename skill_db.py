"""
skill_db.py - 技能名称数据库(纯函数,无 PyQt5 依赖)

跟 item_db.py 平行设计,职责相同但数据结构不同:
- 技能 ID 是 int(可转换的)或 str(BOSS 技能的字符串 ID)
- 数据来源: skill_data.py(由 gen_data.py 从 form8_skill.json 生成)

API:
- load_from_dict(skills_dict):主加载路径,GUI 启动时调一次
- get_name(skill_id) -> Optional[str]:查中文名,ID 支持 int 和 str

容错跟 item_db 一致:加载失败不抛异常,get_name() 返回 None。
"""
from typing import Optional, Union


# 内存数据库:{ skill_id(int 或 str) -> 中文名(str) }
_DB: dict = {}

# 加载状态标志
_LOADED: bool = False
_LOAD_ERROR: str = ''
_LOADED_COUNT: int = 0


def load_from_dict(skills_dict: dict, source_name: str = '<inline>') -> int:
    """
    从 Python dict 加载(主路径)。

    期望格式(跟 skill_data.SKILLS 一致):
        {
            51: {'name': '普通攻击', 'jobs': ['0','1','2','3','4','5']},
            72: {'name': '普通射击', ...},
            'zakunLarm1Skill1': {'name': '扎昆左臂1技能1', ...},
            ...
        }

    key 可以是 int 或 str,value 必须是 dict 且含 'name' 字符串字段。
    """
    global _LOADED, _LOAD_ERROR, _LOADED_COUNT
    try:
        if not isinstance(skills_dict, dict):
            _LOAD_ERROR = f'{source_name} 不是 dict,是 {type(skills_dict).__name__}'
            _LOADED = False
            _LOADED_COUNT = 0
            return 0

        _DB.clear()
        for sid, v in skills_dict.items():
            # key 只接受 int 或 str
            if not isinstance(sid, (int, str)):
                continue
            # value 是 dict + 含 NAME 字符串字段(2026-06-19 统一大写规范)
            if isinstance(v, dict) and isinstance(v.get('NAME'), str):
                _DB[sid] = v['NAME']
            elif isinstance(v, dict) and isinstance(v.get('name'), str):
                # 兼容旧小写 key(过渡期)
                _DB[sid] = v['name']
            elif isinstance(v, str):  # 兼容纯字符串 dict
                _DB[sid] = v

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


def get_name(skill_id: Union[int, str]) -> Optional[str]:
    """
    按 ID 查技能中文名。ID 支持 int 和 str。

    调用方:玩家存档里的 id 字段是字符串(可能带前导 0),调用前要 int()
            name = get_skill_name(int(s['id']))
            display = name if name else s['id']

    未找到返回 None。
    """
    return _DB.get(skill_id)


def is_loaded() -> bool:
    return _LOADED


def load_error() -> str:
    return _LOAD_ERROR


def count() -> int:
    return _LOADED_COUNT


def _reset_for_test():
    """测试用:清空内存数据库。仅供单测,不要在产品代码里调。"""
    global _LOADED, _LOAD_ERROR, _LOADED_COUNT
    _DB.clear()
    _LOADED = False
    _LOAD_ERROR = ''
    _LOADED_COUNT = 0
"""
save_codec.py - 存档编解码核心模块
纯函数,不依赖 PyQt5,可独立单测
"""
import json
from typing import Optional


# 硬编码两种存档的 XOR 密钥
KEY_ROLE_INFO = 0x9F
KEY_PLAYER = 0x77

# 文件名 → (kind, key) 映射
_KIND_ROLE_INFO = 'role_info'
_KIND_PLAYER = 'player'


def classify(filename: str) -> Optional[tuple]:
    """根据文件名识别存档类型,返回 (kind, key) 或 None"""
    if filename == 'RoleInfo.json':
        return (_KIND_ROLE_INFO, KEY_ROLE_INFO)
    if filename.startswith('Player') and filename.endswith('.json'):
        return (_KIND_PLAYER, KEY_PLAYER)
    return None


def decode(raw: bytes, key: int) -> dict:
    """XOR 解密后 JSON 解析"""
    return json.loads(bytes(b ^ key for b in raw).decode('utf-8'))


def map_job_id(job_id: int) -> str:
    """
    职业 ID → 可读字符串(带转职推断)

    规则(基于 mem0 记录的冒险岛传统编码):
        0          = 新手(0 转)
        xx0        = 1 转
        xx1, xx2   = 2 转
        xx3        = 4 转
    后续你提供完整 ID 映射表后,改成查表,只改这一个函数
    """
    if job_id == 0:
        return f'{job_id} (新手)'
    tier = job_id % 10
    if tier == 0:
        return f'{job_id} (1 转)'
    if tier in (1, 2):
        return f'{job_id} (2 转)'
    if tier == 3:
        return f'{job_id} (4 转)'
    return f'{job_id}'


def bag_total(data: dict) -> int:
    """
    背包物品总数 = 5 个容器之和
    equips   = 背包里的装备
    consumes = 消耗品
    others   = 其他
    specials = 特殊
    fashions = 时装
    (nowEquips 是身上穿的,不算)
    """
    return (
        len(data.get('equips', [])) +
        len(data.get('consumes', [])) +
        len(data.get('others', [])) +
        len(data.get('specials', [])) +
        len(data.get('fashions', []))
    )


def killrecord_stats(data: dict) -> dict:
    """
    击杀记录统计
    返回 {'kinds': 怪物种类数, 'total': 击杀总数}
    """
    records = data.get('killrecordlist', []) or []
    return {
        'kinds': len(records),
        'total': sum(int(item.get('num', 0)) for item in records),
    }


def summarize_player(decoded: dict) -> str:
    """角色存档的一句话摘要,用于树节点和导入对话框"""
    name = decoded.get('name', '?')
    lev = decoded.get('lev', '?')
    return f'{name}·Lv{lev}'


def summarize_role_info(decoded: dict) -> str:
    """全局存档的一句话摘要"""
    roles = decoded.get('roles', []) or []
    last = decoded.get('lastLoadedId', '?')
    return f'{len(roles)} 角色 / 当前 {last}'

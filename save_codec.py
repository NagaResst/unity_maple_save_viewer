"""
save_codec.py - 存档编解码核心模块
纯函数,不依赖 PyQt5,可独立单测
"""
import json
import re
from typing import Optional


# 硬编码两种存档的 XOR 密钥
KEY_ROLE_INFO = 0x9F
KEY_PLAYER = 0x77

# 文件名 → (kind, key) 映射
_KIND_ROLE_INFO = 'role_info'
_KIND_PLAYER = 'player'

# 严格正则:
#   RoleInfo.json     — 账号全局
#   Player<digits>.json — 角色(数字至少 1 位,不带任何后缀/副本/空格)
_RE_PLAYER = re.compile(r'^Player\d+\.json$')


def classify(filename: str) -> Optional[tuple]:
    """根据文件名识别存档类型,返回 (kind, key) 或 None
    严格匹配:RoleInfo.json 或 Player<数字>.json,其他全部不识别"""
    if filename == 'RoleInfo.json':
        return (_KIND_ROLE_INFO, KEY_ROLE_INFO)
    if _RE_PLAYER.match(filename):
        return (_KIND_PLAYER, KEY_PLAYER)
    return None


def decode(raw: bytes, key: int) -> dict:
    """XOR 解密后 JSON 解析"""
    return json.loads(bytes(b ^ key for b in raw).decode('utf-8'))


def encode(obj: dict, key: int) -> bytes:
    """
    把 obj 序列化为紧凑 JSON,再用 key 异或加密,返回密文字节

    实现要点(skill 验证过):
    - 紧凑序列化 separators=(',', ':') 否则体积膨胀
    - ensure_ascii=False 保留中文(存档名"希尔"等)
    - 写盘前必须经此函数,不能直接 str(obj).encode() + XOR
    """
    plain = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return bytes(b ^ key for b in plain)


def map_job_id(job_id: int) -> str:
    """
    职业 ID → 字符串
    暂只返回原数字 ID,不做中文名映射
    后续你提供完整 ID 映射表后,改成查表(返回名字),只改这一个函数
    """
    return str(job_id)


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

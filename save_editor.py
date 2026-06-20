"""
save_editor.py - 存档编辑核心模块(纯函数,不依赖 PyQt5)
=========================================================

职责:
- 校验:字段值范围 / 武器脱下检查
- 应用:把编辑列表应用到内存 dict
- 落盘:原子写盘 (.tmp -> rename) + 自动 .bak 备份
- 容差:浮点字节差异 <0.1% 放行(memory 拍板)

数据模型:
- Edit = (path, value)
  path 支持:
    - 'lev' / 'coin' / 'currentExp'  (顶层)
    - 'attributes._maxHP' / 'attributes.attack'  (点路径)
    - 'skillPoint.3'  (list 索引)
    - 'nowSkills.5.level'  (list 元素字段)
- 现在只支持 batch 编辑,不做事务

设计约束(用户 2026-06-20 拍板):
- Q2: 武器判定严格 position == 11(Q3 阻止保存场景)
- Q3: 阻止保存 + 提示"请先在游戏里脱下武器再读档回来",不自动卸
- memory 拍板铁律:不可改字段锁死(attributes._str/_dex/_luk/_int 在客户端重算,
  UI 层要禁;这里只做 path 解析,锁死靠 caller)
- 批 2 范围:只支持 int / float / str 标量;list 整体替换不在批 2(留给批 3 增删装备)
"""
import copy
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

# 武器在 nowEquips 里的 position(用户 2026-06-20 拍板,Q2 严格相等)
# 注:具体 itemId 随存档而异(不同账号武器不同),仅 position 编号稳定 = 11
WEAPON_POSITION_IN_NOW_EQUIPS: int = 11

# 浮点字节差异容忍度(批 1.1 拍板,实际 0.004%)
FLOAT_BYTE_DIFF_TOLERANCE: float = 0.001  # 0.1%

# 字节差异硬上限(超过这个就完全拒绝,防止某处把整张表写坏)
BYTE_DIFF_HARD_LIMIT: float = 0.05  # 5%


# ============== 异常 ==============

class SaveEditError(Exception):
    """所有 save_editor 异常的基类"""


class FieldLockedError(SaveEditError):
    """尝试编辑被锁死的字段(attributes._str/_dex/_luk/_int / RoleInfo 等)"""


class InvalidPathError(SaveEditError):
    """Edit path 格式错误或指向不存在的 key"""


class InvalidValueError(SaveEditError):
    """字段值校验失败(类型错 / 范围越界)"""


class WeaponEquippedError(SaveEditError):
    """编辑四维/攻击力前需要先脱下武器(Q3 拍板)"""

    def __init__(self, weapon_position: int, weapon_item_id: Optional[str] = None):
        self.weapon_position = weapon_position
        self.weapon_item_id = weapon_item_id
        msg = (
            f'检测到身上穿着武器(position={weapon_position}'
            + (f', itemId={weapon_item_id}' if weapon_item_id else '')
            + ')。请先在游戏里脱下武器,再读档回来保存属性改动。'
        )
        super().__init__(msg)


# ============== Edit 数据类 ==============

@dataclass(frozen=True)
class Edit:
    """单条编辑: path -> value"""
    path: str
    value: Any

    def __post_init__(self):
        if not isinstance(self.path, str) or not self.path:
            raise InvalidPathError(f'path 必须是非空字符串,got {self.path!r}')


# ============== 字段锁死清单 ==============

# ⚠ P0 #1 + Smell #1 修复:用白名单代替黑名单
# 一切不在 ALLOWED_* 里的 path 都被拒(默认拒绝)
# 这能挡掉所有 "nowSkills.0" "nowEquips.0.attack" 等意外路径

# 顶层可改字段(白名单)
ALLOWED_TOP_PATHS = frozenset({
    'lev',           # 等级
    'coin',          # 金币
    'currentExp',    # 当前经验
})

# attributes.XXX 可改字段(白名单)
ALLOWED_ATTR_FIELDS = frozenset({
    # 战斗核心 6 项(memory 拍板 + 2026-06-20 拍板)
    '_maxHP', '_maxMP', 'attack', 'magicPower', 'attackSpeed', 'defense',
    # 战斗进阶 8 项
    'CriticalRate', 'CriticalDamage', 'percentDamage', 'finalDamage',
    'imdR', 'bdR', 'stanceProp', 'abilityPoint',
    # 当前状态(批 2.2 拍板,只展示)
    '_nowHP', '_nowMP', 'Mastery',
})

# 客户端重算,不能改(memory 拍板)
LOCKED_TOP_KEYS = frozenset({
    'RoleInfo.json',  # 顶层文件锁定
})

LOCKED_ATTR_FIELDS = frozenset({
    '_str', '_dex', '_luk', '_int',  # 四维客户端重算
    'name', 'job', 'baseJob', 'family', 'popularity',  # 顶层 attributes 的元数据
})

# 这 5 个键在客户端重算/锁定,UI 也不展示
LOCKED_TOP_PATH_PREFIXES = (
    'RoleInfo',
    'roleData',
    'objcetInfos',  # 原项目拼写错误
    'nowKeyCodes',
    'suitAttributes',
    'damage',  # 列表
    'equipInfo.',  # 嵌套子结构(批 3 之前不开放)
    'nowEquips',
    'nowSpecials',
    'attributes.suit',
    'attributes.panelOptions',
)

# skillPoint / nowSkills 走专门的格式校验(P0 #1 修复),不走白名单

# 编辑四维/攻击力时需要先脱武器(用户 2026-06-20 拍板)
# 严格匹配:_str/_dex/_luk/_int 全部四维,以及顶层 attack(attributes.attack)
WEAPON_GUARD_FIELDS = frozenset({
    'attributes._str',
    'attributes._dex',
    'attributes._luk',
    'attributes._int',
    'attributes.attack',
    'attributes.magicPower',  # 顺手护一下,魔法力跟武器攻击挂钩
})


# ============== 路径解析 ==============

def _parse_path(path: str) -> List[str]:
    """'a.b.0.c' -> ['a', 'b', '0', 'c']"""
    if not path:
        raise InvalidPathError('path 不能为空')
    parts = path.split('.')
    for p in parts:
        if not p:
            raise InvalidPathError(f'path 包含空段: {path!r}')
    return parts


def _get_nested(root: Any, path: str) -> Any:
    """取值,不存在返回 None"""
    parts = _parse_path(path)
    cur = root
    for p in parts:
        if isinstance(cur, list):
            try:
                idx = int(p)
            except ValueError:
                return None
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        elif isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
        if cur is None:
            return None
    return cur


def _set_nested(root: Any, path: str, value: Any) -> None:
    """
    就地写入。list 走 int index 自动扩,dict 缺 key 直接建。
    """
    parts = _parse_path(path)
    if len(parts) == 1:
        if not isinstance(root, dict):
            raise InvalidPathError(f'顶层 path 必须写到 dict,实际 {type(root).__name__}')
        root[parts[0]] = value
        return

    cur = root
    for i, p in enumerate(parts[:-1]):
        # 看下一段是数字 → list,否则 → dict
        next_p = parts[i + 1]
        is_next_list = next_p.isdigit()

        if isinstance(cur, list):
            idx = int(p)
            if idx < 0:
                raise InvalidPathError(f'list 索引不能为负: {idx}')
            while len(cur) <= idx:
                cur.append(None)
            if cur[idx] is None:
                cur[idx] = [] if is_next_list else {}
            cur = cur[idx]
        elif isinstance(cur, dict):
            # ⚠ P0 #2 修复:None 中间值歧义 — 显式 key 不存在 vs value=None
            if p not in cur:
                # key 缺失:自动建占位符
                cur[p] = [] if is_next_list else {}
            elif cur[p] is None:
                # key 存在但 value 是 None:拒绝,防静默改写结构
                raise InvalidPathError(
                    f'路径 {p!r} 在 dict 中已存在但 value=None,'
                    f'无法推断目标类型(list/dict)。请在调用前显式初始化。'
                )
            cur = cur[p]
        else:
            raise InvalidPathError(f'路径在非 dict/list 处中断: {p!r} in {parts}')

    last = parts[-1]
    if isinstance(cur, list):
        idx = int(last)
        if idx < 0:
            raise InvalidPathError(f'list 索引不能为负: {idx}')
        while len(cur) <= idx:
            cur.append(None)
        cur[idx] = value
    elif isinstance(cur, dict):
        cur[last] = value
    else:
        raise InvalidPathError(f'末段容器既不是 list 也不是 dict: {type(cur).__name__}')


# ============== 字段锁死校验 ==============

def _is_locked_path(path: str) -> bool:
    """返回 True 表示该 path 不可写"""
    if path in LOCKED_TOP_KEYS:
        return True
    if any(path.startswith(pref) for pref in LOCKED_TOP_PATH_PREFIXES):
        return True
    # attributes.XXX 里的四维
    if path.startswith('attributes.'):
        field = path[len('attributes.'):]
        if field in LOCKED_ATTR_FIELDS:
            return True
    return False


# 可编辑的容器及字段
EDITABLE_CONTAINERS = frozenset({
    'consumes', 'equips', 'others', 'specials', 'fashions',
})
EDITABLE_CONTAINER_FIELDS = frozenset({
    'num',      # 数量
})


def _is_container_edit_path(path: str) -> bool:
    """
    判断 path 是否是合法的容器编辑路径。
    合法格式: {container}.{index}.{field}
    例: consumes.0.num
    """
    parts = path.split('.')
    if len(parts) != 3:
        return False
    container, idx_str, field = parts
    if container not in EDITABLE_CONTAINERS:
        return False
    if not idx_str.isdigit():
        return False
    if field not in EDITABLE_CONTAINER_FIELDS:
        return False
    return True


# ============== 武器脱下检查 ==============

def check_no_weapon_equipped(
    data: dict,
    weapon_position: int = WEAPON_POSITION_IN_NOW_EQUIPS,
) -> Tuple[bool, Optional[str]]:
    """
    检查身上是否穿着武器(用户 2026-06-20 拍板 Q2 严格 position == 11)。

    返回 (ok, item_id):
    - ok=True 表示身上没穿武器,可以保存
    - ok=False 表示身上穿武器,item_id 是武器的 id(可能为 None)
    """
    now_equips = data.get('nowEquips', []) or []
    for it in now_equips:
        if it.get('position') == weapon_position:
            # 物品 id 字段可能叫 'id' (现在存档) 或 'itemId' (旧存档)
            iid = it.get('id') or it.get('itemId')
            iid_str = str(iid) if iid is not None else None
            return False, iid_str
    return True, None


# ============== 单字段校验 ==============

def validate_field(path: str, value: Any) -> None:
    """
    校验单个字段的 value 是否合法。失败抛 InvalidValueError / FieldLockedError。
    """
    # ⚠ P1 修复:显式拒 bool(isinstance(True, int) == True 会让 QCheckBox 值漏过)
    if isinstance(value, bool):
        raise InvalidValueError(f'{path} 不接受 bool 值,got {value!r}')

    if _is_locked_path(path):
        raise FieldLockedError(f'字段被锁死,不可编辑: {path}')

    # ⚠ 白名单校验(默认拒绝)
    if path in ALLOWED_TOP_PATHS:
        pass  # 顶层白名单通过
    elif path.startswith('attributes.'):
        field = path[len('attributes.'):]
        if field not in ALLOWED_ATTR_FIELDS:
            raise InvalidValueError(
                f'{path} 不在白名单,attributes 可改字段: {sorted(ALLOWED_ATTR_FIELDS)}'
            )
    elif path.startswith('skillPoint.') or (path.startswith('nowSkills.') and path.endswith('.level')):
        pass  # skillPoint / nowSkills.X.level 走下面的专门格式校验
    elif _is_container_edit_path(path):
        pass  # 容器编辑路径(consumes.N.num 等)走下面的专门校验
    else:
        # 既不是顶层白名单,也不是 attributes.X 白名单,也不是 skillPoint/nowSkills,也不是容器编辑
        raise InvalidValueError(
            f'{path} 不在白名单(顶层: {sorted(ALLOWED_TOP_PATHS)}, '
            f'attributes: {sorted(ALLOWED_ATTR_FIELDS)}, skillPoint.X, nowSkills.X.level, '
            f'容器: consumes/equips.X.num)'
        )

    if path in ('lev', 'coin', 'currentExp'):
        if not isinstance(value, int) or value < 0:
            raise InvalidValueError(f'{path} 必须是非负 int,got {value!r}')

    if path.startswith('attributes.'):
        if not isinstance(value, (int, float)):
            raise InvalidValueError(f'{path} 必须是 int 或 float,got {value!r}')
        # HP/MP/攻击/防御保护(0 是个边界,允许 = 不做任何事)
        if path in (
            'attributes._maxHP', 'attributes._maxMP',
            'attributes.attack', 'attributes.magicPower',
            'attributes.defense', 'attributes.attackSpeed',
        ) and value < 0:
            raise InvalidValueError(f'{path} 不能为负')

    # ⚠ P0 #1 修复:加括号修正优先级 (A or B) and C,不再让 nowSkills.0 漏过校验
    # 同时拆分支,理清 "skillPoint.X" 和 "nowSkills.X.level" 两条规则的边界
    if path.startswith('skillPoint.'):
        # skillPoint.X 必须是非负 int,X 必须是数字
        last = path.split('.')[-1]
        if not last.isdigit():
            raise InvalidPathError(f'skillPoint 索引必须为数字: {path!r}')
        if not isinstance(value, int) or value < 0:
            raise InvalidValueError(f'{path} 必须是非负 int,got {value!r}')
    elif path.startswith('nowSkills.') and path.endswith('.level'):
        # nowSkills.X.level X 必须是数字,value 必须是非负 int 且 ≤ 30
        middle = path.split('.')[-2]
        if not middle.isdigit():
            raise InvalidPathError(f'nowSkills 索引必须为数字: {path!r}')
        if not isinstance(value, int) or value < 0:
            raise InvalidValueError(f'{path} 必须是非负 int,got {value!r}')
        if value > 30:
            raise InvalidValueError(f'技能等级不能超过 30,got {value}')

    # 容器编辑路径值校验
    if _is_container_edit_path(path):
        parts = path.split('.')
        field = parts[2]
        if field == 'num':
            if not isinstance(value, int) or value < 0:
                raise InvalidValueError(f'{path} num 必须是非负 int,got {value!r}')


# ============== 批量应用 ==============

def apply_edits(
    data: dict,
    edits: Iterable[Edit],
    *,
    require_no_weapon: bool = True,
    weapon_position: int = WEAPON_POSITION_IN_NOW_EQUIPS,
) -> dict:
    """
    把编辑列表应用到 data(深拷贝返回,原 dict 不动)。

    流程:
    1. 深拷贝 data(防污染原对象)
    2. 校验每条 Edit(path 锁死 + value 范围)
    3. 如果 require_no_weapon=True 且 edits 涉及 WEAPON_GUARD_FIELDS,
       先 check_no_weapon_equipped,有武器抛 WeaponEquippedError(Q3 拍板)
    4. 应用所有编辑
    5. 返回新 dict
    """
    edits_list = list(edits)
    new_data = copy.deepcopy(data)

    # 先校验所有 edit 的 path + value
    for ed in edits_list:
        if _is_locked_path(ed.path):
            raise FieldLockedError(f'字段被锁死,不可编辑: {ed.path}')
        validate_field(ed.path, ed.value)

    # 武器脱下校验(Q3)
    if require_no_weapon:
        if any(ed.path in WEAPON_GUARD_FIELDS for ed in edits_list):
            ok, iid = check_no_weapon_equipped(new_data, weapon_position)
            if not ok:
                raise WeaponEquippedError(weapon_position, iid)

    # 应用
    for ed in edits_list:
        _set_nested(new_data, ed.path, ed.value)

    return new_data


# ============== 字节差异校验 ==============

def compute_byte_diff_rate(before: bytes, after: bytes) -> float:
    """
    返回 (不同字节数 / 总字节数),范围 [0, 1]。
    字节数不同则按较短者算(避免误报)。
    """
    if not before and not after:
        return 0.0
    n = min(len(before), len(after))
    if n == 0:
        return 1.0  # 一边是空
    diff = sum(1 for a, b in zip(before, after) if a != b)
    diff += abs(len(before) - len(after))  # 长度差也算
    return diff / max(len(before), len(after))


def check_byte_diff_ok(before: bytes, after: bytes) -> Tuple[bool, float, str]:
    """
    返回 (ok, diff_rate, reason)
    - 浮点差异容忍:< 0.1% 视为正常(JSON 浮点 16→15 位精度,批 1.1 拍板)
    - 硬上限 5%:超过就完全拒绝
    """
    rate = compute_byte_diff_rate(before, after)
    if rate <= FLOAT_BYTE_DIFF_TOLERANCE:
        return True, rate, f'字节差异 {rate:.4%} ≤ 容忍度 {FLOAT_BYTE_DIFF_TOLERANCE:.2%}'
    if rate <= BYTE_DIFF_HARD_LIMIT:
        # 在容忍和硬限之间,放行但 warn(批 2 留给 GUI 决定是否警告)
        return True, rate, f'字节差异 {rate:.4%} 超过浮点容忍度 {FLOAT_BYTE_DIFF_TOLERANCE:.2%},但在硬限 {BYTE_DIFF_HARD_LIMIT:.2%} 内,放行'
    return False, rate, f'字节差异 {rate:.4%} 超过硬限 {BYTE_DIFF_HARD_LIMIT:.2%},拒绝'


# ============== 原子写盘 + 备份 ==============

def backup_file(path: Path) -> Optional[Path]:
    """
    把 path 复制到 path.bak(覆盖式,memory C7 拍板)。
    - 源不存在:返回 None
    - .bak 已存在:覆盖
    """
    path = Path(path)
    if not path.exists():
        return None
    bak = path.with_suffix(path.suffix + '.bak')
    shutil.copy2(path, bak)
    return bak


def write_save_atomic(path: Path, data: dict, key: int) -> bytes:
    """
    原子写盘:先写 .tmp 再 rename。
    失败时 .tmp 留在原位,不污染原文件。
    """
    from save_codec import encode  # 局部 import 避免循环

    path = Path(path)
    encoded = encode(data, key)

    # 写到同目录的 .tmp(保证 rename 是同 fs)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + '.', suffix='.tmp', dir=str(path.parent)
    )
    try:
        with os.fdopen(tmp_fd, 'wb') as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic on POSIX
    except Exception:
        # 清理 .tmp
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return encoded

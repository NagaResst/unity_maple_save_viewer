"""
gen_data.py - 把 JSON 数据转换成 Python 模块(只读运行一次)

用法:
    python gen_data.py

输入(项目根目录):
    items.json         - 物品数据(1242 条)
    form8_skill.json   - 技能数据(287 条)

输出(项目根目录):
    item_data.py       - 物品字典 (ITEMS)
    skill_data.py      - 技能字典 (SKILLS)

设计要点:
- 用 dict 不用 list:O(1) 查找,import 即用,无 JSON 解析步骤
- items 只保留 NAME 字段(查询用)+ TYPE/EQUIPTYPE(未来扩展用)
- skills 保留 name(查询用)+ jobs(未来按职业过滤用)
- 顶部 docstring 注明生成时间和源文件名,提醒不要手动改
- Python 字面量输出:用 repr() 保证 unicode 中文不被转义
- 格式化成多行 dict(每行一项),git diff 可读

只读源 JSON,不修改源文件,只生成 Python 模块。
如果源 JSON 不存在,脚本会清晰报错,不静默失败。
"""
import json
import sys
from pathlib import Path
from datetime import datetime


# ============== 物品数据 ==============
def _normalize_key(k: str) -> str:
    """把所有 JSON key 统一转大写,避免类似 EQUIPtYPE 的大小写混淆 bug。

    设计要点:
    - JSON 里 key 大小写混用(ID / NAME / EQUIPtYPE / EQUIPiNFO / TRADtYPE ...),
      写代码时容易漏一个字母
    - 全部转大写后,EQUIPtYPE → EQUIPTYPE,后续不会再踩坑
    - 查询端统一用全大写:item_data.ITEMS[id]['NAME']
    """
    return str(k).upper() if isinstance(k, str) else k


def gen_items_data(src: Path, dst: Path) -> int:
    """从 items.json 生成 item_data.py,返回写入条目数"""
    if not src.exists():
        raise FileNotFoundError(f'找不到源文件: {src}')

    with open(src, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError(f'{src} 顶层不是 list,是 {type(raw).__name__}')

    # 转成 dict:key=8位ID,value=精简字段(所有 value key 全大写)
    items = {}
    skipped_short_id = 0
    skipped_no_name = 0
    for it in raw:
        if not isinstance(it, dict):
            continue
        item_id = it.get('ID')
        name = it.get('NAME')
        if not isinstance(item_id, str) or len(item_id) != 8:
            skipped_short_id += 1
            continue
        if not isinstance(name, str):
            skipped_no_name += 1
            continue
        # 只保留查询必需的字段,key 统一转大写
        items[item_id] = {
            _normalize_key('NAME'): name,
            _normalize_key('TYPE'): it.get('TYPE', ''),
            _normalize_key('EQUIPtYPE'): it.get('EQUIPtYPE', ''),
        }

    # 写出 Python 模块
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        '"""',
        f'item_data.py - 物品数据字典',
        f'由 gen_data.py 在 {timestamp} 自动生成',
        f'源文件: items.json',
        f'',
        f'条目数: {len(items)} 条(8位ID)',
        f'',
        f'!!! 不要手动修改本文件,改 items.json 后跑 gen_data.py 重新生成 !!!',
        '"""',
        '',
        '',
        '# ITEMS: { 8位物品ID(str) -> {NAME, TYPE, EQUIPTYPE} }',
        f'ITEMS = {{',
    ]
    for item_id in sorted(items.keys()):
        v = items[item_id]
        # 用 repr() 保证中文不被转义
        lines.append(f"    {item_id!r}: {{'NAME': {v['NAME']!r}, 'TYPE': {v['TYPE']!r}, 'EQUIPTYPE': {v['EQUIPTYPE']!r}}},")
    lines.append('}')
    lines.append('')

    dst.write_text('\n'.join(lines), encoding='utf-8')
    print(f'✅ 写入 {dst} ({len(items)} 条,跳过 {skipped_short_id} 条短ID / {skipped_no_name} 条无NAME)')
    return len(items)


# ============== 技能数据 ==============
def gen_skill_data(src: Path, dst: Path) -> int:
    """从 form8_skill.json 生成 skill_data.py,返回写入条目数"""
    if not src.exists():
        raise FileNotFoundError(f'找不到源文件: {src}')

    with open(src, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError(f'{src} 顶层不是 list,是 {type(raw).__name__}')

    # 转成 dict:key=int(可转换的)或 str(字符串 ID)
    # value key 全大写('name' → 'NAME', 'jobs' → 'JOBS')
    skills = {}
    for s in raw:
        if not isinstance(s, dict):
            continue
        sid = s.get('id')
        name = s.get('name')
        if not isinstance(name, str):
            continue

        # key 转换:数字 ID 用 int(查表 O(1)),字符串 ID 保留 str
        try:
            key = int(sid) if isinstance(sid, str) else sid
        except (ValueError, TypeError):
            key = sid

        # 精简字段(key 全大写)
        jobs = s.get('jobs', [])
        if not isinstance(jobs, list):
            jobs = []
        skills[key] = {
            'NAME': name,
            'JOBS': jobs,
        }

    # 写出 Python 模块
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    numeric_count = sum(1 for k in skills if isinstance(k, int))
    str_count = sum(1 for k in skills if isinstance(k, str))

    lines = [
        '"""',
        f'skill_data.py - 技能数据字典',
        f'由 gen_data.py 在 {timestamp} 自动生成',
        f'源文件: form8_skill.json',
        f'',
        f'条目数: {len(skills)} 条(数字 ID: {numeric_count}, 字符串 ID: {str_count})',
        f'',
        f'!!! 不要手动修改本文件,改 form8_skill.json 后跑 gen_data.py 重新生成 !!!',
        '"""',
        '',
        '',
        '# SKILLS: { 技能ID(int 或 str) -> {NAME, JOBS} }',
        f'SKILLS = {{',
    ]
    # 数字 ID 排前面(查询常用),字符串 ID 排后面
    for key in sorted(skills.keys(), key=lambda k: (isinstance(k, str), k)):
        v = skills[key]
        key_repr = f'{key!r}'  # int 和 str 都能 repr
        lines.append(f'    {key_repr}: {{"NAME": {v["NAME"]!r}, "JOBS": {v["JOBS"]!r}}},')
    lines.append('}')
    lines.append('')

    dst.write_text('\n'.join(lines), encoding='utf-8')
    print(f'✅ 写入 {dst} ({len(skills)} 条 = {numeric_count} 数字 + {str_count} 字符串)')
    return len(skills)


# ============== 入口 ==============
def main():
    project_root = Path(__file__).parent

    items_json = project_root / 'items.json'
    form8_skill_json = project_root / 'form8_skill.json'

    print('=== 生成 Python 数据模块 ===')
    print(f'项目根目录: {project_root}')

    n_items = gen_items_data(items_json, project_root / 'item_data.py')
    n_skills = gen_skill_data(form8_skill_json, project_root / 'skill_data.py')

    print(f'\n=== 总计: {n_items} 物品 + {n_skills} 技能 ===')
    print('✅ 生成完成。源 JSON 文件可保留作备份,或删除(项目运行不依赖 JSON)。')


if __name__ == '__main__':
    main()
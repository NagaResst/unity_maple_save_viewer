"""
zip_io.py - 存档打包/解包(纯函数,无 GUI 依赖)
"""
import zipfile
from pathlib import Path
from typing import Optional

from save_codec import classify, decode, summarize_player, summarize_role_info
from save_paths import default_save_dir


def collect_saves(save_dir: Path) -> list:
    """
    扫描存档目录,返回严格匹配的存档
    [RoleInfo.json(若有), Player00.json, Player01.json, ...]
    不存在的目录返回空列表
    只识别符合 classify() 规则的文件名(过滤掉"副本"/空格/后缀等)
    """
    if not save_dir.exists() or not save_dir.is_dir():
        return []
    out = []
    ri = save_dir / 'RoleInfo.json'
    if ri.exists() and classify(ri.name) is not None:
        out.append(ri)
    # glob 拿到所有 Player*.json,再用 classify 过滤(去掉副本/中文等)
    for p in sorted(save_dir.glob('Player*.json')):
        if classify(p.name) is not None:
            out.append(p)
    return out


def export_zip(save_dir: Path, zip_path: Path) -> dict:
    """
    把 save_dir 下所有存档原样打包到 zip_path(密文形式,不预先解码)
    zip 内只用文件名(无目录层级)
    返回 {'count': N, 'size': bytes}
    找不到任何存档时抛 FileNotFoundError
    """
    files = collect_saves(save_dir)
    if not files:
        raise FileNotFoundError(f'目录里没找到存档: {save_dir}')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    return {'count': len(files), 'size': zip_path.stat().st_size}


def read_zip_entries(zip_path: Path) -> list:
    """
    打开 zip,读取所有可识别的 .json 条目
    返回 [{'name', 'raw', 'kind', 'summary', 'decoded'/'error': ...}, ...]
    解码失败时 decoded=None,error=str
    """
    out = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.endswith('.json'):
                continue
            info = classify(name)
            if info is None:
                continue
            kind, key = info
            raw = zf.read(name)
            entry = {
                'name': name,
                'raw': raw,
                'kind': kind,
            }
            try:
                decoded = decode(raw, key)
                entry['decoded'] = decoded
                if kind == 'player':
                    entry['summary'] = summarize_player(decoded)
                else:
                    entry['summary'] = summarize_role_info(decoded)
            except Exception as e:
                entry['decoded'] = None
                entry['error'] = f'解码失败: {e}'
                entry['summary'] = '(解码失败)'
            out.append(entry)
    return out


def import_zip_entries(zip_path: Path, save_dir: Path, selected_names: list) -> dict:
    """
    把 zip 里勾选的文件密文原样写入 save_dir(直接覆盖,不做存在性检查)
    覆盖确认由调用方(viewer.on_import)在调用前完成
    返回 {'imported': [...], 'failed': [...]}  failed = zip 内找不到该条目
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    imported, failed = [], []
    with zipfile.ZipFile(zip_path) as zf:
        available = set(zf.namelist())
        for name in selected_names:
            if name not in available:
                failed.append(name)
                continue
            target = save_dir / name
            target.write_bytes(zf.read(name))
            imported.append(name)
    return {'imported': imported, 'failed': failed}

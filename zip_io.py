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
    扫描存档目录,返回 [RoleInfo.json(若有), Player00.json, Player01.json, ...]
    不存在的目录返回空列表
    """
    if not save_dir.exists() or not save_dir.is_dir():
        return []
    out = []
    ri = save_dir / 'RoleInfo.json'
    if ri.exists():
        out.append(ri)
    out.extend(sorted(save_dir.glob('Player*.json')))
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
    把 zip 里勾选的文件密文原样写入 save_dir
    存在同名文件时**默认跳过**,返回 {'imported': [...], 'skipped_existing': [...]}
    调用方负责处理"是否覆盖"的用户确认
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    imported, skipped = [], []
    with zipfile.ZipFile(zip_path) as zf:
        for name in selected_names:
            target = save_dir / name
            try:
                data = zf.read(name)
            except KeyError:
                skipped.append(name)
                continue
            if target.exists():
                skipped.append(name)
                continue
            target.write_bytes(data)
            imported.append(name)
    return {'imported': imported, 'skipped_existing': skipped}

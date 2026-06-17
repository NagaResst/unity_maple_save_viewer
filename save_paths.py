"""
save_paths.py - 默认存档目录探测
"""
import os
import sys
from pathlib import Path


def default_save_dir() -> Path:
    """
    返回 Unity 冒险岛默认存档目录:
        Windows: %USERPROFILE%\\AppData\\LocalLow\\DefaultCompany\\Unity冒险岛
        其他:    <cwd>/fake_saves   (开发回退)
    """
    if sys.platform == 'win32':
        base = os.environ.get('USERPROFILE') or str(Path.home())
        return Path(base) / 'AppData' / 'LocalLow' / 'DefaultCompany' / 'Unity冒险岛'
    return Path.cwd() / 'fake_saves'

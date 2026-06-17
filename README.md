# 枫叶存档查看器

Unity 冒险岛存档浏览器(只读)。支持两类加密存档:

| 存档类型 | 文件名 | 密钥 |
|---|---|---|
| 账号全局 | `RoleInfo.json` | `0x9F` |
| 角色 | `PlayerNN.json` (NN = 00/01/02...) | `0x77` |

## 功能

- **浏览**:左侧树形导航,右侧分页显示
  - RoleInfo:`👥 角色列表` / `⚔ 击杀记录`(种类数 + 总击杀)
  - PlayerNN:`📊 总览`(名称/等级/经验/金币/职业/背包物品总数)
- **导出全部**:把默认目录里所有存档打包成 `.zip`(密文原样)
- **导入 zip**:选择 zip → 多选 → 逐个确认覆盖(显示原 vs 新对比)→ 密文原样写回

## 默认存档目录

```
%USERPROFILE%\AppData\LocalLow\DefaultCompany\Unity冒险岛
```

Linux 开发时回退到 `<cwd>/fake_saves`。

## 运行环境

- Python 3.8+
- PyQt5 5.15+

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python viewer.py
```

## 打包成 exe(Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "枫叶存档查看器" viewer.py
```

产物在 `dist/枫叶存档查看器.exe`,单文件 ~30MB,无需 Python 环境。

## 文件结构

```
maple_save_viewer/
├── viewer.py          # PyQt5 GUI(主入口)
├── save_codec.py      # 纯函数:decode / classify / 字段统计 / 职业 ID 映射
├── save_paths.py      # 默认存档目录探测
├── zip_io.py          # 纯函数:export_zip / read_zip_entries / import_zip_entries
├── requirements.txt   # PyQt5
└── README.md
```

3 个纯函数模块不依赖 PyQt5,方便单测和后续扩展。

## 已知限制

1. **只读**——不修改任何存档字节(导出/导入都基于密文原样,不经过解码→编码)
2. **物品/技能/任务名不翻译**——`id` 是 8 位数字编码,无游戏资源文件做 ID→名字 映射
3. **职业 ID 不翻译**——`map_job_id()` 暂返回原数字 ID(后续接入完整 ID 映射表后改这一个函数)
4. **只支持两类存档**——其他文件加载时跳过
5. **导入默认跳过已存在**——需要用户主动确认覆盖

## 后续扩展(预留)

- `save_codec.map_job_id()` → 接完整职业 ID 映射表
- 新增显示页签(如装备/背包/技能/任务)→ 参考 `PlayerOverviewPage` 写法
- 导出选项增加"按类型过滤"(只导全局 / 只导角色)

# 枫叶存档查看器 — 加存档编辑功能 设计稿

> 起草日期:2026-06-19
> 状态:**待拍板**(本文档由用户直接修改,改完回到对话跟 AI 核对)
> 配套代码:`/home/nagaresst/workspace/maple_save_viewer/`

---

## 0. 改动总览

| 模块 | 类型 | 行数估算 |
|---|---|---|
| `save_codec.py` | 加 `encode(obj, key)` 函数 | +5 |
| `save_editor.py` | **新建** 纯函数模块(校验 + 应用编辑 + 原子写盘) | +80 |
| `viewer.py` | 改造 `PlayerOverviewPage` + 新建 `PlayerBagPage` + `PlayerSkillPage` | +220 |
| **合计** | | **+305 行** |

---

## 1. 第一页:基础属性

### 1.1 顶部 4 个(第一梯队)
展示与编辑策略如下表。

| 字段 | 来源 | 当前值(希尔) | 编辑策略 |
|---|---|---|---|
| 名字 | 顶层 `name` | `'希尔'` | **只读显示** |
| 等级 | 顶层 `lev` | `184` | **只读显示** |
| 经验值 | 顶层 `currentExp` | `305,699,223` | ✅ **可改** |
| 金币 | 顶层 `coin` | `39,154,466` | ✅ **可改** |

### 1.2 四维(只显示,不改)
来源:`attributes._str / _dex / _luk / _int`

| 字段 | 当前值 | 编辑策略 |
|---|---|---|
| 力量 `_str` | `78` | 只读显示 |
| 敏捷 `_dex` | `214` | 只读显示 |
| 运气 `_luk` | `1178` | 只读显示 |
| 智力 `_int` | `78` | 只读显示 |

### 1.3 核心战斗 6 个(用户已点名可改)
来源:`attributes.<字段>`

| 字段 | 当前值 | 编辑策略 | 备注 |
|---|---|---|---|
| 最大血量 `_maxHP` | `57400` | ✅ **可改** | 用 QSpinBox,上限 9,999,999 |
| 最大魔量 `_maxMP` | `3972` | ✅ **可改** | 用 QSpinBox,上限 9,999,999 |
| 攻击力 `attack` | `218` | ✅ **可改** | 用 QSpinBox,上限 9,999,999 |
| 魔法力 `magicPower` | `89` | ✅ **可改** | QSpinBox,上限 9,999,999(skill 警告:跳变 >5 倍客户端可能拒绝加载) |
| 攻击速度 `attackSpeed` | `4` | ✅ **可改** | 用 QSpinBox,上限 10 |
| 防御力 `defense` | `2008` | ✅ **可改** | 用 QSpinBox,上限 9,999,999 |

### 1.4 其余战斗属性(第一版不展示,等后续)
来源:`attributes` 字典其余 46 个字段。

排除列表(默认不展示,不分到任何页):
- `CriticalRate=75` / `CriticalDamage=16` / `percentDamage=0` / `finalDamage=29`
- `abnormalResistance=300` / `attributeResistance=300` / `indiePowerGuard=0` / `attackAR=0`
- `eva=99` / `bdR=267` / `imdR=53` / `stanceProp=100` / `range=0`
- `mhpR=35` / `mmpR=15` / `recover=170`
- `SkillMastery = [37 元素 list]`
- `mpSteal / bossMpSteal`(各 3 字段 dict)
- `psdSpeed=45.0` / `psdJump=42.0` / `speedMax=20.0`
- `lv2mhp=0` / `lv2mmp=0`
- `skillDefense=150` / `defencePercent=0` / `damAbsorbShieldR=0`
- `WeaponMultiplier=1.75` / `damage=[26972, 27245]`
- `bloodSucking=20` / `costmpR=0` / `damPlus=0/1/2/3=0` / `coinR=0` / `stunDamage=0` / `ultimateMagicDamage=0`
- `abilityPoint=0`
- `_nowHP=77490` / `_nowMP=2732` / `Mastery=0.95`
- `attributes.name / job / baseJob / family / popularity`(跟顶层重复)

---

## 2. 第二页:背包

### 2.1 容器分类
**铁律**:身上穿的不能改(由用户确认)。

#### 可改容器(8 个,每个容器都支持编辑每条目的 7 字段)

| 容器 | 当前长度(希尔) | 备注 |
|---|---|---|
| `equips` | 12 | 装备仓库 |
| `consumes` | 28 | 消耗品(药水/卷轴) |
| `others` | 1 | 杂物/材料 |
| `settings` | 5 | 设置物品(?) |
| `specials` | 35 | 特殊(宠物/坐骑/特殊道具) |
| `fashions` | 9 | 时装 |
| `trunkItems` | 0 | 仓库 |
| `buyBackGoods` | 10 | 回购栏 |

#### 只读容器(2 个,显示但不编辑)

| 容器 | 当前长度 | 备注 |
|---|---|---|
| `nowEquips` | 19 | 身上穿的装备 |
| `nowSpecials` | 6 | 身上特殊槽(戒指/勋章) |

### 2.2 每个条目的可编辑字段(7 个)
来源:对希尔存档每个容器首项字段验证,所有容器字段结构一致(见 §2.3)。

| 字段 | 类型 | 备注 |
|---|---|---|
| `id` | str(8 位) | 物品 ID,长度严格 8 |
| `num` | int | 数量 |
| `nowNum` | int | 当前数量(有时跟 `num` 不同) |
| `position` | int(0-?) | 槽位号,容器内唯一 |
| `gainType` | int | 获得途径 |
| `price` | int | 价格(显示可改) |
| `shopPrice` | int | 商店价格(显示可改) |

### 2.3 每个条目的只读字段(7 个,编辑时不开放)

| 字段 | 备注 |
|---|---|
| `equipInfo` | 41 字段嵌套子结构(magicPower/attack 溢出 uint64 上限) |
| `type` | 物品大类型 |
| `bulletFlag` / `cantUse` / `petFlag` / `chairFlag` / `hitNumberFlag` | 5 个 bool 标志 |

### 2.4 第一版不做的功能
- ❌ **新增装备**:加新装备需要完整 41 字段 `equipInfo` 嵌套子结构,`equipInfo` 默认全 0,加完进游戏客户端可能卡死或重算覆盖
- ❌ **删除装备**:删除要处理 `position` 重排,容易把别的物品挤掉
- ❌ **跨容器移动**:同 ID 在 `equips` 和 `nowEquips` 可能各有一份(skill 教训)

---

## 3. 第三页:技能

### 3.1 数据来源
- `nowSkills`:当前已学技能列表(39 条,每条 `id / level / switchFlag / type`)
- `skillPoint = [0, 0, 84, 12, 260, 0]`:6 元素数组,按 `job` 索引分职业剩余技能点

### 3.2 编辑范围
每条技能展示 4 字段,但**只可编辑 `level`**:

| 字段 | 编辑策略 |
|---|---|
| `id` | 只读显示(8 位字符串) |
| `level` | ✅ **可改**(QSpinBox,上限 30) |
| `switchFlag` | 只读(只 2 个 True,影响技能自动触发) |
| `type` | 只读(技能分类) |

### 3.3 第一版不做的功能
- ❌ **改 `skillPoint` 数组**:改完每个转职的"剩余可分配点"会乱,需要单独做"加点向导"
- ❌ **新增技能**:`nowSkills` 加新 ID,客户端会校验技能表,可能拒绝加载
- ❌ **删除技能**:同上
- ❌ **显示技能中文名**:存档只有数字 ID,需要技能词典(单独功能)

### 3.4 数据示例(希尔 nowSkills 39 条样本)
```
id=        51  level=  1
id=      1010  level=  1
id=   0001000  level=  0
id=   4001334  level= 15
id=   4000005  level= 10
id=   4101013  level= 20
id=   4101014  level= 29  ← 最大值 30
id=   4100001  level= 30  ← 最大值 30
... (共 39 条)
```

---

## 4. 跨页通用设计

### 4.1 保存流程(每页底部 3 个按钮:💾 保存 / ↩ 撤销 / ❌ 取消)

```
用户在某页改了字段
        │
        ▼
  [取消] [撤销] [保存]
        │          │
        │          ▼
        │   二次确认弹窗:
        │     "将保存以下改动:
        │      - 希尔·lev: 184 → 185
        │      - 希尔·equips[2].star: 3 → 5
        │      确认写入磁盘? "
        │          │
        │          ▼  Yes
        │   ① 把当前 self.saves[name]['data'] 编码为 bytes (save_codec.encode)
        │   ② 写临时文件 <name>.json.tmp
        │   ③ os.replace() 原子替换原文件
        │   ④ 重新读 raw bytes 校验(json.loads + 对比字段)
        │   ⑤ 弹"已保存",状态栏显示 sha256 前 8 位
        │          │
        │          ▼  校验失败 → 弹窗报错,保留 .tmp,原文件不变
        ▼
   直接丢所有改动,刷新树
```

**铁律**:
- 写盘永远是**密文**(改完 → `encode` → XOR → 写文件),不绕过加密
- `.tmp` 是**唯一**中间产物,失败时人工可查
- 保存成功后 `self.saves[name]` 的 `raw` 也要同步更新

### 4.2 树节点结构
```
📁 已加载 (3)
  ├─ 👤 希尔
  │   ├─ 📊 属性   ← 第 1 页
  │   ├─ 🎒 背包   ← 第 2 页
  │   └─ ⚔ 技能   ← 第 3 页
  └─ ...
```

### 4.3 save_editor.py 模块边界(纯函数,不带 PyQt5 依赖)

| 函数 | 职责 |
|---|---|
| `validate_int(value, min, max) -> int` | 整数范围校验,失败抛 ValueError |
| `validate_str(value, max_len) -> str` | 字符串长度校验 |
| `apply_player_edit(data, field_path, new_value) -> dict` | 改一个字段,返回新 data(不写盘) |
| `write_save_atomic(path, raw_bytes) -> None` | 原子写盘(先 .tmp 再 replace) |

### 4.4 save_codec.encode() 实现要点
```python
def encode(obj: dict, key: int) -> bytes:
    plain = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return bytes(b ^ key for b in plain)
```
- 必须用紧凑序列化 `separators=(',', ':')`,否则体积膨胀
- 用 `ensure_ascii=False` 保留中文

---

## 5. 第一版明确**不做**的事(后续版本再加)

### 5.1 第三梯队和后面的(用户已确认晚点再说)
- 改职业 `attributes.job` + `jobList` + `questInfos` 三联改
- 改技能 `skillPoint` 数组
- 改套装属性 `suitAttributes` 56 字段(跟 attributes 一样结构,数值都是装备汇总)
- 改 `equipInfo` 嵌套子结构(41 字段)
- 改 `pet_HP_Item / pet_MP_Item`(宠物药完整 Item 表)
- 改 `pet` ID
- 改 `roleData`(外观 bodyID/hairID/faceID)
- 改 `nowKeyCodes`(31 条键位)
- 改 `objcetInfos`(地图对象 17 条)
- 改 `panelOptions`(12 个面板位置)
- 改 `nowSpecials` / `nowEquips`(身上穿的,用户已确认不能改)
- 改 `buyBackGoods`(回购栏数值)
- 改 `attributes.damage = [26972, 27245]`(伤害区间数组)
- 改 `attributes._nowHP / _nowMP / Mastery`(当前血蓝/熟练度,等用户定)

### 5.2 基础架构层面
- ❌ pyinstaller 打包命令(用户自己负责)
- ❌ 日志系统 / 配置系统 / 多语言
- ❌ 自动刷新 / 自动备份链
- ❌ 关于页显示密钥(`0x9F`/`0x77`)
- ❌ 加密密钥遍历探测(已硬编码)

---

## 6. 需要用户拍板的 10 个点

下面每条都列了候选方案,**用户在候选字母上打勾或在文字位置直接改写**。

### #1 — 编辑入口策略
- A. **原页直接编辑**(属性页就地改、背包页/技能页是新页)— 我推荐
- B. 在所有页加一个统一的"📝 编辑模式"开关,关掉时所有字段只读
- C. 单独的"编辑窗口"弹窗,从树节点右键菜单触发

**用户选择:_____**

### #2 — RoleInfo.json 编辑范围
- A. **完全不做**(第一版只让编辑 PlayerNN)— 我推荐
- B. 顺便加"修改当前激活角色"(lastLoadedId)
- C. 完整支持 RoleInfo 编辑(角色列表 add/remove 等)

**用户选择:_____**

### #3 — 自动备份 .bak 文件机制
- A. **每次"保存"前自动备份成 `.bak`(只保留最近 1 份)**— 我推荐,简单
- B. 不做自动备份,依赖 zip 导出兜底
- C. 完整版本控制:每次保存留 `.bak.1` `.bak.2` `.bak.3` 三份轮转

**用户选择:_____**

### #4 — 编辑 undo 范围
- A. **会话级 undo**(打开查看器后所有改动可一条条撤销)— 推荐
- B. 只在当前页 undo(切页就清栈)— 简单
- C. 不做 undo,只做"取消 = 重新加载原文件"

**用户选择:_____**

### #5 — 装备容器编辑范围
- A. **8 个可改容器全开**(`equips`+`consumes`+`others`+`settings`+`specials`+`fashions`+`trunkItems`+`buyBackGoods`)— 用户最新需求
- B. 只允许编辑 `equips` + `nowEquips`(避免新手改消耗品 num=99999)
- C. 装备 + 消耗品 + 杂物,时装和特殊物品不允许

**用户选择:_____**

### #6 — 角色名校验
- A. 不做校验,随便改 — 简单,但客户端可能拒绝加载名字含特殊字符的存档
- B. **长度 ≤ 12 个字符 + 不含特殊符号(只允许中英文 + 数字)**— 我推荐
- C. 等用户给出"游戏允许的角色名字符集"再做

**用户选择:_____**

### #7 — 路径:`save_editor.py` 单文件 vs 直接放 `save_codec.py`
- A. **新建 `save_editor.py`,放校验 + 写盘 + 应用编辑**— 我推荐(后续命令行工具能复用)
- B. 全塞 `save_codec.py`,一个文件搞定
- C. 顺便再加个 `save_editor_cli.py` 命令行入口(批量改多个 PlayerNN)

**用户选择:_____**

### #8 — 顶层字段范围(从第一梯队 11 个里挑)
- A. **4 个**(name/lev 只显示,currentExp/coin 可改)— 用户最新需求
- B. 5 个(name/lev 只显示,currentExp/coin/voucher 可改)
- C. 11 个全要可改(name/lev/gender/mapLocation/form/deadFlag/bagToggle/skillToggle 都加)

**用户选择:_____**

### #9 — 健康检查警告
- A. **保存前弹"检测到 _nowHP>_maxHP 异常,确认要保存吗?"**— 我推荐(用户已发现这个 bug)
- B. 不做警告,直接保存
- C. 第一版不做,等用户用完再加

**用户选择:_____**

### #10 — 技能等级上限
- A. **0-30 通用上限**(看到最大的就是 30)— 我推荐
- B. 0-20(大部分技能)
- C. 不设上限,让玩家自由填(可能客户端拒绝)

**用户选择:_____**

### #11 — 技能页要不要显示中文名
- A. **不加**,纯数字 ID(简单)— 我推荐第一版这样
- B. 等用户给一份技能 ID→中文名映射表(放到 `save_codec.py` 里查表)
- C. 第一版不做,后续单独做"技能词典"功能

**用户选择:_____**

### #12 — 套装属性 suitAttributes 要不要展示
- A. **不展示**(冗余,跟 attributes 重)— 我推荐
- B. 在第一页底部加一栏"套装加成",只读展示
- C. 第一页用 Tab 切换"角色属性 / 套装属性"

**用户选择:_____**

### #13 — 每个角色的页面数
- A. **3 页(属性 / 背包 / 技能)**— 用户最新需求
- B. 2 页(合并属性 + 技能为一页"角色")
- C. 4 页(属性 / 背包 / 技能 / 套装)

**用户选择:_____**

---

## 7. 数据规模统计(第一版可编辑单元格)

| 页 | 区域 | 可编辑数 |
|---|---|---|
| 第 1 页 基础属性 | 顶层 | 2 (exp / coin) |
| 第 1 页 基础属性 | 战斗核心 | 6 (_maxHP / _maxMP / attack / magicPower / attackSpeed / defense) |
| 第 2 页 背包 | 8 个可改容器 × 7 字段/条 | 8 × 7 = 56 字段 (按条目数扩展,实际 56 + 物品数) |
| 第 3 页 技能 | 39 条技能 × 1 字段 | 39 (level) |
| **合计** | | **8 + 56 字段 + 39 技能 = 103 个可编辑单元格** |

按希尔实际数据估算:**8 + 8 × 物品数 × 7 + 39 ≈ 432 个可编辑单元格**。

---

## 8. 实施顺序(用户拍板后我会按此顺序写)

1. `save_codec.encode()`(5 行,纯函数,单测)
2. `save_editor.py` 新建(80 行,纯函数,单测)
3. `viewer.PlayerOverviewPage` 改造(可编辑表单 + 3 按钮)
4. `viewer.PlayerBagPage` 新建(8 容器下拉 + QTableWidget)
5. `viewer.PlayerSkillPage` 新建(QTableWidget + QSpinBox)
6. `viewer.MainWindow` 改造(树节点加 3 子页签 + 工具栏加"💾 保存当前页"按钮?)
7. 沙盒测试 `QT_QPA_PLATFORM=offscreen`
8. 真实存档 roundtrip 验证(改 → encode → write → re-read → 字段对比)

---

## 9. 不确定项 / 风险点(AI 提醒)

1. **`magicPower` 跳 5 倍以上客户端可能拒绝加载**(skill 验证过:247 → 26000 后用户进游戏变 18446744073709525402)
2. **`_nowHP > _maxHP` 是已存在的 bug**(希尔 = 77,490 / 57,400 = 1.35x),客户端进游戏可能修正
3. **`attributes.attack / magicPower` 改完进游戏,可能被脱装保存时重算覆盖**(skill 教训)
4. **同一 ID 在 `equips` 和 `nowEquips` 可能各有一份**(skill 警告),第二页可改容器仅 8 个,不含 nowEquips,绕过了这个坑
5. **保存按钮的"二次确认弹窗"必须显示具体改动**(字段名 + 改前/改后值),不显示笼统"将保存 5 项改动"
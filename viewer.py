"""
viewer.py - PyQt5 主窗口
"""
import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QAction, QApplication, QCheckBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QSplitter, QStackedWidget, QStatusBar,
    QTableWidget, QTableWidgetItem, QToolBar, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from save_codec import (
    bag_total, classify, decode, killrecord_stats, map_job_id,
    summarize_player, summarize_role_info, KEY_PLAYER,
)
from save_paths import default_save_dir
from item_db import get_name as get_item_name, is_loaded as items_db_loaded
from skill_db import get_name as get_skill_name, is_loaded as skills_db_loaded
from edit_mode_mixin import EditModeMixin  # 批 2.2 新增
from save_editor import Edit  # 批 2.2 _collect_edits 用
# 数据来源:Python 模块(由 gen_data.py 从 JSON 生成),不是 JSON 直接读
# 用 try/except 容错:导入失败时给个空 dict,_load_items_dict 会走容错分支
try:
    from item_data import ITEMS as _ITEMS_RAW
except Exception as _e:
    _ITEMS_RAW = {}
    print(f'[viewer] 警告: item_data 导入失败 ({_e}),物品名 fallback 到 ID')
try:
    from skill_data import SKILLS as _SKILLS_RAW
except Exception as _e:
    _SKILLS_RAW = {}
    print(f'[viewer] 警告: skill_data 导入失败 ({_e}),技能名 fallback 到 ID')
# 给 _load_items_dict / _load_skills_dict 用(避免每次都重新 import)
ITEMS = _ITEMS_RAW
SKILLS = _SKILLS_RAW
from zip_io import (
    collect_saves, export_zip, import_zip_entries, read_zip_entries,
)


# =================== PlayerNN 总览页 ===================
class PlayerOverviewPage(EditModeMixin, QWidget):
    """
    单页:展示角色的基础属性 + 战斗属性
    批 1:展示 14 个核心战斗字段 + 4 个顶层字段(只读 label)
    批 2.2:加编辑模式(E1 A 开关在顶部右侧,E2 B 武器提示永远显示,E3 B 简单确认弹窗,E4 A 取消=撤销退出)

    字段布局(2x2 QGridLayout + QGroupBox):
    - 顶部:名字(大字号) + ⚠ 武器提示(E2 B,永远显示)
    - (0,0) 📋 身份信息 GroupBox:lev / currentExp / coin(批 2 可改)
    - (0,1) 💪 四维属性 GroupBox:_str / _dex / _luk / _int(可改,保存前仍受武器守卫)
    - (1,0) ⚔ 战斗核心 GroupBox:_maxHP / _maxMP / attack / magicPower / attackSpeed / defense(可改)
    - (1,1) 🎯 战斗进阶 GroupBox:CriticalRate / CriticalDamage / percentDamage / finalDamage / imdR / bdR / stanceProp / abilityPoint(可改)
    + 🔋 当前状态 GroupBox:_nowHP / _nowMP / Mastery(可改)
    """

    # 字段元数据:(label_text, path, kind, range, default)
    # kind: 'int' / 'float'
    # range: (min, max) for QSpinBox,上限 2^31-1 ≈ 2.1e9
    EDITABLE_FIELDS = [
        # 身份区(3)
        ('等级', 'lev', 'int', (0, 300), 0),
        ('经验值', 'currentExp', 'int', (0, 2_000_000_000), 0),
        ('金币', 'coin', 'int', (0, 2_000_000_000), 0),
        # 四维(4)
        ('力量 _str', '_str', 'int', (0, 2_000_000_000), 0),
        ('敏捷 _dex', '_dex', 'int', (0, 2_000_000_000), 0),
        ('运气 _luk', '_luk', 'int', (0, 2_000_000_000), 0),
        ('智力 _int', '_int', 'int', (0, 2_000_000_000), 0),
        # 战斗核心(6)
        ('最大血量 _maxHP', '_maxHP', 'int', (0, 2_000_000_000), 0),
        ('最大魔量 _maxMP', '_maxMP', 'int', (0, 2_000_000_000), 0),
        ('攻击力 attack', 'attack', 'int', (0, 2_000_000_000), 0),
        ('魔法力 magicPower', 'magicPower', 'int', (0, 2_000_000_000), 0),
        ('攻击速度 attackSpeed', 'attackSpeed', 'int', (0, 1000), 0),
        ('防御力 defense', 'defense', 'int', (0, 2_000_000_000), 0),
        # 战斗进阶(8)
        ('暴击率 CriticalRate', 'CriticalRate', 'int', (0, 1000), 0),
        ('暴击伤害 CriticalDamage', 'CriticalDamage', 'int', (0, 1000), 0),
        ('增伤百分比 percentDamage', 'percentDamage', 'int', (0, 1000), 0),
        ('最终伤害 finalDamage', 'finalDamage', 'int', (0, 1000), 0),
        ('无视防御 imdR', 'imdR', 'int', (0, 1000), 0),
        ('首领伤害 bdR', 'bdR', 'int', (0, 1000), 0),
        ('稳如泰山 stanceProp', 'stanceProp', 'int', (0, 1000), 0),
        ('可用能力值 abilityPoint', 'abilityPoint', 'int', (0, 2_000_000_000), 0),
        # 当前状态(3)
        ('当前血量 _nowHP', '_nowHP', 'int', (0, 2_000_000_000), 0),
        ('当前魔量 _nowMP', '_nowMP', 'int', (0, 2_000_000_000), 0),
        ('熟练度 Mastery', 'Mastery', 'float', (0.0, 100.0), 0.0),
    ]

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        EditModeMixin.__init__(self, page_title='基础属性')
        self._data: dict | None = None
        self._build_ui()

    def _build_ui(self):
        # 用 QScrollArea 包一层,字段多了之后窗口缩小时可滚动
        from PyQt5.QtWidgets import QScrollArea, QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # EditModeMixin 的开关/按钮(E1 A 顶部右侧 + 底部按钮)
        self._build_edit_mode_controls(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ===== 角色名(大字号) + 武器提示(E2 B 永远显示) =====
        name_row = QHBoxLayout()
        self.lbl_name = QLabel('-')
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.lbl_name.setFont(font)
        name_row.addWidget(self.lbl_name)

        # 武器提示(E2 B 永远显示,红色小字)
        self.lbl_weapon_hint = QLabel('⚠ 修改四维和攻击力前需要脱下武器')
        self.lbl_weapon_hint.setStyleSheet('color: #c00; font-size: 11px; padding-left: 12px;')
        self.lbl_weapon_hint.setWordWrap(True)
        name_row.addWidget(self.lbl_weapon_hint, 1)
        root.addLayout(name_row)

        # ===== 2x2 网格布局 =====
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        # 容器(每个 group 同时存 label + spinbox,切换时 setVisible)
        # {path: (lbl, spin)}  spin 在 kind='float' 时是 QDoubleSpinBox
        self._field_widgets = {}
        # ====== (0,0) 身份信息 ======
        gb_id, id_form = self._make_groupbox('📋 身份信息')
        for label, path, kind, rng, default in self.EDITABLE_FIELDS[:3]:
            self._add_field_row(id_form, label, path, kind, rng, default)
        grid.addWidget(gb_id, 0, 0)

        # ====== (0,1) 四维属性 ======
        gb_stat, stat_form = self._make_groupbox('💪 四维属性')
        for label, path, kind, rng, default in self.EDITABLE_FIELDS[3:7]:
            self._add_field_row(stat_form, label, path, kind, rng, default)
        grid.addWidget(gb_stat, 0, 1)

        # ====== (1,0) 战斗核心(6 项) ======
        gb_combat, combat_form = self._make_groupbox('⚔ 战斗核心')
        for label, path, kind, rng, default in self.EDITABLE_FIELDS[7:13]:
            self._add_field_row(combat_form, label, path, kind, rng, default)
        grid.addWidget(gb_combat, 1, 0)

        # ====== (1,1) 战斗进阶(8 项) ======
        gb_adv, adv_form = self._make_groupbox('🎯 战斗进阶')
        for label, path, kind, rng, default in self.EDITABLE_FIELDS[13:21]:
            self._add_field_row(adv_form, label, path, kind, rng, default)
        grid.addWidget(gb_adv, 1, 1)

        # ====== 跨整行(2,0)+(2,1): 当前状态(3 项) ======
        gb_now, now_form = self._make_groupbox('🔋 当前状态')
        for label, path, kind, rng, default in self.EDITABLE_FIELDS[21:]:
            self._add_field_row(now_form, label, path, kind, rng, default)
        grid.addWidget(gb_now, 2, 0, 1, 2)  # 跨两列

        # 初始:spinbox 全部隐藏(只读模式)
        self._apply_edit_mode_to_widgets(False)
        # 注册控件到 mixin(让 valueChanged 触发 save/undo 启用)
        self.register_field_widgets({p: spin for p, (lbl, spin) in self._field_widgets.items()})

    def _make_groupbox(self, title: str) -> tuple:
        from PyQt5.QtWidgets import QGroupBox, QFormLayout
        gb = QGroupBox(title)
        form = QFormLayout(gb)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        return gb, form

    def _add_field_row(self, form, label_text, path, kind, rng, default):
        """加一行:同时建 label 和 spinbox,同 cell 用 setVisible 切换(只读 ↔ 编辑)。"""
        from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox
        lbl = QLabel('-')
        if kind == 'float':
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
        else:
            spin = QSpinBox()
        spin.setRange(rng[0], rng[1])
        spin.setValue(default)

        # 用 QWidget 装 {lbl, spin} 同一 cell,EditMode 切 setVisible
        from PyQt5.QtWidgets import QWidget as _W
        wrap = _W()
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(lbl)
        h.addWidget(spin)
        h.addStretch()
        form.addRow(f'{label_text}:', wrap)
        # 初始:只读模式 → label 显示,spinbox 隐藏
        spin.setVisible(False)
        self._field_widgets[path] = (lbl, spin)

    def _apply_edit_mode_to_widgets(self, on: bool):
        """
        EditModeMixin 调用:切换所有可改字段的 label ↔ spinbox。
        on=True → 显示 spinbox,隐藏 label
        on=False → 显示 label,隐藏 spinbox
        """
        for path, (lbl, spin) in self._field_widgets.items():
            lbl.setVisible(not on)
            spin.setVisible(on)
        # 武器提示永远显示(E2 B)
        self.lbl_weapon_hint.setVisible(True)

    def set_data(self, data: dict):
        # 存 data 供 _do_save + snapshot 供撤销
        self._data = data
        self.take_data_snapshot(data)  # mixin 的撤销

        # 身份区
        self.lbl_name.setText(str(data.get('name', '?')))
        self.lbl_lev_spin = getattr(self, '_field_widgets', {}).get('lev', (None, None))[1]
        # set label / spin 文本
        attrs = data.get('attributes', {}) or {}
        for label, path, kind, rng, default in self.EDITABLE_FIELDS:
            if path in ('lev', 'coin', 'currentExp'):
                val = data.get(path, default)
            else:
                val = attrs.get(path, default)
            lbl, spin = self._field_widgets[path]
            lbl.setText(str(val))
            spin.setValue(float(val) if kind == 'float' else int(val))

        # 武器提示:动态显示状态
        # E2 B:永远显示提示(可读模式也显示)
        # 加个小标记:穿着武器时变红+粗体
        from save_editor import check_no_weapon_equipped
        ok, iid = check_no_weapon_equipped(data)
        if ok:
            self.lbl_weapon_hint.setText('✓ 当前未穿武器,可正常修改四维和攻击力')
            self.lbl_weapon_hint.setStyleSheet('color: #080; font-size: 11px; padding-left: 12px;')
        else:
            self.lbl_weapon_hint.setText(
                f'⚠ 当前穿着武器 (itemId={iid}),修改四维和攻击力会被阻止,'
                f'请先在游戏里脱下武器再读档回来'
            )
            self.lbl_weapon_hint.setStyleSheet('color: #c00; font-size: 11px; padding-left: 12px; font-weight: bold;')

    def _do_save(self, edits):
        """
        EditModeMixin._on_save_clicked 调:把 edits 写到磁盘。
        用 save_editor.apply_edits + write_save_atomic + backup_file。
        """
        if self._data is None:
            QMessageBox.warning(self, '保存', '没有数据可保存')
            return
        from save_editor import (
            apply_edits, write_save_atomic, backup_file, check_byte_diff_ok,
            WeaponEquippedError, FieldLockedError, InvalidValueError,
        )
        from save_codec import KEY_PLAYER

        # 1. 找 path
        save = self._data.get('_save_meta')  # 由 MainWindow 注入
        if save is None:
            QMessageBox.warning(self, '保存', '找不到源文件路径')
            return
        path = save['path']
        key = save.get('key', KEY_PLAYER)

        # 2. 应用编辑(深拷贝,排除 _save_meta 等注入字段)
        # _save_meta 含 PosixPath 不可 JSON 序列化,必须 pop
        data_for_edit = {k: v for k, v in self._data.items() if k != '_save_meta'}
        try:
            new_data = apply_edits(data_for_edit, edits)
        except WeaponEquippedError as e:
            QMessageBox.warning(self, '武器未脱下', str(e))
            return
        except (FieldLockedError, InvalidValueError) as e:
            QMessageBox.warning(self, '校验失败', str(e))
            return

        # 3. 备份
        backup_file(path)

        # 4. 写盘
        try:
            new_raw = write_save_atomic(path, new_data, key)
        except Exception as e:
            QMessageBox.critical(self, '写盘失败', str(e))
            return

        # 5. 字节差异校验
        old_raw = save.get('raw')
        if old_raw is not None:
            ok, rate, msg = check_byte_diff_ok(old_raw, new_raw)
            if not ok:
                QMessageBox.warning(
                    self, '字节差异超限',
                    f'字节差异 {rate:.4%} 超过硬限,已写盘但请检查。\n{msg}'
                )
            elif rate > 0.001:
                QMessageBox.information(
                    self, '已保存(警告)',
                    f'已保存 {len(edits)} 项。\n字节差异 {rate:.4%} 略超浮点容忍度,但在硬限内。'
                )

        # 6. 更新内存 data + tree 重渲
        # 把 _save_meta 重新注入到 new_data(下次 _do_save 还要用)
        new_data['_save_meta'] = save  # 同一个 dict 引用
        save['data'] = new_data
        save['raw'] = new_raw
        self.set_data(new_data)  # 重渲 UI(重置 _data_snapshot)

    def _collect_edits(self):
        """
        PlayerOverviewPage 专用:把 {path: (lbl, spin)} 转成 Edit 列表,
        path 形如 'attributes.attack' / 'lev'。
        只收集与 snapshot 原值不同的字段。
        """
        if self._data_snapshot is None:
            return []
        out = []
        attrs_snap = self._data_snapshot.get('attributes', {}) or {}
        for path, pair in self._field_widgets.items():
            lbl, spin = pair
            val = self._read_widget_value(spin)
            if val is None:
                continue
            # 取 snapshot 中的原值
            if path in ('lev', 'coin', 'currentExp'):
                edit_path = path
                old_val = self._data_snapshot.get(path)
            else:
                edit_path = f'attributes.{path}'
                old_val = attrs_snap.get(path)
            # 值没变就跳过
            if old_val is not None and val == old_val:
                continue
            # int/float 精度差异也跳过(如 spinbox 显示 0.0 vs 原值 0)
            if old_val is not None and type(val) != type(old_val):
                try:
                    if float(val) == float(int(old_val) if isinstance(old_val, (int, float)) else 0):
                        continue
                except (TypeError, ValueError):
                    pass
            out.append(Edit(path=edit_path, value=val))
        return out



# =================== PlayerNN 背包页 ===================
class PlayerBagPage(EditModeMixin, QWidget):
    """
    单页:展示角色的背包详情(批 1 只读,批 2 加编辑)

    容器选择(Q3 A:用户拍板):
    - equips    (可改容器 — 批 2)
    - consumes  (可改容器 — 批 2)
    - nowEquips (身上穿的 — 只读永久,不能改)

    UI 结构(2026-06-20 改造 2 + 6-21 升级):
    - 顶部第 1 行:容器下拉(equips/consumes/nowEquips) + 长度 + 锁定标签
    - 顶部第 2 行:物品下拉(当前容器内所有物品,按"物品名 (id)"排序)
    - 右下方:QScrollArea + 动态 layout,显示选中物品的详情

    详情面板分支(2026-06-21 拍板):
    - consumes 容器:Q2 简化面板,只显示物品名 + 数量
    - equips / nowEquips 容器:Q1 B 横排,左列强化+提示 / 右列附加属性

    字段精简(2026-06-20 用户拍板):
    - 显示: 物品名 / id / star / typeLv / attack / magicPower / defense
            / _str / _dex / _luk / _int / _maxHP / _maxMP
            / moveSpeed / jumpForce + 1 个固定提示
    - 不显示(38 个): num/nowNum/position, req_* 6 个, setItemID/allProp/bullet/type/
            classification/attackSpeed, action/action2, pdd/bdr/igpddr/mdd,
            fixTimes/goldenHammer/platinumHammer/knockback/bdR/imdR/mhpR/mmpR,
            gainType/price/shopPrice/type/5 个 bool 标志
    - tuc 替换为固定文本提示: "修改强化等级不影响属性" (Q2 A,放在强化分组下面)
    """

    # 容器列表(显示文本 -> data key)
    CONTAINER_OPTIONS = [
        ('🎒 背包装备 (equips)', 'equips'),
        ('🧪 消耗品 (consumes)', 'consumes'),
        ('👕 身上装备 (nowEquips) 🔒', 'nowEquips'),
    ]

    STAR_OPTIONS = [
        ('0星', 0), ('1星', 1), ('2星', 2), ('3星', 3), ('4星', 4), ('5星', 5),
    ]
    TYPELV_OPTIONS = [
        ('C级', 0), ('B级', 1), ('A级', 2), ('S级', 3), ('SS级', 4),
    ]

    EQUIP_EDITABLE_FIELDS = [
        ('star', 'equipInfo.star', (0, 999)),
        ('typeLv', 'equipInfo.typeLv', (0, 999)),
        ('攻击力 attack', 'equipInfo.attack', (0, 2_000_000_000)),
        ('魔法力 magicPower', 'equipInfo.magicPower', (0, 2_000_000_000)),
        ('防御力 defense', 'equipInfo.defense', (0, 2_000_000_000)),
        ('力量 _str', 'equipInfo._str', (0, 2_000_000_000)),
        ('敏捷 _dex', 'equipInfo._dex', (0, 2_000_000_000)),
        ('运气 _luk', 'equipInfo._luk', (0, 2_000_000_000)),
        ('智力 _int', 'equipInfo._int', (0, 2_000_000_000)),
        ('最大血量 _maxHP', 'equipInfo._maxHP', (0, 2_000_000_000)),
        ('最大魔量 _maxMP', 'equipInfo._maxMP', (0, 2_000_000_000)),
        ('移动速度 moveSpeed', 'equipInfo.moveSpeed', (0, 2_000_000_000)),
        ('跳跃力 jumpForce', 'equipInfo.jumpForce', (0, 2_000_000_000)),
    ]

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        EditModeMixin.__init__(self, page_title='背包')
        self._data: dict | None = None
        self._current_key: str = 'equips'
        self._items_in_container: list = []
        self._current_item_index: int = 0
        self._bag_edit_widgets: dict = {}  # {field_key: (display_widget, editor_widget)}
        self._build_ui()

    def _build_ui(self):
        from PyQt5.QtWidgets import QScrollArea, QComboBox
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # EditModeMixin 的开关/按钮
        self._build_edit_mode_controls(layout)

        # ===== 顶部第 1 行:容器下拉 + 长度 + 锁状态 =====
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel('容器:'))
        self.cmb_container = QComboBox()
        for display, key in self.CONTAINER_OPTIONS:
            self.cmb_container.addItem(display, key)
        self.cmb_container.currentIndexChanged.connect(self._on_container_changed)
        top_row.addWidget(self.cmb_container)
        self.lbl_count = QLabel('0 件')
        top_row.addWidget(self.lbl_count)
        top_row.addStretch()
        self.lbl_locked = QLabel('')  # 容器只读时显示 "🔒 永久只读"
        self.lbl_locked.setStyleSheet('color: #c00; font-weight: bold;')
        top_row.addWidget(self.lbl_locked)
        layout.addLayout(top_row)

        # ===== 顶部第 2 行:物品下拉 =====
        item_row = QHBoxLayout()
        item_row.addWidget(QLabel('物品:'))
        self.cmb_item = QComboBox()
        self.cmb_item.setMinimumWidth(400)
        self.cmb_item.currentIndexChanged.connect(self._on_item_changed)
        item_row.addWidget(self.cmb_item, 1)
        layout.addLayout(item_row)

        # ===== 详情面板(滚动,动态生成 QFormLayout) =====
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self.scroll, 1)

        # 详情面板内的 QWidget(每次切物品重建 form_layout)
        self.detail_widget = QWidget()
        self.scroll.setWidget(self.detail_widget)
        # 默认空 form 布局,后续 _render_item_details 重建
        self.detail_widget.setLayout(QVBoxLayout())
        self.detail_widget.layout().setContentsMargins(12, 12, 12, 12)
        self.detail_widget.layout().setSpacing(8)

        self._update_lock_label()

    def _update_lock_label(self):
        """nowEquips 是身上穿的,永久只读,显示红色提示"""
        if self._current_key == 'nowEquips':
            self.lbl_locked.setText('🔒 身上穿的不能改')
        else:
            self.lbl_locked.setText('')

    def _on_container_changed(self, index: int):
        self._current_key = self.cmb_container.itemData(index)
        self._update_lock_label()
        # 重建物品下拉(用户已选 Q3 A:保留两个下拉)
        self._refresh_item_dropdown()

    def _on_item_changed(self, index: int):
        # 找到选中的 item dict 并渲染详情
        self._current_item_index = index
        if 0 <= index < len(self._items_in_container):
            item = self._items_in_container[index]
            self._render_item_details(item)

    def set_data(self, data: dict):
        self._data = data
        self.take_data_snapshot(data)
        # 注意:先设置数据,再重建物品下拉(_refresh_item_dropdown 会读 _data)
        self._refresh_item_dropdown()

    def _refresh_item_dropdown(self):
        """从当前容器里读所有物品,填充到物品下拉,默认选第一个"""
        if self._data is None:
            self._items_in_container = []
            self.cmb_item.clear()
            self._render_empty('(无数据)')
            return

        items = self._data.get(self._current_key, []) or []
        self._items_in_container = [it for it in items if isinstance(it, dict)]
        self.lbl_count.setText(f'{len(self._items_in_container)} 件')

        # 暂存当前选中,避免触发 currentIndexChanged 时旧 index 无效
        self.cmb_item.blockSignals(True)
        self.cmb_item.clear()

        if not self._items_in_container:
            self.cmb_item.addItem('(该容器为空)', None)
            self.cmb_item.setEnabled(False)
            self.cmb_item.blockSignals(False)
            self._render_empty('该容器为空')
            return

        self.cmb_item.setEnabled(True)
        for it in self._items_in_container:
            item_id = str(it.get('id', ''))
            name = get_item_name(item_id)
            display_name = name if name else item_id  # 未命中 fallback 到 id(Q1 A)
            self.cmb_item.addItem(f'{display_name} ({item_id})', item_id)
        # 默认选第一个
        self.cmb_item.setCurrentIndex(0)
        self.cmb_item.blockSignals(False)
        # 主动触发一次渲染
        self._on_item_changed(0)

    def _clear_detail_layout(self):
        """
        清理详情面板的所有子节点(QWidget + QLayout 都递归删除)。

        之前的实现只处理 takeAt(0).widget() = QWidget 的情况,
        但 _render_item_details 把多个 QFormLayout addWidget 到 QVBoxLayout,
        takeAt 取出的是 layout,要递归处理 layout 的 children。
        """
        layout = self.detail_widget.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                break
            # 可能是 widget 或 layout
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
                continue
            sub_layout = item.layout()
            if sub_layout is not None:
                # 递归清理子 layout 的内容
                self._recursive_clear_layout(sub_layout)
                sub_layout.setParent(None)

    def _recursive_clear_layout(self, layout):
        """递归清空一个 layout 及其所有子 layout 的 widgets/layouts"""
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
                continue
            sub_layout = item.layout()
            if sub_layout is not None:
                self._recursive_clear_layout(sub_layout)
                sub_layout.setParent(None)

    def _render_empty(self, msg: str):
        """详情面板显示占位文本(空容器 / 无数据)"""
        self._clear_detail_layout()
        self.detail_widget.layout().addWidget(QLabel(msg))

    def _render_item_details(self, item: dict):
        """
        渲染单个物品的精简字段详情 + 1 个固定提示。

        字段分支(2026-06-21 拍板):
        - consumes 容器(消耗品):走 _render_consumable_details,简化面板
          (Q2: 物品名 + 数量就够了,不再显示强化/附加属性)
        - equips / nowEquips 容器(装备):走下方,显示:
          - 基础信息: 物品名(大字标题) / ID
          - 🔧 强化 + 📊 附加属性 横排(Q1 B:2x2 网格,左列强化+提示 / 右列附加属性)
          - 固定提示 ⚠ 修改强化等级不影响属性(Q4 A:放在强化分组下面)

        Q3 C 判断依据:容器名 == 'consumes'
        """
        # 清理旧内容(递归处理 layout 子树)
        self._clear_detail_layout()
        self._bag_edit_widgets = {}

        # Q3 C:消耗品容器走简化分支
        if self._current_key == 'consumes':
            self._render_consumable_details(item)
            return

        ei = item.get('equipInfo', {}) if isinstance(item.get('equipInfo'), dict) else {}
        item_id = str(item.get('id', ''))
        name = get_item_name(item_id)
        display_name = name if name else item_id  # 未命中 fallback

        old_layout = self.detail_widget.layout()

        # ===== 标题(物品名 大字号) =====
        title = QLabel(display_name)
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)
        old_layout.addWidget(title)

        # ===== 基础信息(物品名 + ID) =====
        # 物品名已在标题展示,基础信息只显示 ID
        id_form = QFormLayout()
        id_form.setSpacing(6)
        id_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        id_form.addRow('ID:', QLabel(item_id))
        old_layout.addLayout(id_form)

        # ===== Q1 B:强化 + 附加属性 横排(2x2 QGridLayout) =====
        # (0,0)=强化 标题     (0,1)=附加属性 标题
        # (1,0)=强化 字段     (1,1)=附加属性 字段
        from PyQt5.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)  # 附加属性 11 字段多,给 2 倍宽度
        old_layout.addLayout(grid)

        # --- 左列(0,0)+(1,0):强化 + 提示 ---
        grid.addWidget(self._make_group_title('🔧 强化'), 0, 0)
        star_form = QFormLayout()
        star_form.setSpacing(6)
        star_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._add_bag_choice_row(star_form, 'star:', 'equipInfo.star', ei.get('star', 0), self.STAR_OPTIONS)
        self._add_bag_choice_row(star_form, 'typeLv:', 'equipInfo.typeLv', ei.get('typeLv', 0), self.TYPELV_OPTIONS)
        if self._current_key == 'nowEquips':
            star_form.addRow('position:', QLabel(str(item.get('position', ''))))
        star_form_w = QWidget()
        star_form_w.setLayout(star_form)
        grid.addWidget(star_form_w, 1, 0)
        # Q4 A:固定提示放在强化分组下面
        hint = QLabel('⚠ 修改强化等级不影响属性')
        hint.setStyleSheet('color: #c00; padding: 4px 0;')
        hint.setWordWrap(True)
        # 提示放在强化字段下面,加到强化列的 layout 容器里
        star_form_w.layout().addWidget(hint)

        # --- 右列(0,1)+(1,1):附加属性 标题 + 11 字段 ---
        grid.addWidget(self._make_group_title('📊 附加属性'), 0, 1)
        attr_form = QFormLayout()
        attr_form.setSpacing(6)
        attr_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._add_bag_edit_row(attr_form, '攻击力 attack:', 'equipInfo.attack', ei.get('attack', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '魔法力 magicPower:', 'equipInfo.magicPower', ei.get('magicPower', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '防御力 defense:', 'equipInfo.defense', ei.get('defense', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '力量 _str:', 'equipInfo._str', ei.get('_str', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '敏捷 _dex:', 'equipInfo._dex', ei.get('_dex', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '运气 _luk:', 'equipInfo._luk', ei.get('_luk', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '智力 _int:', 'equipInfo._int', ei.get('_int', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '最大血量 _maxHP:', 'equipInfo._maxHP', ei.get('_maxHP', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '最大魔量 _maxMP:', 'equipInfo._maxMP', ei.get('_maxMP', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '移动速度 moveSpeed:', 'equipInfo.moveSpeed', ei.get('moveSpeed', 0), (0, 2_000_000_000))
        self._add_bag_edit_row(attr_form, '跳跃力 jumpForce:', 'equipInfo.jumpForce', ei.get('jumpForce', 0), (0, 2_000_000_000))
        attr_form_w = QWidget()
        attr_form_w.setLayout(attr_form)
        grid.addWidget(attr_form_w, 1, 1)

        old_layout.addStretch()

        self.register_field_widgets({k: widget for k, (_, widget) in self._bag_edit_widgets.items()})
        self._apply_edit_mode_to_widgets(self.is_edit_mode)

    def _render_consumable_details(self, item: dict):
        """
        消耗品简化详情面板(Q2:物品名 + 数量就够了)。

        只显示:
        - 物品名(大字标题)
        - 数量: num 值(从容器条目顶层),编辑模式下可改为 QSpinBox
        """
        from PyQt5.QtWidgets import QSpinBox

        self._bag_edit_widgets = {}

        item_id = str(item.get('id', ''))
        name = get_item_name(item_id)
        display_name = name if name else item_id  # 未命中 fallback
        num = item.get('num') or 0  # None / 缺失 / 0 都安全显示成 0

        old_layout = self.detail_widget.layout()

        # 标题(物品名 大字号)
        title = QLabel(display_name)
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        title.setFont(f)
        old_layout.addWidget(title)

        # 数量:label + spinbox 同行,编辑模式切换
        num_row = QHBoxLayout()
        num_lbl = QLabel(f'数量: {num}')
        fn = QFont()
        fn.setPointSize(14)
        num_lbl.setFont(fn)
        num_spin = QSpinBox()
        num_spin.setRange(0, 99999)
        num_spin.setValue(int(num))
        num_spin.setVisible(False)  # 初始只读模式
        num_row.addWidget(num_lbl)
        num_row.addWidget(num_spin)
        num_row.addStretch()
        old_layout.addLayout(num_row)

        # 记录编辑控件
        self._bag_edit_widgets = {'num': (num_lbl, num_spin)}
        self.register_field_widgets({'num': num_spin})

        # 提示(告诉用户消耗品详情简化)
        hint = QLabel('(消耗品只显示名称和数量)')
        hint.setStyleSheet('color: #888; padding-top: 8px;')
        old_layout.addWidget(hint)

        old_layout.addStretch()
        # 刷新编辑模式状态(切物品后控件重建,要重新应用)
        self._apply_edit_mode_to_widgets(self.is_edit_mode)

    def _make_group_title(self, text: str) -> QLabel:
        """分组标题(灰底加粗,小一号的 emoji)"""
        lbl = QLabel(text)
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        lbl.setFont(f)
        lbl.setStyleSheet('color: #555; padding-top: 4px;')
        return lbl

    def _add_bag_edit_row(self, form, label_text: str, field_key: str, value, value_range: tuple):
        """详情面板里加一行 label/spin 组合,供编辑模式切换。"""
        from PyQt5.QtWidgets import QSpinBox

        lbl = QLabel(str(value))
        spin = QSpinBox()
        spin.setRange(value_range[0], value_range[1])
        try:
            spin.setValue(int(value))
        except (TypeError, ValueError):
            spin.setValue(0)
        spin.setVisible(False)

        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(lbl)
        row.addWidget(spin)
        row.addStretch()
        form.addRow(label_text, wrap)
        self._bag_edit_widgets[field_key] = (lbl, spin)

    def _add_bag_choice_row(self, form, label_text: str, field_key: str, value, options):
        """详情面板里加一行枚举下拉,查看时禁用显示,编辑模式下可选。"""
        from PyQt5.QtWidgets import QComboBox

        combo = QComboBox()
        try:
            current_value = int(value)
        except (TypeError, ValueError):
            current_value = 0

        found = False
        for text, data in options:
            combo.addItem(text, data)
            if data == current_value:
                found = True
        if not found:
            combo.addItem(f'未知({current_value})', current_value)

        idx = combo.findData(current_value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setEnabled(False)
        form.addRow(label_text, combo)
        self._bag_edit_widgets[field_key] = (combo, combo)

    # ---- EditModeMixin 接口实现 ----

    def _apply_edit_mode_to_widgets(self, on: bool):
        """
        切换背包页编辑模式:label ↔ spinbox。
        nowEquips 容器永远不可编辑。
        """
        if self._current_key == 'nowEquips':
            # 身上装备不能改,即使开了编辑模式也不显示 spinbox
            for key, (display_widget, editor_widget) in self._bag_edit_widgets.items():
                if display_widget is editor_widget:
                    editor_widget.setVisible(True)
                    editor_widget.setEnabled(False)
                else:
                    display_widget.setVisible(True)
                    editor_widget.setVisible(False)
            return
        for key, (display_widget, editor_widget) in self._bag_edit_widgets.items():
            if display_widget is editor_widget:
                editor_widget.setVisible(True)
                editor_widget.setEnabled(on)
            else:
                display_widget.setVisible(not on)
                editor_widget.setVisible(on)

    def _collect_edits(self):
        """
        背包页编辑:收集当前物品变更的字段。
        目前支持消耗品 num,以及 equips 容器当前装备的可见 equipInfo 属性。
        """
        if self._data is None or self._current_key == 'nowEquips':
            return []
        if not (0 <= self._current_item_index < len(self._items_in_container)):
            return []

        out = []
        idx = self._current_item_index
        # 取 snapshot 原值
        attrs_snap = self._data_snapshot.get(self._current_key, []) or [] if self._data_snapshot else []

        for key, (lbl, spin) in self._bag_edit_widgets.items():
            val = self._read_widget_value(spin)
            if val is None:
                continue
            edit_path = f'{self._current_key}.{idx}.{key}'
            # 与原值对比,没变就跳过
            if idx < len(attrs_snap) and isinstance(attrs_snap[idx], dict):
                if key.startswith('equipInfo.'):
                    equip_info = attrs_snap[idx].get('equipInfo', {}) or {}
                    old_val = equip_info.get(key.split('.', 1)[1]) if isinstance(equip_info, dict) else None
                else:
                    old_val = attrs_snap[idx].get(key)
                if old_val is not None and val == old_val:
                    continue
                if old_val is not None and type(val) != type(old_val):
                    try:
                        if float(val) == float(old_val):
                            continue
                    except (TypeError, ValueError):
                        pass
            out.append(Edit(path=edit_path, value=val))
        return out

    def _do_save(self, edits):
        """背包页保存:与属性页同模式"""
        if self._data is None:
            QMessageBox.warning(self, '保存', '没有数据可保存')
            return
        from save_editor import (
            apply_edits, write_save_atomic, backup_file, check_byte_diff_ok,
        )
        from save_codec import KEY_PLAYER

        save = self._data.get('_save_meta')
        if save is None:
            QMessageBox.warning(self, '保存', '找不到源文件路径')
            return
        path = save['path']
        key = save.get('key', KEY_PLAYER)

        data_for_edit = {k: v for k, v in self._data.items() if k != '_save_meta'}
        try:
            new_data = apply_edits(data_for_edit, edits)
        except Exception as e:
            QMessageBox.warning(self, '校验失败', str(e))
            return

        backup_file(path)
        try:
            new_raw = write_save_atomic(path, new_data, key)
        except Exception as e:
            QMessageBox.critical(self, '写盘失败', str(e))
            return

        old_raw = save.get('raw')
        if old_raw is not None:
            ok, rate, msg = check_byte_diff_ok(old_raw, new_raw)
            if not ok:
                QMessageBox.warning(self, '字节差异超限', f'字节差异 {rate:.4%} 超过硬限。\n{msg}')

        new_data['_save_meta'] = save
        save['data'] = new_data
        save['raw'] = new_raw
        self.set_data(new_data)


# =================== PlayerNN 技能页 ===================
class PlayerSkillPage(QWidget):
    """
    单页:展示角色的技能(批 1 只读,批 2 加编辑)

    数据来源:
    - nowSkills:已学技能列表(id / level / switchFlag / type),批 2 可改 level
    - skillPoint:6 元素数组(按 job 索引的剩余技能点),批 2 可改

    设计要点:
    - 批 1 全部只读,等用户给技能 ID→中文名映射表(设计稿 #11 B)再加中文列
    - skillPoint 用一行 6 个 QSpinBox 展示,跟 nowSkills 表格分开两个区域
    """

    SKILL_POINT_COUNT = 6  # skillPoint 数组固定长度

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ===== 顶部:技能点区域 =====
        sp_section = QLabel('📊 剩余技能点 (skillPoint)')
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        sp_section.setFont(f)
        layout.addWidget(sp_section)

        sp_hint = QLabel('按 job 索引的 6 个值,批 2 可改;level 不消耗这里(独立字段)')
        sp_hint.setStyleSheet('color: #666; font-size: 10px;')
        layout.addWidget(sp_hint)

        # 6 个 QSpinBox 横排
        from PyQt5.QtWidgets import QSpinBox
        sp_row = QHBoxLayout()
        self.skill_point_spins: list[QSpinBox] = []
        for i in range(self.SKILL_POINT_COUNT):
            spin = QSpinBox()
            spin.setRange(0, 9999)
            spin.setValue(0)
            spin.setEnabled(False)  # 批 1 只读
            spin.setPrefix(f'[{i}] ')
            spin.setMinimumWidth(90)
            self.skill_point_spins.append(spin)
            sp_row.addWidget(spin)
        sp_row.addStretch()
        layout.addLayout(sp_row)

        # ===== 中部:技能列表 =====
        skill_section = QLabel('⚔ 已学技能 (nowSkills)')
        skill_section.setFont(f)
        layout.addWidget(skill_section)

        skill_hint = QLabel('批 2 时 level 列可改(上限你给数据后定);中文名来自 skill_data')
        skill_hint.setStyleSheet('color: #666; font-size: 10px;')
        layout.addWidget(skill_hint)

        # 表格:技能名(id 中文名)、id、level、switchFlag、type
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['技能名', 'id', 'level', 'switchFlag', 'type'])
        # 技能名列宽一些(中文长),其他列 Stretch
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 100)  # id 列 100px
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 70)   # level 列 70px
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 100)  # switchFlag 列 100px
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(4, 80)   # type 列 80px
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        layout.addStretch()

    def set_data(self, data: dict):
        self._data = data
        self._refresh_skill_point()
        self._refresh_table()

    def _refresh_skill_point(self):
        if self._data is None:
            return
        sp = self._data.get('skillPoint', []) or []
        # 数组可能不足 6 个,补 0
        for i in range(self.SKILL_POINT_COUNT):
            val = sp[i] if i < len(sp) else 0
            try:
                self.skill_point_spins[i].setValue(int(val))
            except (TypeError, ValueError):
                self.skill_point_spins[i].setValue(0)

    def _refresh_table(self):
        if self._data is None:
            return
        skills = self._data.get('nowSkills', []) or []
        self.table.setRowCount(len(skills))
        for row, s in enumerate(skills):
            if not isinstance(s, dict):
                continue
            sid_raw = str(s.get('id', ''))
            # 查中文名:玩家存档 id 是字符串(可能带前导 0),需要 int() 才能匹配 skill_data 的 int key
            # 字符串 ID(BOSS 技能)保留字符串查
            try:
                sid_int = int(sid_raw)
                name = get_skill_name(sid_int)
                if name is None:
                    # fallback:字符串查
                    name = get_skill_name(sid_raw)
            except ValueError:
                # 字符串 ID 直接查
                name = get_skill_name(sid_raw)
            display_name = name if name else sid_raw  # 未命中 fallback 到 id
            # col 0: 技能名
            name_item = QTableWidgetItem(display_name)
            if name is None:
                name_item.setForeground(Qt.gray)
            self.table.setItem(row, 0, name_item)
            # col 1-4: id / level / switchFlag / type
            self.table.setItem(row, 1, QTableWidgetItem(sid_raw))
            self.table.setItem(row, 2, QTableWidgetItem(str(s.get('level', ''))))
            self.table.setItem(row, 3, QTableWidgetItem(str(s.get('switchFlag', ''))))
            self.table.setItem(row, 4, QTableWidgetItem(str(s.get('type', ''))))


# =================== RoleInfo 角色列表页 ===================
class RoleListPage(QWidget):
    """RoleInfo 的角色列表页:2 列(角色名 / 等级)
    角色名通过扫描 PlayerNN.json 实时查得,缺失则显示 ID"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['角色名', '等级'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def set_data(self, data: dict):
        # data 是 RoleInfo 解码结果,含 roles 列表
        # name/lev 需要从对应的 PlayerNN.json 拿
        # MainWindow 调用前需要把 loaded_saves 传进来?简化:只从 roles 显示 ID,等级空
        # 真正实现走 MainWindow._show_role_list
        self._roles = data.get('roles', []) or []
        self._refresh([])

    def set_data_with_players(self, roles: list, player_lookup: dict):
        """roles: ['Player00','Player01',...]; player_lookup: {name: {name, lev}}"""
        self.table.setRowCount(len(roles))
        for i, rid in enumerate(roles):
            info = player_lookup.get(rid)
            if info:
                name = info.get('name', '?')
                lev = str(info.get('lev', '?'))
            else:
                name = rid  # 未加载时显示 ID
                lev = '-'
            self.table.setItem(i, 0, QTableWidgetItem(str(name)))
            self.table.setItem(i, 1, QTableWidgetItem(lev))


# =================== RoleInfo 击杀记录页 ===================
class KillRecordPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel('击杀记录')
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 统计
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(12)
        self.lbl_kinds = QLabel('-')
        self.lbl_total = QLabel('-')
        big = QFont()
        big.setPointSize(14)
        self.lbl_kinds.setFont(big)
        self.lbl_total.setFont(big)
        form.addRow('怪物种类数:', self.lbl_kinds)
        form.addRow('击杀总数:', self.lbl_total)
        layout.addLayout(form)

        layout.addStretch()

    def set_data(self, data: dict):
        stats = killrecord_stats(data)
        self.lbl_kinds.setText(f'{stats["kinds"]:,}')
        self.lbl_total.setText(f'{stats["total"]:,}')


# =================== 导入多选对话框 ===================
class ImportSelectDialog(QDialog):
    """
    弹窗:列出 zip 里所有可识别的 .json,每行一个 QCheckBox
    顶部 3 个按钮:全选/全不选/反选
    底部 OK/Cancel
    """

    def __init__(self, parent, entries: list):
        super().__init__(parent)
        self.setWindowTitle('选择要导入的存档')
        self.resize(560, 480)
        self.entries = entries
        self._checkboxes = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 顶部提示
        hint = QLabel('勾选要导入的存档(存在同名文件会单独提示覆盖):')
        layout.addWidget(hint)

        # 全选/全不选/反选
        btn_row = QHBoxLayout()
        b_all = QPushButton('全选')
        b_none = QPushButton('全不选')
        b_inv = QPushButton('反选')
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none.clicked.connect(lambda: self._set_all(False))
        b_inv.clicked.connect(self._invert)
        btn_row.addWidget(b_all)
        btn_row.addWidget(b_none)
        btn_row.addWidget(b_inv)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 列表(滚动)
        self.list_widget = QListWidget()
        for entry in self.entries:
            item = QListWidgetItem()
            cb = QCheckBox(f"{entry['name']}    {entry['summary']}")
            cb.setChecked(True)
            self._checkboxes.append(cb)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, cb)
        layout.addWidget(self.list_widget)

        # OK / Cancel
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText('确定')
        bb.button(QDialogButtonBox.Cancel).setText('取消')
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _set_all(self, checked: bool):
        for cb in self._checkboxes:
            cb.setChecked(checked)

    def _invert(self):
        for cb in self._checkboxes:
            cb.setChecked(not cb.isChecked())

    def selected_names(self) -> list:
        return [e['name'] for e, cb in zip(self.entries, self._checkboxes) if cb.isChecked()]


# =================== 主窗口 ===================
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('枫叶存档查看器')
        self.resize(1100, 700)

        # 已加载存档: {name: {'path': Path, 'kind': str, 'data': dict, 'raw': bytes}}
        self.saves = {}
        # zip 导入时的中间数据
        self._pending_zip = None
        self._pending_entries = None

        self._build_toolbar()
        self._build_central()
        self.setStatusBar(QStatusBar())

        # 启动时加载 item_data.ITEMS(物品名数据库)
        self._load_items_dict()
        # 启动时加载 skill_data.SKILLS(技能名数据库)
        self._load_skills_dict()

        # 启动时自动加载默认目录
        self.reload_default_dir()

    # ---------- 工具栏 ----------
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        a_open = QAction('📂 打开存档目录', self)
        a_open.triggered.connect(self.on_open_dir)
        tb.addAction(a_open)

        a_export = QAction('📦 导出全部', self)
        a_export.triggered.connect(self.on_export)
        tb.addAction(a_export)

        a_import = QAction('📥 导入 zip', self)
        a_import.triggered.connect(self.on_import)
        tb.addAction(a_import)

        tb.addSeparator()

        a_refresh = QAction('⟳ 刷新', self)
        a_refresh.triggered.connect(self.reload_default_dir)
        tb.addAction(a_refresh)

        a_about = QAction('ℹ 关于', self)
        a_about.triggered.connect(self.on_about)
        tb.addAction(a_about)

    # ---------- 中心区域:树 + 右侧分页 ----------
    def _build_central(self):
        splitter = QSplitter(Qt.Horizontal)

        # 左侧树
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(220)
        self.tree.currentItemChanged.connect(self._on_tree_changed)
        splitter.addWidget(self.tree)

        # 右侧 stacked
        self.stack = QStackedWidget()
        self.player_page = PlayerOverviewPage()     # index 1
        self.player_bag_page = PlayerBagPage()       # index 4
        self.player_skill_page = PlayerSkillPage()   # index 5
        self.role_list_page = RoleListPage()         # index 2
        self.killrecord_page = KillRecordPage()      # index 3
        self.empty_page = QLabel('请选择左侧节点')
        self.empty_page.setAlignment(Qt.AlignCenter)
        self.empty_page.setStyleSheet('color: gray; font-size: 14px;')

        self.stack.addWidget(self.empty_page)            # 0
        self.stack.addWidget(self.player_page)           # 1
        self.stack.addWidget(self.role_list_page)        # 2
        self.stack.addWidget(self.killrecord_page)       # 3
        self.stack.addWidget(self.player_bag_page)       # 4
        self.stack.addWidget(self.player_skill_page)     # 5
        splitter.addWidget(self.stack)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        self.setCentralWidget(splitter)

    # ---------- 加载物品/技能数据(2026-06-19 改为 Python 模块直接导入) ----------
    def _load_items_dict(self):
        """
        启动时调用:从 item_data.ITEMS 加载物品名数据库。
        数据来自 Python 模块(由 gen_data.py 从 items.json 生成),无需读 JSON 文件。
        加载失败不弹错误框,只在状态栏提示(容错)。
        """
        import item_db
        n = item_db.load_from_dict(ITEMS, 'item_data.ITEMS')
        if n == 0 and item_db.load_error():
            self._items_load_msg = f'物品数据加载失败: {item_db.load_error()}'
        else:
            self._items_load_msg = f'已加载 {n} 条物品名 (item_data.ITEMS)'

    def _load_skills_dict(self):
        """
        启动时调用:从 skill_data.SKILLS 加载技能名数据库。
        同物品模式,Python 模块直接导入,无需读 JSON。
        """
        import skill_db
        n = skill_db.load_from_dict(SKILLS, 'skill_data.SKILLS')
        if n == 0 and skill_db.load_error():
            self._skills_load_msg = f'技能数据加载失败: {skill_db.load_error()}'
        else:
            self._skills_load_msg = f'已加载 {n} 条技能名 (skill_data.SKILLS)'

    def reload_default_dir(self):
        save_dir = default_save_dir()
        files = collect_saves(save_dir)

        self.saves.clear()
        self.tree.clear()

        if not files:
            placeholder = QTreeWidgetItem([f'(未找到存档: {save_dir})'])
            self.tree.addTopLevelItem(placeholder)
            self.stack.setCurrentIndex(0)
            self.statusBar().showMessage(f'默认目录无存档: {save_dir}')
            return

        loaded = 0
        for f in files:
            try:
                raw = f.read_bytes()
                info = classify(f.name)
                if info is None:
                    continue
                kind, key = info
                data = decode(raw, key)
                self.saves[f.name] = {
                    'path': f, 'kind': kind, 'data': data, 'raw': raw,
                }
                # 注入 _save_meta 供 PlayerOverviewPage._do_save 读取文件路径/密钥
                data['_save_meta'] = self.saves[f.name]
                loaded += 1
            except Exception as e:
                self.statusBar().showMessage(f'加载 {f.name} 失败: {e}')

        self._rebuild_tree()
        items_msg = getattr(self, '_items_load_msg', '')
        skills_msg = getattr(self, '_skills_load_msg', '')
        extras = []
        if items_msg:
            extras.append(items_msg)
        if skills_msg:
            extras.append(skills_msg)
        extra_str = f"  |  {' / '.join(extras)}" if extras else ''
        self.statusBar().showMessage(
            f'已加载 {loaded} 个存档(目录: {save_dir}){extra_str}  时间: {datetime.now():%H:%M:%S}'
        )

    def on_open_dir(self):
        """用系统文件管理器打开默认存档目录"""
        save_dir = default_save_dir()
        if not save_dir.exists():
            # 目录不存在,提示一下
            QMessageBox.information(
                self, '打开存档目录',
                f'目录不存在,可能是游戏从未启动过:\n{save_dir}'
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(save_dir)))
        self.statusBar().showMessage(f'已打开: {save_dir}')

    def _rebuild_tree(self):
        self.tree.clear()

        # 节点 item 用元数据 (name, page_index, save_name) 区分
        # page_index: 0=empty, 1=player, 2=role_list, 3=killrecord
        # 实际我们用 (kind, sub) 来定位
        # 先 RoleInfo(若有),再按 Player00/01/... 顺序
        names = sorted(self.saves.keys(), key=lambda n: (n != 'RoleInfo.json', n))

        for name in names:
            save = self.saves[name]
            top = QTreeWidgetItem([name])
            top.setData(0, Qt.UserRole, ('file', name))

            if save['kind'] == 'role_info':
                child1 = QTreeWidgetItem(['👥 角色列表'])
                child1.setData(0, Qt.UserRole, ('page', name, 'role_list'))
                top.addChild(child1)
                child2 = QTreeWidgetItem(['⚔ 击杀记录'])
                child2.setData(0, Qt.UserRole, ('page', name, 'killrecord'))
                top.addChild(child2)
            else:
                # 角色存档:节点文本只显示名字
                top.setText(0, summarize_player(save['data']).split('·')[0])
                # 加 3 个子节点对应 3 个 page
                c_overview = QTreeWidgetItem(['📊 属性'])
                c_overview.setData(0, Qt.UserRole, ('page', name, 'overview'))
                top.addChild(c_overview)
                c_bag = QTreeWidgetItem(['🎒 背包'])
                c_bag.setData(0, Qt.UserRole, ('page', name, 'bag'))
                top.addChild(c_bag)
                c_skill = QTreeWidgetItem(['⚔ 技能'])
                c_skill.setData(0, Qt.UserRole, ('page', name, 'skill'))
                top.addChild(c_skill)

            self.tree.addTopLevelItem(top)

        self.tree.expandAll()

    # ---------- 树点击事件 ----------
    def _on_tree_changed(self, current, previous):
        if current is None:
            self.stack.setCurrentIndex(0)
            return
        meta = current.data(0, Qt.UserRole)
        if not meta:
            self.stack.setCurrentIndex(0)
            return
        if meta[0] == 'file':
            # 点击文件节点:RoleInfo 不做特殊处理(没子节点)
            # PlayerNN 节点直接显示总览
            save = self.saves.get(meta[1])
            if save is None:
                self.stack.setCurrentIndex(0)
                return
            if save['kind'] == 'player':
                self.player_page.set_data(save['data'])
                self.stack.setCurrentIndex(1)
            else:
                self.stack.setCurrentIndex(0)
            return
        if meta[0] == 'page':
            _, save_name, sub = meta
            save = self.saves.get(save_name)
            if save is None:
                self.stack.setCurrentIndex(0)
                return
            if sub == 'overview':
                self.player_page.set_data(save['data'])
                self.stack.setCurrentIndex(1)
            elif sub == 'bag':
                self.player_bag_page.set_data(save['data'])
                self.stack.setCurrentIndex(4)
            elif sub == 'skill':
                self.player_skill_page.set_data(save['data'])
                self.stack.setCurrentIndex(5)
            elif sub == 'role_list':
                # 构造 player_lookup: {'Player00': {'name': '希尔', 'lev': 184}, ...}
                # key 用文件名去掉 .json 后缀,匹配 RoleInfo.roles 里的 ID
                lookup = {}
                for n, s in self.saves.items():
                    if s['kind'] == 'player':
                        key = n[:-5] if n.endswith('.json') else n
                        lookup[key] = {
                            'name': s['data'].get('name', '?'),
                            'lev': s['data'].get('lev', '?'),
                        }
                self.role_list_page.set_data_with_players(
                    save['data'].get('roles', []) or [], lookup
                )
                self.stack.setCurrentIndex(2)
            elif sub == 'killrecord':
                self.killrecord_page.set_data(save['data'])
                self.stack.setCurrentIndex(3)
            return
        self.stack.setCurrentIndex(0)

    # ---------- 导出 ----------
    def on_export(self):
        save_dir = default_save_dir()
        files = collect_saves(save_dir)
        if not files:
            QMessageBox.warning(self, '导出', f'没找到存档:\n{save_dir}')
            return

        default_name = f'saves_{datetime.now():%Y%m%d-%H%M%S}.zip'
        zip_str, _ = QFileDialog.getSaveFileName(
            self, '导出存档', str(Path.home() / default_name), 'ZIP (*.zip)'
        )
        if not zip_str:
            return
        zip_path = Path(zip_str)

        try:
            result = export_zip(save_dir, zip_path)
        except Exception as e:
            QMessageBox.critical(self, '导出失败', str(e))
            return

        QMessageBox.information(
            self, '导出完成',
            f'已打包 {result["count"]} 个文件\n'
            f'大小: {result["size"]/1024:.1f} KB\n'
            f'位置: {zip_path}'
        )
        self.statusBar().showMessage(f'已导出: {zip_path}')

    # ---------- 导入 ----------
    def on_import(self):
        # 1) 选 zip
        zip_str, _ = QFileDialog.getOpenFileName(
            self, '选择 zip 存档', str(Path.home()), 'ZIP (*.zip)'
        )
        if not zip_str:
            return
        zip_path = Path(zip_str)

        # 2) 读 zip
        try:
            entries = read_zip_entries(zip_path)
        except Exception as e:
            QMessageBox.critical(self, '读取 zip 失败', str(e))
            return
        if not entries:
            QMessageBox.warning(self, '导入', 'zip 里没有可识别的存档\n(只识别 RoleInfo.json / Player*.json)')
            return

        # 3) 多选
        dlg = ImportSelectDialog(self, entries)
        if dlg.exec_() != QDialog.Accepted:
            return
        selected = dlg.selected_names()
        if not selected:
            QMessageBox.information(self, '导入', '未选择任何存档')
            return

        # 4) 写回
        save_dir = default_save_dir()
        # 先检查已存在的文件,逐个弹覆盖确认
        overwrite_yes_to_all = False
        overwritten, skipped_overwrite, will_import = [], [], []

        for name in selected:
            target = save_dir / name
            if target.exists() and not overwrite_yes_to_all:
                # 读一下原存档做对比
                try:
                    info = classify(name)
                    if info:
                        kind, key = info
                        old_data = decode(target.read_bytes(), key)
                        old_summary = (
                            summarize_player(old_data) if kind == 'player'
                            else summarize_role_info(old_data)
                        )
                except Exception:
                    old_summary = '(读取失败)'

                # 在 entries 里找这个 name 的新摘要
                new_entry = next((e for e in entries if e['name'] == name), None)
                new_summary = new_entry['summary'] if new_entry else '?'

                reply = QMessageBox.question(
                    self, '覆盖确认',
                    f'{name} 目标目录已存在,是否覆盖?\n\n'
                    f'当前: {old_summary}\n'
                    f'导入: {new_summary}',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    skipped_overwrite.append(name)
                    continue
                overwrite_yes_to_all = True  # 第一次 yes 后一路 yes
                overwritten.append(name)
            else:
                overwritten.append(name)

        # 5) 实际导入
        result = import_zip_entries(zip_path, save_dir, overwritten)
        imported = result['imported']
        failed = result['failed']  # zip 内确实找不到的条目(理论上不应出现)

        # 6) 反馈
        msg_parts = []
        if imported:
            msg_parts.append(f'已导入 {len(imported)} 个:\n' + '\n'.join(imported))
        if skipped_overwrite:
            msg_parts.append('用户取消覆盖:\n' + '\n'.join(skipped_overwrite))
        if failed:
            msg_parts.append('zip 内缺失(异常):\n' + '\n'.join(failed))
        if not msg_parts:
            msg_parts.append('未执行任何操作')

        QMessageBox.information(self, '导入结果', '\n\n'.join(msg_parts))
        self.reload_default_dir()  # 刷树

    # ---------- 关于 ----------
    def on_about(self):
        QMessageBox.about(
            self, '关于',
            '<h3>枫叶存档查看器</h3>'
            '<p>Unity 冒险岛存档浏览器(只读)</p>'
            '<p>支持两类存档:</p>'
            '<ul>'
            '<li>RoleInfo.json (账号全局)</li>'
            '<li>PlayerNN.json (单角色)</li>'
            '</ul>'
            '<p>默认存档目录:<br>'
            f'{default_save_dir()}</p>'
        )


# =================== 入口 ===================
def main():
    app = QApplication(sys.argv)
    app.setApplicationName('枫叶存档查看器')
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

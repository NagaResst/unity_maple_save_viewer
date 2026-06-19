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
    summarize_player, summarize_role_info,
)
from save_paths import default_save_dir
from item_db import get_name as get_item_name, is_loaded as items_db_loaded
from zip_io import (
    collect_saves, export_zip, import_zip_entries, read_zip_entries,
)


# =================== PlayerNN 总览页 ===================
class PlayerOverviewPage(QWidget):
    """
    单页:展示角色的基础属性 + 战斗属性(全部只读)
    批 1:展示 14 个核心战斗字段 + 4 个顶层字段
    批 2:加编辑模式开关 + QLineEdit 切换可改

    字段分组(2026-06-19 用户拍板):
    - 身份区(只读):名字 / 等级 / 经验值 / 金币
    - 战斗核心(批 2 可改):_maxHP / _maxMP / attack / magicPower / attackSpeed / defense
    - 战斗进阶(批 2 可改):CriticalRate / CriticalDamage / percentDamage / finalDamage
                       imdR / bdR / stanceProp / abilityPoint
    - 四维(只读):_str / _dex / _luk / _int
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        # 用 QScrollArea 包一层,字段多了之后窗口缩小时可滚动
        from PyQt5.QtWidgets import QScrollArea
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 角色名(大字号)
        self.lbl_name = QLabel('-')
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.lbl_name.setFont(font)
        layout.addWidget(self.lbl_name)

        # ====== 区域 1:身份(只读 4 项) ======
        layout.addWidget(self._make_section_title('📋 身份信息'))
        id_form = QFormLayout()
        id_form.setSpacing(8)
        id_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_lev = QLabel('-')
        self.lbl_exp = QLabel('-')
        self.lbl_coin = QLabel('-')
        id_form.addRow('等级:', self.lbl_lev)
        id_form.addRow('经验值:', self.lbl_exp)
        id_form.addRow('金币:', self.lbl_coin)
        layout.addLayout(id_form)

        # ====== 区域 2:四维(只读 4 项) ======
        layout.addWidget(self._make_section_title('💪 四维属性'))
        stat_form = QFormLayout()
        stat_form.setSpacing(8)
        stat_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_str = QLabel('-')
        self.lbl_dex = QLabel('-')
        self.lbl_luk = QLabel('-')
        self.lbl_int = QLabel('-')
        stat_form.addRow('力量 _str:', self.lbl_str)
        stat_form.addRow('敏捷 _dex:', self.lbl_dex)
        stat_form.addRow('运气 _luk:', self.lbl_luk)
        stat_form.addRow('智力 _int:', self.lbl_int)
        layout.addLayout(stat_form)

        # ====== 区域 3:战斗核心(批 2 可改 6 项) ======
        layout.addWidget(self._make_section_title('⚔ 战斗核心'))
        combat_form = QFormLayout()
        combat_form.setSpacing(8)
        combat_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_maxhp = QLabel('-')
        self.lbl_maxmp = QLabel('-')
        self.lbl_attack = QLabel('-')
        self.lbl_magic = QLabel('-')
        self.lbl_aspd = QLabel('-')
        self.lbl_def = QLabel('-')
        combat_form.addRow('最大血量 _maxHP:', self.lbl_maxhp)
        combat_form.addRow('最大魔量 _maxMP:', self.lbl_maxmp)
        combat_form.addRow('攻击力 attack:', self.lbl_attack)
        combat_form.addRow('魔法力 magicPower:', self.lbl_magic)
        combat_form.addRow('攻击速度 attackSpeed:', self.lbl_aspd)
        combat_form.addRow('防御力 defense:', self.lbl_def)
        layout.addLayout(combat_form)

        # ====== 区域 4:战斗进阶(批 2 可改 8 项) ======
        layout.addWidget(self._make_section_title('🎯 战斗进阶'))
        adv_form = QFormLayout()
        adv_form.setSpacing(8)
        adv_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_crit_rate = QLabel('-')
        self.lbl_crit_dmg = QLabel('-')
        self.lbl_pct_dmg = QLabel('-')
        self.lbl_final_dmg = QLabel('-')
        self.lbl_imdr = QLabel('-')
        self.lbl_bdr = QLabel('-')
        self.lbl_stance = QLabel('-')
        self.lbl_ap = QLabel('-')
        adv_form.addRow('暴击率 CriticalRate:', self.lbl_crit_rate)
        adv_form.addRow('暴击伤害 CriticalDamage:', self.lbl_crit_dmg)
        adv_form.addRow('增伤百分比 percentDamage:', self.lbl_pct_dmg)
        adv_form.addRow('最终伤害 finalDamage:', self.lbl_final_dmg)
        adv_form.addRow('无视防御 imdR:', self.lbl_imdr)
        adv_form.addRow('首领伤害 bdR:', self.lbl_bdr)
        adv_form.addRow('稳如泰山 stanceProp:', self.lbl_stance)
        adv_form.addRow('可用能力值 abilityPoint:', self.lbl_ap)
        layout.addLayout(adv_form)

        layout.addStretch()

    def _make_section_title(self, text: str) -> QLabel:
        """生成区块标题(灰底加粗)"""
        lbl = QLabel(text)
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        lbl.setFont(f)
        lbl.setStyleSheet('color: #555; padding-top: 8px;')
        return lbl

    def set_data(self, data: dict):
        # 身份区
        self.lbl_name.setText(str(data.get('name', '?')))
        self.lbl_lev.setText(str(data.get('lev', '?')))
        self.lbl_exp.setText(f'{int(data.get("currentExp", 0)):,}')
        self.lbl_coin.setText(f'{int(data.get("coin", 0)):,}')

        # 四维(只读)
        attrs = data.get('attributes', {}) or {}
        self.lbl_str.setText(str(attrs.get('_str', '?')))
        self.lbl_dex.setText(str(attrs.get('_dex', '?')))
        self.lbl_luk.setText(str(attrs.get('_luk', '?')))
        self.lbl_int.setText(str(attrs.get('_int', '?')))

        # 战斗核心 6 项
        self.lbl_maxhp.setText(f'{int(attrs.get("_maxHP", 0)):,}')
        self.lbl_maxmp.setText(f'{int(attrs.get("_maxMP", 0)):,}')
        self.lbl_attack.setText(str(attrs.get('attack', '?')))
        self.lbl_magic.setText(str(attrs.get('magicPower', '?')))
        self.lbl_aspd.setText(str(attrs.get('attackSpeed', '?')))
        self.lbl_def.setText(f'{int(attrs.get("defense", 0)):,}')

        # 战斗进阶 8 项
        self.lbl_crit_rate.setText(str(attrs.get('CriticalRate', '?')))
        self.lbl_crit_dmg.setText(str(attrs.get('CriticalDamage', '?')))
        self.lbl_pct_dmg.setText(str(attrs.get('percentDamage', '?')))
        self.lbl_final_dmg.setText(str(attrs.get('finalDamage', '?')))
        self.lbl_imdr.setText(str(attrs.get('imdR', '?')))
        self.lbl_bdr.setText(str(attrs.get('bdR', '?')))
        self.lbl_stance.setText(str(attrs.get('stanceProp', '?')))
        self.lbl_ap.setText(str(attrs.get('abilityPoint', '?')))


# =================== PlayerNN 背包页 ===================
class PlayerBagPage(QWidget):
    """
    单页:展示角色的背包(批 1 只读,批 2 加编辑)

    容器选择(Q3 A:用户拍板):
    - equips    (可改容器 — 批 2)
    - consumes  (可改容器 — 批 2)
    - nowEquips (身上穿的 — 只读永久,不能改)

    每个条目字段(7 列 + 1 标志):
    - id / num / nowNum / position / star / typeLv / tuc / flags(只读)
    - 批 2 时 num/nowNum 可改(上限 999),position 不让手动改,其他也只读
    """

    # 容器列表(显示文本 -> data key)
    CONTAINER_OPTIONS = [
        ('🎒 背包装备 (equips)', 'equips'),
        ('🧪 消耗品 (consumes)', 'consumes'),
        ('👕 身上装备 (nowEquips) 🔒', 'nowEquips'),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict | None = None
        self._current_key: str = 'equips'
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 顶部:容器选择 + 长度 + 锁状态
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel('容器:'))
        from PyQt5.QtWidgets import QComboBox
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

        # 表格(9 列:id + 物品名 + 7 字段)
        # "物品名" 列宽设大一点,因为中文名字符长
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            'id', '物品名', 'num', 'nowNum', 'position',
            'star', 'typeLv', 'tuc', 'flags(只读)',
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 物品名列(列 1)用 Interactive 模式,设宽一些
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 100)  # id 列 100px
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

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
        self._refresh_table()

    def set_data(self, data: dict):
        self._data = data
        self._refresh_table()

    def _refresh_table(self):
        if self._data is None:
            return
        items = self._data.get(self._current_key, []) or []
        self.table.setRowCount(len(items))
        self.lbl_count.setText(f'{len(items)} 件')
        for row, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            # star/typeLv/tuc 实际在 equipInfo 嵌套里(skill 文档 §2.2 标错,这里拍平展示)
            # 批 2 编辑时要改 it['equipInfo']['star'] 等
            ei = it.get('equipInfo', {}) if isinstance(it.get('equipInfo'), dict) else {}
            item_id = str(it.get('id', ''))
            # col 0: id
            self.table.setItem(row, 0, QTableWidgetItem(item_id))
            # col 1: 物品名(Q2 A:未命中只显示 ID,不崩)
            name = get_item_name(item_id)
            display_name = name if name else item_id  # 未命中 fallback 到 id
            name_item = QTableWidgetItem(display_name)
            # 已查到的物品名用正常颜色,未命中的用灰色提示(Q1/Q2 设计)
            if name is None:
                name_item.setForeground(Qt.gray)
            self.table.setItem(row, 1, name_item)
            # col 2-8: 原 7 字段
            self.table.setItem(row, 2, QTableWidgetItem(str(it.get('num', ''))))
            self.table.setItem(row, 3, QTableWidgetItem(str(it.get('nowNum', ''))))
            self.table.setItem(row, 4, QTableWidgetItem(str(it.get('position', ''))))
            self.table.setItem(row, 5, QTableWidgetItem(str(ei.get('star', ''))))
            self.table.setItem(row, 6, QTableWidgetItem(str(ei.get('typeLv', ''))))
            self.table.setItem(row, 7, QTableWidgetItem(str(ei.get('tuc', ''))))
            # flags 拼接显示
            flags = []
            for k in ('bulletFlag', 'cantUse', 'petFlag', 'chairFlag', 'hitNumberFlag'):
                if it.get(k):
                    flags.append(k.replace('Flag', ''))
            self.table.setItem(row, 8, QTableWidgetItem(','.join(flags) if flags else '-'))


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

        skill_hint = QLabel('批 2 时 level 列可改(上限你给数据后定);中文名等映射表')
        skill_hint.setStyleSheet('color: #666; font-size: 10px;')
        layout.addWidget(skill_hint)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['id', 'level', 'switchFlag', 'type'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
            self.table.setItem(row, 0, QTableWidgetItem(str(s.get('id', ''))))
            self.table.setItem(row, 1, QTableWidgetItem(str(s.get('level', ''))))
            self.table.setItem(row, 2, QTableWidgetItem(str(s.get('switchFlag', ''))))
            self.table.setItem(row, 3, QTableWidgetItem(str(s.get('type', ''))))


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

        # 启动时加载 items.json(物品名数据库,Q1 A 方案)
        self._load_items_json()

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

    # ---------- 加载 items.json(物品名数据库) ----------
    def _load_items_json(self):
        """
        启动时调用:从 items.json 加载物品名数据库。
        三段 fallback(Q1 A):GUI 同目录 / cwd / 开发路径。
        加载失败不弹错误框,只在状态栏提示(Q1 容错)。
        """
        import item_db
        path = self._find_items_json()
        if path is None:
            self._items_load_msg = '未找到 items.json,物品名仅显示 ID'
            return
        n = item_db.load_from_json(path)
        if n == 0 and item_db.load_error():
            self._items_load_msg = f'物品数据加载失败: {item_db.load_error()}'
        else:
            self._items_load_msg = f'已加载 {n} 条物品名 (来自 {path})'

    def _find_items_json(self):
        """
        三段 fallback 查找 items.json:
        1. GUI 同目录(适合 pyinstaller 打包后跟 exe 一起)
        2. 当前工作目录
        3. 开发环境 fallback 路径
        """
        candidates = [
            Path(__file__).parent / 'items.json',
            Path.cwd() / 'items.json',
            Path('/home/nagaresst/workspace/2026-06-17打包/items.json'),
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    # ---------- 加载默认目录 ----------
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
                loaded += 1
            except Exception as e:
                self.statusBar().showMessage(f'加载 {f.name} 失败: {e}')

        self._rebuild_tree()
        items_msg = getattr(self, '_items_load_msg', '')
        if items_msg:
            items_msg = f'  |  {items_msg}'
        self.statusBar().showMessage(
            f'已加载 {loaded} 个存档(目录: {save_dir}){items_msg}  时间: {datetime.now():%H:%M:%S}'
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

"""
viewer.py - PyQt5 主窗口
"""
import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
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
from zip_io import (
    collect_saves, export_zip, import_zip_entries, read_zip_entries,
)


# =================== PlayerNN 总览页 ===================
class PlayerOverviewPage(QWidget):
    """单页:名称 / 等级 / 经验 / 金币 / 职业 / 背包物品总数"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 角色名(大字号)
        self.lbl_name = QLabel('-')
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.lbl_name.setFont(font)
        layout.addWidget(self.lbl_name)

        # 表单区
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.lbl_lev = QLabel('-')
        self.lbl_exp = QLabel('-')
        self.lbl_coin = QLabel('-')
        self.lbl_bag = QLabel('-')

        form.addRow('等级:', self.lbl_lev)
        form.addRow('经验值:', self.lbl_exp)
        form.addRow('金币:', self.lbl_coin)
        form.addRow('背包物品总数:', self.lbl_bag)
        layout.addLayout(form)

        # 职业列表
        layout.addWidget(QLabel('职业:'))
        self.list_jobs = QListWidget()
        self.list_jobs.setMaximumHeight(140)
        layout.addWidget(self.list_jobs)

        layout.addStretch()

    def set_data(self, data: dict):
        self.lbl_name.setText(str(data.get('name', '?')))
        self.lbl_lev.setText(str(data.get('lev', '?')))
        exp = data.get('currentExp', 0)
        self.lbl_exp.setText(f'{int(exp):,}')
        coin = data.get('coin', 0)
        self.lbl_coin.setText(f'{int(coin):,}')
        self.lbl_bag.setText(f'{bag_total(data)}')

        self.list_jobs.clear()
        for jid in data.get('jobList', []) or []:
            item = QListWidgetItem(map_job_id(jid))
            self.list_jobs.addItem(item)


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

        # 启动时自动加载默认目录
        self.reload_default_dir()

    # ---------- 工具栏 ----------
    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        a_open = QAction('📂 打开存档目录', self)
        a_open.triggered.connect(self.reload_default_dir)
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
        self.player_page = PlayerOverviewPage()
        self.role_list_page = RoleListPage()
        self.killrecord_page = KillRecordPage()
        self.empty_page = QLabel('请选择左侧节点')
        self.empty_page.setAlignment(Qt.AlignCenter)
        self.empty_page.setStyleSheet('color: gray; font-size: 14px;')

        self.stack.addWidget(self.empty_page)            # 0
        self.stack.addWidget(self.player_page)           # 1
        self.stack.addWidget(self.role_list_page)        # 2
        self.stack.addWidget(self.killrecord_page)       # 3
        splitter.addWidget(self.stack)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        self.setCentralWidget(splitter)

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
        self.statusBar().showMessage(
            f'已加载 {loaded} 个存档(目录: {save_dir})  时间: {datetime.now():%H:%M:%S}'
        )

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
                # 角色存档:节点文本只显示名字,点击节点本身显示总览
                top.setText(0, summarize_player(save['data']).split('·')[0])

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
        skipped_missing = result['skipped_existing']  # zip 内 missing

        # 6) 反馈
        msg_parts = []
        if imported:
            msg_parts.append(f'已导入 {len(imported)} 个:\n' + '\n'.join(imported))
        if skipped_overwrite:
            msg_parts.append('用户取消覆盖:\n' + '\n'.join(skipped_overwrite))
        if skipped_missing:
            msg_parts.append('zip 内缺失:\n' + '\n'.join(skipped_missing))
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
            '<li>RoleInfo.json (密钥 0x9F)</li>'
            '<li>PlayerNN.json (密钥 0x77)</li>'
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

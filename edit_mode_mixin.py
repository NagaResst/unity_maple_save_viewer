"""
edit_mode_mixin.py - 共享"编辑模式"机制(2026-06-20 拍板)

为 PlayerOverviewPage / PlayerBagPage 提供:
- 顶部右侧 QCheckBox "☐ 编辑模式" 开关(E1 A)
- 底部按钮条 "💾 保存 / ↩ 撤销"
- 控件映射表 self._field_widgets: {path: QWidget} (供 save 收集)
- 编辑状态 self._edits: list[Edit] (Edit 来自 save_editor)
- 原始 data snapshot (用于 ↩ 撤销)
- emit signal edit_mode_changed(bool)

设计约束(2026-06-20 拍板 E1-E4):
- E1 A: 开关在页面顶部右侧
- E3 B: 保存时弹 QMessageBox.question(Yes/No),简单确认
- 每页独立(C6 拍板),不在 mixin 里做"全局编辑模式"

使用方法:
    class PlayerOverviewPage(EditModeMixin, QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)  # 必须先 QWidget.__init__,再 EditModeMixin
            EditModeMixin.__init__(self, parent, page_title='基础属性')
            self._build_ui()
            ...
"""
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from save_editor import Edit


class EditModeMixin:
    """
    Mixin: 必须在 QWidget 子类里用,且要在 __init__ 显式调 EditModeMixin.__init__。

    提供:
    - self.edit_mode_check (QCheckBox, 放在顶部右侧)
    - self.btn_save / btn_undo / btn_cancel (QPushButton)
    - self.is_edit_mode (bool)
    - self.original_data_snapshot (deepcopy 的 data,用于撤销)
    - self._edits (list[Edit], 收集控件值)
    - self._field_widgets (dict[path -> QWidget],供 self._collect_edits 用)
    - enter_edit_mode() / exit_edit_mode(force=False) / toggle_edit_mode()
    - save_requested 信号: 子类把 save_handler 接上(默认调 _default_save_handler)
    """

    def __init__(self, parent: Optional[QWidget] = None, page_title: str = '页面'):
        # 状态字段
        self._page_title = page_title
        self.is_edit_mode = False
        self._edits: list[Edit] = []
        self._field_widgets: dict = {}
        self._data_snapshot = None  # 原始 data 的 deepcopy(撤销用)

        # UI 控件(在 _build_edit_mode_controls 里建)
        self.edit_mode_check: Optional[QCheckBox] = None
        self.btn_save: Optional[QPushButton] = None
        self.btn_undo: Optional[QPushButton] = None
        self._edit_buttons_row: Optional[QHBoxLayout] = None

    # ---- 子类必须实现的接口 ----

    def _build_edit_mode_controls(self, top_layout: QVBoxLayout):
        """
        子类在 _build_ui 里调,会在页面布局的:
        - 顶部(第一个 addLayout)插入"开关行"(右上角)
        - 底部(最后 addLayout)插入"保存/撤销/取消行"
        """
        # 顶部行:标题 + 弹簧 + 开关
        top_row = QHBoxLayout()
        top_row.addStretch()
        self.edit_mode_check = QCheckBox('编辑模式')
        self.edit_mode_check.toggled.connect(self._on_edit_mode_toggled)
        top_row.addWidget(self.edit_mode_check)
        top_layout.addLayout(top_row)

        # 底部行:撤销 / 保存
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_undo = QPushButton('撤销')
        self.btn_undo.clicked.connect(self._on_undo_clicked)
        self.btn_undo.setEnabled(False)
        btn_row.addWidget(self.btn_undo)

        self.btn_save = QPushButton('保存')
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_save.setEnabled(False)
        btn_row.addWidget(self.btn_save)

        top_layout.addLayout(btn_row)
        self._edit_buttons_row = btn_row

    def register_field_widgets(self, widgets: dict):
        """
        子类在 _build_ui 末尾调,把 self._field_widgets 传进来,
        mixin 会给每个 spinbox/lineedit 装上 valueChanged/textChanged 监听,
        值变化时启用 save/undo 按钮。

        widgets: {path: QWidget} (QSpinBox/QDoubleSpinBox/QLineEdit)
        """
        from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit
        for path, w in widgets.items():
            # spin 类的 valueChanged(int|float)
            if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.valueChanged.connect(self._on_field_changed)
            elif isinstance(w, QLineEdit):
                w.textChanged.connect(self._on_field_changed)
        # 同时也存一份到 self._mixin_tracked_widgets(供 _disconnect_fields 用)
        self._mixin_tracked_widgets = list(widgets.values())

    def _on_field_changed(self, *args, **kwargs):
        """控件值变化 → 启用 save/undo 按钮(只在编辑模式下)"""
        if not self.is_edit_mode:
            return
        self.btn_save.setEnabled(True)
        self.btn_undo.setEnabled(True)

    def _on_edit_mode_toggled(self, checked: bool):
        """子类可重写以同步控件状态;默认调 enter/exit"""
        if checked:
            self.enter_edit_mode()
        else:
            self.exit_edit_mode(force=True)

    def enter_edit_mode(self):
        """进入编辑模式:不撤销"""
        if self.is_edit_mode:
            return
        self.is_edit_mode = True
        # 子类负责把 label 换成 spinbox
        if hasattr(self, '_apply_edit_mode_to_widgets'):
            self._apply_edit_mode_to_widgets(True)
        # 同步按钮可用性
        self.btn_undo.setEnabled(False)  # 刚进入,无修改
        self.btn_save.setEnabled(False)  # 还没改
        # 状态条
        if hasattr(self, 'statusBar') and callable(self.statusBar):
            try:
                self.statusBar().showMessage(f'{self._page_title}: 编辑模式', 3000)
            except Exception:
                pass

    def exit_edit_mode(self, force: bool = False):
        """
        退出编辑模式。
        - force=True: 撤销所有未保存修改(E4 A 取消按钮的语义)
        - force=False: 子类可重写以做"是否保留"询问
        """
        if not self.is_edit_mode:
            return
        self.is_edit_mode = False
        # 撤销未保存修改
        if force:
            self._revert_widgets_from_snapshot()
        # 子类负责把 spinbox 换回 label
        if hasattr(self, '_apply_edit_mode_to_widgets'):
            self._apply_edit_mode_to_widgets(False)
        # 同步 UI
        self.edit_mode_check.setChecked(False)
        self.btn_undo.setEnabled(False)
        self.btn_save.setEnabled(False)
        # 清空编辑状态
        self._edits.clear()

    def _on_undo_clicked(self):
        """撤销:恢复到进入编辑模式时的状态(回滚到 _data_snapshot)"""
        self._revert_widgets_from_snapshot()
        # 同步按钮
        self.btn_undo.setEnabled(False)
        self.btn_save.setEnabled(False)
        self._edits.clear()

    def _on_save_clicked(self):
        """
        E3 B: 简单 QMessageBox.question 确认。
        校验在 save_editor.apply_edits 里做(包括武器守卫)。
        """
        # 收集所有控件的当前值
        edits = self._collect_edits()
        if not edits:
            QMessageBox.information(self, '保存', '没有任何修改。')
            return

        # E3 B: 简单 Yes/No 弹窗
        lines = [f'  {ed.path}: {ed.value!r}' for ed in edits]
        msg = f'确认保存以下 {len(edits)} 项修改?\n\n' + '\n'.join(lines) + '\n\n(原文件会备份为 .bak)'
        ret = QMessageBox.question(
            self, '确认保存', msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return

        # 子类实现:调 save_editor.apply_edits + write_save_atomic + backup_file
        if hasattr(self, '_do_save'):
            self._do_save(edits)
        # 保存成功后再处理
        self.btn_undo.setEnabled(False)
        self.btn_save.setEnabled(False)
        self._edits.clear()
        if hasattr(self, 'statusBar') and callable(self.statusBar):
            try:
                self.statusBar().showMessage(f'{self._page_title}: 已保存', 3000)
            except Exception:
                pass

    # ---- 子类可重写 ----

    def _collect_edits(self) -> list:
        """
        收集 self._field_widgets 的当前值,返回 Edit 列表。
        默认实现假设 _field_widgets 结构是 {path: QWidget} (QSpinBox/QLineEdit 等)。
        子类如果用不同的结构(比如 PlayerOverviewPage 用 {path: (lbl, spin)}),要重写。
        """
        out = []
        for path, w in self._field_widgets.items():
            val = self._read_widget_value(w)
            if val is not None:
                out.append(Edit(path=path, value=val))
        return out

    def _make_edit_path(self, field_key: str) -> str:
        """
        子类重写以转换内部字段 key 到 save_editor 的 path:
        - PlayerOverviewPage: 'attack' -> 'attributes.attack', 'lev' -> 'lev'
        - PlayerBagPage: 'star' -> 'equips.0.equipInfo.star'(根据当前选中物品 index)
        默认:原样返回 field_key(给背包/技能页用,自己重写)
        """
        return field_key

    def _read_widget_value(self, w) -> object:
        """从控件读值。QSpinBox/QDoubleSpinBox 取 value(),QLineEdit 取 text() 转 int。"""
        from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit
        if isinstance(w, QSpinBox) or isinstance(w, QDoubleSpinBox):
            return w.value()
        if isinstance(w, QLineEdit):
            text = w.text().strip()
            if not text:
                return None
            try:
                return int(text)
            except ValueError:
                try:
                    return float(text)
                except ValueError:
                    return text
        return None

    def _revert_widgets_from_snapshot(self):
        """
        把控件恢复到 self._data_snapshot(进编辑模式时的原值)。
        子类可重写。
        默认:重新调 set_data 走一遍(因为 set_data 会重置所有控件)。
        """
        if self._data_snapshot is not None and hasattr(self, 'set_data'):
            self.set_data(self._data_snapshot)

    def take_data_snapshot(self, data: dict):
        """子类在 set_data 里调,存原始 data 用于撤销"""
        import copy
        self._data_snapshot = copy.deepcopy(data)

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout, 
                             QLineEdit, QMessageBox, QAbstractItemView)
from PyQt6.QtCore import Qt, QPoint
from qfluentwidgets import (SubtitleLabel, PrimaryPushButton, PushButton, 
                            FluentIcon as FIF, TransparentToolButton, ComboBox, CheckBox)
from ...core.models import LogicRule

class LogicEditorDialog(QDialog):
    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 700)
        self.logic_rules = [LogicRule.from_dict(r.to_dict()) for r in action.advanced_logic]
        
        self.setupUI()
        self.refresh_table()
        self.oldPos = self.pos()

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()

    def setupUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self.container.setObjectName("dialogContainer")
        self.container.setStyleSheet("""
            QWidget#dialogContainer {
                background-color: rgb(32, 32, 32);
                border: 1px solid rgb(60, 60, 60);
                border-radius: 8px;
            }
            QTableWidget {
                background-color: rgb(40, 40, 40);
                color: white;
                border: 1px solid rgb(60, 60, 60);
                border-radius: 4px;
                gridline-color: rgb(60, 60, 60);
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: rgb(50, 50, 50);
                color: white;
                border: none;
                padding: 4px;
            }
            QLabel { color: white; }
            QLineEdit { background-color: rgb(40, 40, 40); color: white; border: 1px solid rgb(60, 60, 60); padding: 4px; border-radius: 4px; }
            QGroupBox { color: white; font-weight: bold; border: 1px solid rgb(60, 60, 60); margin-top: 10px; border-radius: 5px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
        """)
        main_layout.addWidget(self.container)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = SubtitleLabel(f"Advanced Logic - {self.action.type.title()}", self)
        title_label.setStyleSheet("color: white;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        close_btn = TransparentToolButton(FIF.CLOSE, self)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Enabled", "Trigger", "Description", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)
        
        # Editor Section
        self.editor_group = QGroupBox("Rule Editor")
        self.editor_layout = QFormLayout(self.editor_group)
        
        self.trigger_combo = ComboBox()
        self.trigger_combo.addItems(["condition", "on_start", "on_success", "on_failure"])
        self.trigger_combo.currentTextChanged.connect(self.update_form_fields)
        self.editor_layout.addRow("Trigger:", self.trigger_combo)
        
        self.var_edit = QLineEdit()
        self.editor_layout.addRow("Variable:", self.var_edit)
        
        self.op_combo = ComboBox()
        self.editor_layout.addRow("Operator:", self.op_combo)
        
        self.val_edit = QLineEdit()
        self.editor_layout.addRow("Value:", self.val_edit)
        
        # Buttons for Editor
        editor_btn_layout = QHBoxLayout()
        self.add_btn = PrimaryPushButton("Add New Rule", self)
        self.add_btn.clicked.connect(self.add_rule)
        
        self.update_btn = PushButton("Update Selected", self)
        self.update_btn.clicked.connect(self.update_rule)
        self.update_btn.setEnabled(False)
        
        self.delete_btn = PushButton("Delete Selected", self)
        self.delete_btn.clicked.connect(self.delete_rule)
        self.delete_btn.setEnabled(False)
        
        editor_btn_layout.addWidget(self.add_btn)
        editor_btn_layout.addWidget(self.update_btn)
        editor_btn_layout.addWidget(self.delete_btn)
        self.editor_layout.addRow(editor_btn_layout)
        
        layout.addWidget(self.editor_group)
        
        # Footer
        footer_layout = QHBoxLayout()
        save_btn = PrimaryPushButton("Save Changes", self)
        save_btn.clicked.connect(self.save_data)
        cancel_btn = PushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addStretch()
        footer_layout.addWidget(save_btn)
        footer_layout.addWidget(cancel_btn)
        layout.addLayout(footer_layout)
        
        # Initial State
        self.update_form_fields("condition")

    def update_form_fields(self, trigger):
        self.op_combo.clear()
        if trigger == "condition":
            self.op_combo.addItems(["==", "!=", ">", "<", ">=", "<=", "exists", "not_exists"])
        else:
            self.op_combo.addItems(["set", "increment", "decrement"])

    def refresh_table(self):
        self.table.setRowCount(0)
        for i, rule in enumerate(self.logic_rules):
            self.table.insertRow(i)
            
            # Enabled Checkbox
            chk = CheckBox()
            chk.setChecked(rule.enabled)
            chk.stateChanged.connect(lambda state, r=rule: setattr(r, 'enabled', state == 2))
            # Center checkbox
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_layout.setContentsMargins(0,0,0,0)
            self.table.setCellWidget(i, 0, chk_widget)
            
            # Trigger
            self.table.setItem(i, 1, QTableWidgetItem(rule.trigger))
            
            # Description
            data = rule.data
            desc = f"{data.get('var', '?')} {data.get('op', '?')} {data.get('val', '')}"
            self.table.setItem(i, 2, QTableWidgetItem(desc))
            
            # Actions (Delete/Edit handled by selection, but maybe visual indicator?)
            self.table.setItem(i, 3, QTableWidgetItem(""))

    def on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            rule = self.logic_rules[row]
            self.load_rule_to_form(rule)
            self.update_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.add_btn.setText("Add as New")
        else:
            self.update_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.add_btn.setText("Add New Rule")

    def load_rule_to_form(self, rule):
        self.trigger_combo.setCurrentText(rule.trigger)
        self.var_edit.setText(str(rule.data.get("var", "")))
        self.update_form_fields(rule.trigger) # Refresh ops
        self.op_combo.setCurrentText(str(rule.data.get("op", "")))
        self.val_edit.setText(str(rule.data.get("val", "")))

    def get_rule_from_form(self):
        trigger = self.trigger_combo.currentText()
        data = {
            "var": self.var_edit.text(),
            "op": self.op_combo.currentText(),
            "val": self.val_edit.text()
        }
        return LogicRule(trigger=trigger, data=data, enabled=True)

    def add_rule(self):
        rule = self.get_rule_from_form()
        self.logic_rules.append(rule)
        self.refresh_table()
        # Clear form? Or keep for easy dup? Keep.

    def update_rule(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        row = rows[0].row()
        
        # Get data from form
        new_rule = self.get_rule_from_form()
        # Preserve enabled state of the existing rule
        new_rule.enabled = self.logic_rules[row].enabled
        
        self.logic_rules[row] = new_rule
        self.refresh_table()
        self.table.selectRow(row) # Keep selection

    def delete_rule(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        row = rows[0].row()
        del self.logic_rules[row]
        self.refresh_table()
        self.update_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

    def save_data(self):
        self.action.advanced_logic = self.logic_rules
        self.accept()

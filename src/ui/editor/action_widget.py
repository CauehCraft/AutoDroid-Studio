from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel)
from PyQt6.QtCore import Qt
from qfluentwidgets import FluentIcon as FIF, TransparentToolButton
from ...core.models import (ClickAction, WaitAction, LoopStartAction, LoopEndAction, OCRAction)

class ActionItemWidget(QWidget):
    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.action = action
        self.is_editing = False
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 5, 10, 5)
        
        # Icon based on type
        icon = FIF.PLAY
        if isinstance(action, ClickAction): icon = FIF.SEND
        elif isinstance(action, WaitAction): icon = FIF.HISTORY
        elif isinstance(action, LoopStartAction): icon = FIF.SYNC
        elif isinstance(action, LoopEndAction): icon = FIF.SYNC
        elif isinstance(action, OCRAction): icon = FIF.VIEW
        
        # Label
        type_str = action.type.replace('_', ' ').title()
        if isinstance(action, LoopStartAction): type_str = "Loop Start"
        if isinstance(action, LoopEndAction): type_str = "Loop End"
        
        self.label = QLabel(f"{type_str} - {action.description or 'No desc'}")
        self.label.setStyleSheet("color: white; font-weight: bold;")
        self.layout.addWidget(self.label)
        
        self.layout.addStretch(1)
        
        # Buttons
        self.editBtn = TransparentToolButton(FIF.EDIT, self)
        self.editBtn.setToolTip("Edit")
        self.editBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.editBtn.clicked.connect(self.on_edit)
        self.layout.addWidget(self.editBtn)
        
        self.testBtn = TransparentToolButton(FIF.PLAY, self)
        self.testBtn.setToolTip("Test Action")
        self.testBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.testBtn.clicked.connect(self.on_test)
        self.layout.addWidget(self.testBtn)
        
        self.stopBtn = TransparentToolButton(FIF.CLOSE, self)
        self.stopBtn.setToolTip("Stop Test")
        self.stopBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stopBtn.clicked.connect(self.on_stop)
        self.stopBtn.hide() # Hidden by default
        self.layout.addWidget(self.stopBtn)
        
        self.duplicateBtn = TransparentToolButton(FIF.COPY, self)
        self.duplicateBtn.setToolTip("Duplicate")
        self.duplicateBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.duplicateBtn.clicked.connect(self.on_duplicate)
        self.layout.addWidget(self.duplicateBtn)
        
        self.deleteBtn = TransparentToolButton(FIF.DELETE, self)
        self.deleteBtn.setToolTip("Delete")
        self.deleteBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deleteBtn.clicked.connect(self.on_delete)
        self.layout.addWidget(self.deleteBtn)
        
        # Hide buttons initially
        self.editBtn.hide()
        self.testBtn.hide()
        self.duplicateBtn.hide()
        self.deleteBtn.hide()
        
        # Callbacks
        self.edit_callback = None
        self.test_callback = None
        self.stop_callback = None
        self.duplicate_callback = None
        self.delete_callback = None

        self.is_loop_start = False
        self.is_loop_end = False
        self.update_style()

    def set_editing_state(self, is_editing):
        self.is_editing = is_editing
        self.update_style()
        
        if is_editing:
            self.editBtn.show()
            self.testBtn.show()
            self.duplicateBtn.show()
            self.deleteBtn.show()
        else:
            self.editBtn.hide()
            self.testBtn.hide()
            self.duplicateBtn.hide()
            self.deleteBtn.hide()

    def set_loop_style(self, is_start=False, is_end=False):
        self.is_loop_start = is_start
        self.is_loop_end = is_end
        self.update_style()

    def update_style(self):
        style = "ActionItemWidget { "
        
        # Border
        borders = []
        if self.is_editing:
             borders.append("border: none")
        elif self.is_loop_start or self.is_loop_end:
            borders.append("border-left: 2px solid #00A6FB")
        else:
            borders.append("border: none")
            
        style += "; ".join(borders) + "; "
        
        # Background and Radius
        if self.is_editing:
            # Use selection style (blue-ish background)
            style += "background-color: #009faa; border-radius: 5px; "
            if "border: 2px solid #00A6FB" in style:
                style = style.replace("border: 2px solid #00A6FB", "border: none")
        elif self.is_loop_start or self.is_loop_end:
            style += "background-color: #252525; "
        else:
            style += "background-color: transparent; "
            
        style += "}"
        self.setStyleSheet(style)


    def enterEvent(self, event):
        self.editBtn.show()
        self.testBtn.show()
        self.duplicateBtn.show()
        self.deleteBtn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_editing:
            self.editBtn.hide()
            self.testBtn.hide()
            self.duplicateBtn.hide()
            self.deleteBtn.hide()
        super().leaveEvent(event)
        
    def on_edit(self):
        if self.edit_callback: self.edit_callback(self.action)
        
    def on_test(self):
        if self.test_callback: self.test_callback(self.action)
        
    def on_stop(self):
        if self.stop_callback:
            self.stop_callback(self.action)

    def on_duplicate(self):
        if self.duplicate_callback:
            self.duplicate_callback(self.action)
            
    def on_delete(self):
        if self.delete_callback:
            self.delete_callback(self.action)
        


    def set_running_state(self, is_running):
        if is_running:
            self.testBtn.hide()
            self.stopBtn.show()
            self.editBtn.setEnabled(False)
            self.duplicateBtn.setEnabled(False)
            self.deleteBtn.setEnabled(False)
        else:
            self.testBtn.show()
            self.stopBtn.hide()
            self.editBtn.setEnabled(True)
            self.duplicateBtn.setEnabled(True)
            self.deleteBtn.setEnabled(True)

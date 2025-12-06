import json
import os
import threading
import time
import traceback

from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSlot, QMetaObject, Q_ARG
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QSizePolicy, QSpinBox, QSplitter,
                             QTableWidget, QTableWidgetItem, QTextEdit,
                             QToolButton, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CardWidget, CheckBox, ComboBox,
                            DoubleSpinBox, FlowLayout, FluentIcon as FIF,
                            LineEdit, MessageDialog, PrimaryPushButton,
                            PushButton, SpinBox, SubtitleLabel,
                            TransparentToolButton)

from ...core.action_factory import ActionFactory
from ...core.adb_manager import AdbManager
from ...core.asset_manager import AssetManager
from ...core.automation_engine import MacroRunner
from ...core.models import (Action, ClickAction, ClickImageAction, ConditionAction,
                            LoopAction, LoopEndAction, LoopStartAction, Macro,
                            MultiAction, MultiRegion, OCRAction, Point, PolygonRegion,
                            Region, Size, SwipeAction, VarAction, WaitAction)
from ...utils.logger import app_logger
from ..styles import COMMON_STYLE
from .action_widget import ActionItemWidget
from .logic_editor import LogicEditorDialog
from .properties_editor import PropertiesEditor


class MacroEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("editorInterface")
        self.adb = AdbManager()
        self.assets = AssetManager()
        self.current_macro = Macro(name="New Macro", target_resolution=Size(1080, 1920))
        self.current_file_path = None  # Track current macro file
        self.runner = None
        self.setupUI()
        self.setupConnections()
        self.setStyleSheet(COMMON_STYLE)

    def update_action_log(self, msg):
        """Slot to update the action log viewer if it exists"""
        if hasattr(self, 'action_log_viewer') and self.action_log_viewer:
            try:
                self.action_log_viewer.append(msg.strip())
                # Auto scroll
                sb = self.action_log_viewer.verticalScrollBar()
                sb.setValue(sb.maximum())
            except RuntimeError:
                pass

    def setupUI(self):
        self.hBoxLayout = QHBoxLayout(self)
        
        # Splitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.hBoxLayout.addWidget(self.splitter)
        
        self._setup_action_panel()
        self._setup_properties_panel()
        
        # Set initial sizes
        self.splitter.setSizes([350, 800])

    def _setup_action_panel(self):
        # Left Panel: Action List
        self.actionPanel = CardWidget(self)
        self.actionLayout = QVBoxLayout(self.actionPanel)
        
        # Macro Title
        self.macroTitleLabel = SubtitleLabel('New Macro', self.actionPanel)
        self.macroTitleLabel.setStyleSheet("color: #00A6FB; font-weight: bold;")
        self.actionLayout.addWidget(self.macroTitleLabel)
        
        self.actionLayout.addWidget(SubtitleLabel('Actions', self.actionPanel))
        
        self._setup_control_bar()
        
        self.actionList = QListWidget(self.actionPanel)
        self.actionList.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.actionList.setDefaultDropAction(Qt.DropAction.MoveAction)
        # Override dropEvent to handle reordering
        self.actionList.dropEvent = self.on_action_drop
        self.actionLayout.addWidget(self.actionList)
        
        self._setup_action_buttons()
        
        self.splitter.addWidget(self.actionPanel)

    def _setup_control_bar(self):
        # Control Bar
        self.controlLayout = QHBoxLayout()
        self.deviceCombo = ComboBox(self.actionPanel)
        self.refreshDevices()
        self.refreshDevicesBtn = PushButton('Refresh', self.actionPanel)
        self.runBtn = PrimaryPushButton('Run', self.actionPanel)
        self.pauseBtn = PushButton('Pause', self.actionPanel)
        self.pauseBtn.setEnabled(False)
        self.stopBtn = PushButton('Stop', self.actionPanel)
        self.stopBtn.setEnabled(False)
        
        self.controlLayout.addWidget(self.deviceCombo)
        self.controlLayout.addWidget(self.refreshDevicesBtn)
        self.controlLayout.addWidget(self.runBtn)
        self.controlLayout.addWidget(self.pauseBtn)
        self.controlLayout.addWidget(self.stopBtn)
        
        self.saveBtn = PushButton('Save Macro', self.actionPanel)
        self.controlLayout.addWidget(self.saveBtn)
        
        self.actionLayout.addLayout(self.controlLayout)

    def _setup_action_buttons(self):
        # Buttons
        self.btnLayout = FlowLayout()
        self.btnLayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.btnLayout.setContentsMargins(0, 10, 0, 0)
        self.addWaitBtn = PushButton('Add Wait', self.actionPanel)
        self.addClickBtn = PushButton('Add Click', self.actionPanel)
        self.addImageClickBtn = PushButton('Add Image Click', self.actionPanel)
        self.addVarBtn = PushButton('Add Var', self.actionPanel)
        
        self.btnLayout.addWidget(self.addWaitBtn)
        self.btnLayout.addWidget(self.addClickBtn)
        self.btnLayout.addWidget(self.addImageClickBtn)
        self.addOCRBtn = PushButton('Add OCR', self.actionPanel)
        self.btnLayout.addWidget(self.addOCRBtn)
        self.btnLayout.addWidget(self.addVarBtn)
        
        self.addSwipeBtn = PushButton('Add Swipe', self.actionPanel)
        self.addMultiBtn = PushButton('Add Multi', self.actionPanel)
        self.addLoopBtn = PushButton('Add Loop', self.actionPanel)
        
        self.btnLayout.addWidget(self.addSwipeBtn)
        self.btnLayout.addWidget(self.addMultiBtn)
        self.btnLayout.addWidget(self.addLoopBtn)
        
        self.actionLayout.addLayout(self.btnLayout)

    def _setup_properties_panel(self):
        # Right Panel: Properties
        self.properties_editor = PropertiesEditor(self)
        self.splitter.addWidget(self.properties_editor)

    def setupConnections(self):
        self.addWaitBtn.clicked.connect(self.add_wait_action)
        self.addClickBtn.clicked.connect(self.add_click_action)
        self.addImageClickBtn.clicked.connect(self.add_image_click_action)
        self.addOCRBtn.clicked.connect(self.add_ocr_action)
        self.addVarBtn.clicked.connect(self.add_var_action)
        self.addSwipeBtn.clicked.connect(self.add_swipe_action)
        self.addMultiBtn.clicked.connect(self.add_multi_action)
        self.addLoopBtn.clicked.connect(self.add_loop_action)
        
        self.runBtn.clicked.connect(self.run_macro)
        self.pauseBtn.clicked.connect(self.pause_macro)
        self.stopBtn.clicked.connect(self.stop_macro)
        self.saveBtn.clicked.connect(self.save_macro)
        self.refreshDevicesBtn.clicked.connect(self.refreshDevices)

    def on_action_drop(self, event):
        # Perform default drop behavior
        super(QListWidget, self.actionList).dropEvent(event)
        
        # Reconstruct actions list from UI order
        new_actions = []
        for i in range(self.actionList.count()):
            item = self.actionList.item(i)
            widget = self.actionList.itemWidget(item)
            if widget and hasattr(widget, 'action'):
                new_actions.append(widget.action)
        
        # Validate Loops
        loop_stack = []
        valid = True
        for action in new_actions:
            if isinstance(action, LoopStartAction):
                loop_stack.append(action.loop_id)
            elif isinstance(action, LoopEndAction):
                if not loop_stack or loop_stack[-1] != action.linked_loop_id:
                    valid = False
                    break
                loop_stack.pop()
        
        if loop_stack: # Unclosed loops
            valid = False
            
        if valid:
            self.current_macro.actions = new_actions
            self.refresh_list() # Refresh to update indentation
        else:
            QMessageBox.warning(self, "Invalid Order", "Loop structure is invalid. Please ensure Loop Start and End are properly nested.")
            self.refresh_list() # Revert to original order

    def delete_action(self, action=None):
        if action is None and hasattr(self, 'current_action_being_edited'):
             action = self.current_action_being_edited

        if action and action in self.current_macro.actions:
            self.current_macro.actions.remove(action)
            
            # Handle Loop Pairs
            if isinstance(action, LoopStartAction):
                to_remove = [a for a in self.current_macro.actions if isinstance(a, LoopEndAction) and a.linked_loop_id == action.loop_id]
                for a in to_remove:
                    self.current_macro.actions.remove(a)
            elif isinstance(action, LoopEndAction):
                to_remove = [a for a in self.current_macro.actions if isinstance(a, LoopStartAction) and a.loop_id == action.linked_loop_id]
                for a in to_remove:
                    self.current_macro.actions.remove(a)
            
            self.refresh_list()
            self.properties_editor.clear_layout_content(self.properties_editor.formLayout)

    def duplicate_action(self, action):
        """Duplicate an action and insert it after the original"""
        if not action or action not in self.current_macro.actions:
            return

        try:
            # 1. Get index
            idx = self.current_macro.actions.index(action)
            
            # 2. Create deep copy via dict
            data = action.to_dict()
            
            # 3. Generate new ID
            new_id = str(time.time())
            data['id'] = new_id
            
            # Handle Loop IDs to avoid conflicts
            if data['type'] == 'loop_start':
                data['loop_id'] = new_id + "_loop"
            elif data['type'] == 'loop_end':
                pass
                
            # 4. Create new action instance
            new_action = ActionFactory.create_action(data)
            
            if new_action:
                # 5. Insert after original
                self.current_macro.actions.insert(idx + 1, new_action)
                self.refresh_list()
                app_logger.info(f"Action {action.id} duplicated as {new_action.id}")
                
        except Exception as e:
            app_logger.error(f"Failed to duplicate action: {e}")
            QMessageBox.warning(self, "Error", f"Failed to duplicate action: {e}")

    def save_macro(self):
        macros_dir = "macros"
        if not os.path.exists(macros_dir):
            os.makedirs(macros_dir)
        
        if hasattr(self, 'current_file_path') and self.current_file_path:
            file_path = self.current_file_path
        else:
            filename = f"{self.current_macro.name.replace(' ', '_')}.json"
            file_path = os.path.join(macros_dir, filename)
        
        try:
            with open(file_path, 'w') as f:
                json.dump(self.current_macro.to_dict(), f, indent=2)
            self.current_file_path = file_path
            app_logger.info(f"Macro '{self.current_macro.name}' saved to {file_path}")
            
            # Use Fluent MessageDialog
            w = MessageDialog("Success", f"Macro saved successfully!", self)
            w.yesButton.setText("OK")
            w.cancelButton.hide()
            w.exec()
        except Exception as e:
            app_logger.error(f"Error saving macro: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save macro: {e}")

    def load_macro(self, file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self.current_macro = Macro(
                name=data.get("name", "Untitled"),
                target_resolution=Size(
                    data["target_resolution"]["width"],
                    data["target_resolution"]["height"]
                ),
                variables=data.get("variables", {}),
                created_at=data.get("created_at", 0)
            )
            
            for action_data in data.get("actions", []):
                action = ActionFactory.create_action(action_data)
                if action:
                    self.current_macro.actions.append(action)
            
            self.current_file_path = file_path
            self.macroTitleLabel.setText(f"📝 {self.current_macro.name}")
            
            self.refresh_list()
            app_logger.info(f"Macro '{self.current_macro.name}' loaded from {file_path}")
        except Exception as e:
            app_logger.error(f"Error loading macro: {e}")
            app_logger.error(f"Traceback: {traceback.format_exc()}")
            QMessageBox.critical(self, "Error", f"Failed to load macro: {e}")
    
    def refreshDevices(self):
        self.deviceCombo.clear()
        devices = self.adb.get_devices()
        for device in devices:
            self.deviceCombo.addItem(device.serial)

    def run_macro(self):
        serial = self.deviceCombo.currentText()
        if not serial:
            return
            
        if self.runner and self.runner.is_alive():
            return

        self.runner = MacroRunner(serial, self.current_macro, self.adb)
        self.runner.start()
        self.runBtn.setEnabled(False)
        self.pauseBtn.setEnabled(True)
        self.stopBtn.setEnabled(True)
        
        self.check_timer = threading.Timer(1.0, self.check_runner)
        self.check_timer.start()

    def check_runner(self):
        if self.runner and not self.runner.is_alive():
            self.runBtn.setEnabled(True)
            self.pauseBtn.setEnabled(False)
            self.stopBtn.setEnabled(False)
            self.pauseBtn.setText("Pause")
        else:
             self.check_timer = threading.Timer(1.0, self.check_runner)
             self.check_timer.start()

    def pause_macro(self):
        if self.runner:
            if self.runner.paused:
                self.runner.resume()
                self.pauseBtn.setText("Pause")
            else:
                self.runner.pause()
                self.pauseBtn.setText("Resume")

    def stop_macro(self):
        if self.runner:
            self.runner.stop()
            self.runner.join()
        self.runBtn.setEnabled(True)
        self.pauseBtn.setEnabled(False)
        self.stopBtn.setEnabled(False)
        self.pauseBtn.setText("Pause")

    def add_wait_action(self):
        action = WaitAction(id=str(time.time()), type="wait", duration_ms=1000, advanced_logic=[])
        self.current_macro.actions.append(action)
        self.refresh_list()

    def add_click_action(self):
        action = ClickAction(id=str(time.time()), type="click", target=Point(0,0), advanced_logic=[])
        self.current_macro.actions.append(action)
        self.refresh_list()

    def add_image_click_action(self):
        action = ClickImageAction(id=str(time.time()), type="click_image", image_name="", advanced_logic=[])
        self.current_macro.actions.append(action)
        self.refresh_list()

    def add_ocr_action(self):
        action = OCRAction(id=str(time.time()), type="ocr", region_name="", variable_name="ocr_text", advanced_logic=[])
        self.current_macro.actions.append(action)
        self.refresh_list()

    def add_var_action(self):
        action = VarAction(id=str(time.time()), type="variable", var_name="new_var", operation="set", value="0", advanced_logic=[])
        self.current_macro.actions.append(action)
        self.refresh_list()

    def add_swipe_action(self):
        action = SwipeAction(id=str(time.time()), type="swipe", start_point=Point(100, 100), end_point=Point(500, 500), advanced_logic=[])
        self.current_macro.actions.append(action)
        self.refresh_list()

    def add_multi_action(self):
        action = MultiAction(id=str(time.time()), type="multi", description="Simultaneous Actions", advanced_logic=[])
        self.current_macro.actions.append(action)
        self.refresh_list()

    def add_loop_action(self):
        loop_id = str(time.time())
        start_action = LoopStartAction(id=loop_id + "_start", type="loop_start", loop_id=loop_id, iterations=5, description="Loop Start", advanced_logic=[])
        end_action = LoopEndAction(id=loop_id + "_end", type="loop_end", linked_loop_id=loop_id, description="Loop End", advanced_logic=[])
        
        self.current_macro.actions.append(start_action)
        self.current_macro.actions.append(end_action)
        self.refresh_list()

    def refresh_list(self):
        scroll_val = 0
        if self.actionList.verticalScrollBar():
            scroll_val = self.actionList.verticalScrollBar().value()
            
        self.actionList.clear()
        loop_depth = 0
        indent_step = 20
        
        for action in self.current_macro.actions:
            item = QListWidgetItem(self.actionList)
            item.setSizeHint(QSize(0, 35))
            item.setData(Qt.ItemDataRole.UserRole, action)
            
            widget = ActionItemWidget(action)
            widget.edit_callback = self.properties_editor.show_properties
            widget.test_callback = self.test_single_action
            widget.stop_callback = self.stop_action_test
            widget.duplicate_callback = self.duplicate_action
            widget.delete_callback = self.delete_action
            
            if isinstance(action, LoopEndAction):
                loop_depth = max(0, loop_depth - 1)
                
            if loop_depth > 0:
                widget.layout.setContentsMargins(10 + (loop_depth * indent_step), 5, 10, 5)
                
            if isinstance(action, LoopStartAction):
                loop_depth += 1
                widget.set_loop_style(is_start=True)
            elif isinstance(action, LoopEndAction):
                widget.set_loop_style(is_end=True)
            
            self.actionList.setItemWidget(item, widget)
            
            if hasattr(self, 'current_action_being_edited') and self.properties_editor.current_action_being_edited == action:
                widget.set_editing_state(True)
                item.setSelected(True)

        if self.actionList.verticalScrollBar():
            self.actionList.verticalScrollBar().setValue(scroll_val)

    def on_action_selected(self, row):
        if row < 0:
            return
        item = self.actionList.item(row)
        action = item.data(Qt.ItemDataRole.UserRole)
        self.properties_editor.show_properties(action)

    def test_single_action(self, action):
        serial = self.deviceCombo.currentText()
        if not serial:
            QMessageBox.warning(self, "No Device", "Please select a device first.")
            return
            
        # Create a temporary macro
        temp_macro = Macro(name="Test Action", target_resolution=self.current_macro.target_resolution)
        
        # Determine actions to run
        actions_to_run = [action]
        
        if isinstance(action, LoopStartAction):
            # Find the matching end action
            try:
                start_idx = self.current_macro.actions.index(action)
                end_idx = -1
                
                # Search for matching LoopEndAction
                # We need to handle nested loops to find the CORRECT end action
                loop_depth = 0
                for i in range(start_idx + 1, len(self.current_macro.actions)):
                    curr = self.current_macro.actions[i]
                    if isinstance(curr, LoopStartAction):
                        loop_depth += 1
                    elif isinstance(curr, LoopEndAction):
                        if loop_depth > 0:
                            loop_depth -= 1
                        elif curr.linked_loop_id == action.loop_id:
                            end_idx = i
                            break
                
                if end_idx != -1:
                    actions_to_run = self.current_macro.actions[start_idx : end_idx + 1]
                else:
                    app_logger.warning("Could not find matching Loop End for testing.")
            except ValueError:
                pass # Action not in list?
        
        temp_macro.actions = actions_to_run
        # Copy variables
        temp_macro.variables = self.current_macro.variables.copy()
        
        # Run in a separate thread to avoid freezing UI
        def run_test():
            # Update UI to running state
            QMetaObject.invokeMethod(self, "set_action_running_state", Qt.ConnectionType.QueuedConnection, Q_ARG(object, action), Q_ARG(bool, True))
            
            self.active_test_runner = MacroRunner(serial, temp_macro, self.adb)
            self.active_test_runner.run() # Run synchronously in this thread
            
            # Update UI to stopped state
            QMetaObject.invokeMethod(self, "set_action_running_state", Qt.ConnectionType.QueuedConnection, Q_ARG(object, action), Q_ARG(bool, False))
            self.active_test_runner = None
            
        threading.Thread(target=run_test).start()

    @pyqtSlot(object, bool)
    def set_action_running_state(self, action, is_running):
        # Find the widget for this action
        for i in range(self.actionList.count()):
            item = self.actionList.item(i)
            item_action = item.data(Qt.ItemDataRole.UserRole)
            if item_action == action:
                widget = self.actionList.itemWidget(item)
                widget.set_running_state(is_running)
                break
                
    def stop_action_test(self, action):
        if hasattr(self, 'active_test_runner') and self.active_test_runner:
            self.active_test_runner.stop()

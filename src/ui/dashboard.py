import json
import os

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QMessageBox, QScrollArea, QSplitter, QWidget, QVBoxLayout, QToolButton)
from qfluentwidgets import (BodyLabel, CardWidget, CheckBox,
                            FluentIcon as FIF, MessageBoxBase, LineEdit,
                            PrimaryPushButton, PushButton, SearchLineEdit,
                            SubtitleLabel, TextEdit, MessageDialog, TransparentToolButton)

from ..core.action_factory import ActionFactory
from ..core.adb_manager import AdbManager
from ..core.automation_engine import MacroRunner
from ..core.models import Macro, Size
from ..utils.logger import app_logger
from .widgets.device_card import DeviceCard
from .styles import COMMON_STYLE, DASHBOARD_STYLE


class DevicePoller(QThread):
    devices_updated = pyqtSignal(list)

    def __init__(self, adb_manager):
        super().__init__()
        self.adb = adb_manager
        self.running = True

    def run(self):
        while self.running:
            try:
                devices = self.adb.get_devices()
                self.devices_updated.emit(devices)
            except Exception as e:
                print(f"Error polling devices: {e}")
                self.devices_updated.emit([])
            
            # Sleep for 2 seconds
            self.msleep(2000)

    def stop(self):
        self.running = False
        self.wait()

class DashboardRunner(QObject):
    status_changed = pyqtSignal(str, str) # serial, status
    variable_changed = pyqtSignal(str, str, object) # serial, var_name, value
    finished = pyqtSignal(str) # serial

    def __init__(self, serial, macro, adb_manager):
        super().__init__()
        self.serial = serial
        self.macro = macro
        self.runner = MacroRunner(serial, macro, adb_manager)
        
        # Connect callbacks
        self.runner.on_status_update = self._on_status
        self.runner.on_variable_update = self._on_var
        
    def start(self):
        self.runner.start()
        
    def stop(self):
        self.runner.stop()
        
    def pause(self):
        if self.runner.paused:
            self.runner.resume()
        else:
            self.runner.pause()
            
    def _on_status(self, status):
        self.status_changed.emit(self.serial, status)
        if status == "Finished":
            self.finished.emit(self.serial)
            
    def _on_var(self, name, value):
        self.variable_changed.emit(self.serial, name, value)

class MacroItemWidget(QWidget):
    def __init__(self, text, on_edit, on_delete, on_duplicate, parent=None):
        super().__init__(parent)
        self.text = text
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_duplicate = on_duplicate
        self.setupUI()
        
    def setupUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(10)
        
        # Macro Name Label
        self.label = BodyLabel(self.text, self)
        self.label.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        layout.addWidget(self.label, 1) # Stretch
        
        # Buttons Container
        self.btnContainer = QWidget(self)
        btnLayout = QHBoxLayout(self.btnContainer)
        btnLayout.setContentsMargins(0, 0, 0, 0)
        btnLayout.setSpacing(8)
        
        # Edit Button
        self.editBtn = TransparentToolButton(FIF.EDIT, self.btnContainer)
        self.editBtn.setToolTip("Edit Macro")
        self.editBtn.clicked.connect(self.on_edit)
        self.editBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Delete Button
        self.deleteBtn = TransparentToolButton(FIF.DELETE, self.btnContainer)
        self.deleteBtn.setToolTip("Delete Macro")
        self.deleteBtn.clicked.connect(self.on_delete)
        self.deleteBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Duplicate Button
        self.duplicateBtn = TransparentToolButton(FIF.COPY, self.btnContainer)
        self.duplicateBtn.setToolTip("Duplicate Macro")
        self.duplicateBtn.clicked.connect(self.on_duplicate)
        self.duplicateBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        btnLayout.addWidget(self.editBtn)
        btnLayout.addWidget(self.duplicateBtn)
        btnLayout.addWidget(self.deleteBtn)
        
        layout.addWidget(self.btnContainer)
        
        # Hide buttons initially
        self.btnContainer.setVisible(False)
        
    def enterEvent(self, event):
        self.btnContainer.setVisible(True)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.btnContainer.setVisible(False)
        super().leaveEvent(event)

class Dashboard(QWidget):
    macroSelected = pyqtSignal(str) # filename

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("dashboardInterface")
        self.adb = AdbManager()
        self.runners = {} # serial -> DashboardRunner
        self.device_variables = {} # serial -> dict
        self.macros_dir = "macros"
        if not os.path.exists(self.macros_dir):
            os.makedirs(self.macros_dir)
            
        self.setupUI()
        self.setupConnections()
        self.applyStyles()
        self.refresh_macros()
        
        # Poller thread
        self.poller = DevicePoller(self.adb)
        self.poller.devices_updated.connect(self.update_device_list)
        self.poller.start()

    def closeEvent(self, event):
        self.poller.stop()
        super().closeEvent(event)

    def applyStyles(self):
        self.setStyleSheet(f"{COMMON_STYLE}\n{DASHBOARD_STYLE}")

    def setupUI(self):
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.mainLayout.addWidget(self.splitter)
        
        self._setup_left_panel()
        self._setup_right_panel()
        
        self._setup_splitter()

    def _setup_splitter(self):
        self.splitter.addWidget(self.leftPanel)
        self.splitter.addWidget(self.rightPanel)
        
        # Set initial sizes (60% left, 40% right)
        self.splitter.setSizes([600, 400])
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

    def _setup_left_panel(self):
        # LEFT PANEL: Devices & Logs
        self.leftPanel = QWidget()
        self.leftLayout = QVBoxLayout(self.leftPanel)
        self.leftLayout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        self.headerLabel = SubtitleLabel('Dashboard', self)
        self.leftLayout.addWidget(self.headerLabel)
        
        # Device Section
        self.deviceContainer = QWidget()
        self.deviceLayout = QVBoxLayout(self.deviceContainer)
        self.deviceLayout.setContentsMargins(0, 0, 0, 0)
        self.deviceLayout.setSpacing(10)
        self.deviceLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setWidget(self.deviceContainer)
        self.scrollArea.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.leftLayout.addWidget(self.scrollArea, 1) # Give it stretch
        
        # Refresh Button
        self.refreshBtn = PrimaryPushButton('Refresh Devices', self)
        self.leftLayout.addWidget(self.refreshBtn)
        
        self.device_cards = {} # Map serial -> DeviceCard
        
        # Logs Section
        log_header_layout = QHBoxLayout()
        self.logLabel = BodyLabel('Logs', self)
        log_header_layout.addWidget(self.logLabel)
        
        self.logToggle = CheckBox("Enable Logging", self)
        self.logToggle.setChecked(True)
        self.logToggle.stateChanged.connect(self.toggle_logging)
        log_header_layout.addWidget(self.logToggle)
        
        self.leftLayout.addLayout(log_header_layout)
        
        self.logText = TextEdit(self)
        self.logText.setReadOnly(True)
        self.logText.setMaximumHeight(200)
        self.leftLayout.addWidget(self.logText)

    def _setup_right_panel(self):
        # RIGHT PANEL: Macro Manager
        self.rightPanel = CardWidget(self)
        self.rightLayout = QVBoxLayout(self.rightPanel)
        
        self.macroHeader = SubtitleLabel('Macros', self.rightPanel)
        self.rightLayout.addWidget(self.macroHeader)
        
        # Search & New Macro
        self.toolsLayout = QHBoxLayout()
        self.searchBar = SearchLineEdit(self.rightPanel)
        self.searchBar.setPlaceholderText("Search macros...")
        self.searchBar.textChanged.connect(self.filter_macros)
        
        self.newMacroBtn = PrimaryPushButton('New Macro', self.rightPanel)
        self.newMacroBtn.setIcon(FIF.ADD)
        self.newMacroBtn.clicked.connect(self.create_macro)
        
        self.toolsLayout.addWidget(self.searchBar)
        self.toolsLayout.addWidget(self.newMacroBtn)
        self.rightLayout.addLayout(self.toolsLayout)
        
        # Macro List
        self.macroList = QListWidget(self.rightPanel)
        self.rightLayout.addWidget(self.macroList)

    def setupConnections(self):
        self.refreshBtn.clicked.connect(self.refresh_devices_manual)
        # Connect logger signal
        try:
            app_logger.log_signal.disconnect(self.append_log)
        except: pass
        app_logger.log_signal.connect(self.append_log)

        app_logger.info("Refreshing devices...")

    def refresh_devices_manual(self):
        app_logger.info("Refreshing devices...")
        # Trigger manual refresh via adb
        devices = self.adb.get_devices()
        self.update_device_list(devices)

    def update_device_list(self, devices):
        current_serials = {d.serial for d in devices}
        
        # Remove disconnected devices
        for serial in list(self.device_cards.keys()):
            if serial not in current_serials:
                card = self.device_cards.pop(serial)
                self.deviceLayout.removeWidget(card)
                card.deleteLater()
        
        # Add new devices
        for device in devices:
            if device.serial not in self.device_cards:
                card = DeviceCard(device.serial, self.deviceContainer)
                
                # Connect signals
                card.run_signal.connect(self.start_macro)
                card.pause_signal.connect(self.toggle_pause_macro)
                card.stop_signal.connect(self.stop_macro)
                
                # Populate macros
                self.update_card_macros(card)
                
                self.device_cards[device.serial] = card
                self.deviceLayout.addWidget(card)
                
    def update_card_macros(self, card):
        macros = []
        if os.path.exists(self.macros_dir):
            for f in os.listdir(self.macros_dir):
                if f.endswith(".json"):
                    macros.append(f)
        card.set_macros(macros)

    def toggle_logging(self, state):
        app_logger.set_enabled(state == Qt.CheckState.Checked.value)

    def append_log(self, msg):
        self.logText.append(msg)
        
        # Limit log lines to 300
        doc = self.logText.document()
        if doc.blockCount() > 300:
            cursor = self.logText.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, doc.blockCount() - 300)
            cursor.removeSelectedText()
            
        # Auto scroll
        sb = self.logText.verticalScrollBar()
        sb.setValue(sb.maximum())

    # --- Macro Management Methods ---

    def refresh_macros(self):
        self.macroList.clear()
        if os.path.exists(self.macros_dir):
            for f in os.listdir(self.macros_dir):
                if f.endswith(".json"):
                    self.add_macro_item(f)
        
        # Update existing cards
        for card in self.device_cards.values():
            self.update_card_macros(card)

    def add_macro_item(self, filename):
        item = QListWidgetItem(self.macroList)
        item.setSizeHint(QSize(0, 70)) # Set fixed height for item
        
        # Create custom widget
        widget = MacroItemWidget(
            text=filename,
            on_edit=lambda: self.edit_macro(filename),
            on_delete=lambda: self.delete_macro(filename),
            on_duplicate=lambda: self.duplicate_macro(filename)
        )
        
        self.macroList.addItem(item)
        self.macroList.setItemWidget(item, widget)

    def filter_macros(self, text):
        for i in range(self.macroList.count()):
            item = self.macroList.item(i)
            widget = self.macroList.itemWidget(item)
            if widget:
                item.setHidden(text.lower() not in widget.text.lower())

    def create_macro(self):
        
        class InputDialog(MessageBoxBase):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.titleLabel = SubtitleLabel("New Macro", self)
                self.inputField = LineEdit(self)
                self.inputField.setPlaceholderText("Enter macro name")
                self.inputField.setClearButtonEnabled(True)
                
                self.viewLayout.addWidget(self.titleLabel)
                self.viewLayout.addWidget(self.inputField)
                
                self.widget.setMinimumWidth(350)
                
        w = InputDialog(self)
        if w.exec():
            name = w.inputField.text().strip()
            if name:
                filename = f"{name.replace(' ', '_')}.json"
                path = os.path.join(self.macros_dir, filename)
                
                if os.path.exists(path):
                    err = MessageDialog("Error", "Macro already exists!", self)
                    err.exec()
                    return
                
                # Create default macro
                macro = Macro(name=name, target_resolution=Size(1080, 1920))
                try:
                    with open(path, 'w') as f:
                        json.dump(macro.to_dict(), f, indent=2)
                    self.refresh_macros()
                except Exception as e:
                    err = MessageDialog("Error", f"Failed to create macro: {e}", self)
                    err.exec()

    def edit_macro(self, filename):
        path = os.path.join(self.macros_dir, filename)
        self.macroSelected.emit(path)

    def delete_macro(self, filename):
        path = os.path.join(self.macros_dir, filename)
        
        w = MessageDialog("Confirm Delete", f"Are you sure you want to delete '{filename}'?", self)
        
        if w.exec():
            try:
                os.remove(path)
                self.refresh_macros()
            except Exception as e:
                err = MessageDialog("Error", f"Failed to delete macro: {e}", self)
                err.exec()
    
    def duplicate_macro(self, filename):
        path = os.path.join(self.macros_dir, filename)
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                
            original_name = data.get("name", "Unknown")
            
            class InputDialog(MessageBoxBase):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.titleLabel = SubtitleLabel("Duplicate Macro", self)
                    self.inputField = LineEdit(self)
                    self.inputField.setPlaceholderText(f"Copy of {original_name}")
                    self.inputField.setClearButtonEnabled(True)
                    
                    self.viewLayout.addWidget(self.titleLabel)
                    self.viewLayout.addWidget(self.inputField)
                    
                    self.widget.setMinimumWidth(350)
            
            w = InputDialog(self)
            if w.exec():
                new_name = w.inputField.text().strip()
                if new_name:
                    new_filename = f"{new_name.replace(' ', '_')}.json"
                    new_path = os.path.join(self.macros_dir, new_filename)
                    
                    if os.path.exists(new_path):
                        err = MessageDialog("Error", "Macro with this name already exists!", self)
                        err.exec()
                        return
                    
                    # Update name and reset created_at
                    data["name"] = new_name
                    import time
                    data["created_at"] = time.time()
                    
                    with open(new_path, 'w') as f:
                        json.dump(data, f, indent=2)
                        
                    self.refresh_macros()
        except Exception as e:
             err = MessageDialog("Error", f"Failed to duplicate macro: {e}", self)
             err.exec()
    
    def start_macro(self, serial, filename):
        if serial in self.runners:
            return
            
        path = os.path.join(self.macros_dir, filename)
        try:
            macro = self._load_macro_from_file(path)
            
            runner = DashboardRunner(serial, macro, self.adb)
            runner.status_changed.connect(self.on_runner_status)
            runner.variable_changed.connect(self.on_runner_var)
            runner.finished.connect(self.on_runner_finished)
            
            self.runners[serial] = runner
            self.device_variables[serial] = macro.variables.copy()
            
            runner.start()
            
            if serial in self.device_cards:
                self.device_cards[serial].set_running_state(True)
                self.device_cards[serial].update_status("Running", filename)
                self.device_cards[serial].update_variables(self.device_variables[serial])
                
        except Exception as e:
            app_logger.error(f"Failed to start macro: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start macro: {e}")

    def _load_macro_from_file(self, path):
        with open(path, 'r') as f:
            data = json.load(f)
            
        macro = Macro(
            name=data.get("name", "Untitled"),
            target_resolution=Size(
                data["target_resolution"]["width"],
                data["target_resolution"]["height"]
            ),
            variables=data.get("variables", {}),
            created_at=data.get("created_at", 0)
        )
        
        self.load_actions_into_macro(macro, data.get("actions", []))
        return macro

    def toggle_pause_macro(self, serial):
        if serial in self.runners:
            self.runners[serial].pause()

    def stop_macro(self, serial):
        if serial in self.runners:
            self.runners[serial].stop()

    def on_runner_status(self, serial, status):
        if serial in self.device_cards:
            self.device_cards[serial].update_status(status, self.runners[serial].macro.name if serial in self.runners else None)
            
    def on_runner_var(self, serial, name, value):
        if serial not in self.device_variables:
            self.device_variables[serial] = {}
        self.device_variables[serial][name] = value
        
        if serial in self.device_cards:
            self.device_cards[serial].update_variables(self.device_variables[serial])

    def on_runner_finished(self, serial):
        if serial in self.runners:
            del self.runners[serial]
            
        if serial in self.device_cards:
            self.device_cards[serial].set_running_state(False)
            self.device_cards[serial].update_status("Idle")

    def load_actions_into_macro(self, macro, actions_data):
        for action_data in actions_data:
            action = ActionFactory.create_action(action_data)
            if action:
                macro.actions.append(action)

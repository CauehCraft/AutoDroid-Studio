import os
import time

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QListWidget, QListWidgetItem, QSizePolicy,
                             QSlider, QSpinBox, QSplitter, QTableWidget,
                             QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QLineEdit)
from qfluentwidgets import (BodyLabel, CardWidget, CheckBox, ComboBox,
                            DoubleSpinBox, LineEdit, MessageBoxBase, PrimaryPushButton,
                            PushButton, SpinBox, SubtitleLabel)

from ...core.action_factory import ActionFactory
from ...core.models import (Action, ClickAction, ClickImageAction, ConditionAction,
                            LoopAction, LoopEndAction, LoopStartAction, MultiAction,
                            MultiRegion, OCRAction, Point, PolygonRegion, Region,
                            SwipeAction, VarAction, WaitAction, ScreenshotAction)
from ...utils.logger import app_logger
from .action_widget import ActionItemWidget
from .logic_editor import LogicEditorDialog


class PropertiesEditor(QWidget):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.adb = editor.adb
        self.assets = editor.assets
        self.setupUI()

    def setupUI(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        self.formLayout = QFormLayout()
        self.layout.addLayout(self.formLayout)
        self.layout.addStretch()

    def clear_layout_content(self, layout):
        if layout is None:
            return
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_layout_content(child.layout())
                child.layout().deleteLater()

    # ---- UI Helper Methods ----
    
    def _create_spinbox(self, value: int, min_val: int = 0, max_val: int = 10000, 
                        on_change=None) -> SpinBox:
        """Create a configured SpinBox widget."""
        spin = SpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(value)
        if on_change:
            spin.valueChanged.connect(on_change)
        return spin

    def _create_double_spinbox(self, value: float, min_val: float = 0.0, max_val: float = 1.0,
                               step: float = 0.1, on_change=None) -> DoubleSpinBox:
        """Create a configured DoubleSpinBox widget."""
        spin = DoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setValue(value)
        if on_change:
            spin.valueChanged.connect(on_change)
        return spin

    def _add_duration_variance_fields(self, action, duration_attr: str, variance_attr: str,
                                       duration_label: str = "Duration (ms):", 
                                       variance_label: str = "Variance (ms):"):
        """Add duration and variance spinbox fields to the form layout."""
        duration_spin = self._create_spinbox(
            value=getattr(action, duration_attr),
            on_change=lambda val: setattr(action, duration_attr, val)
        )
        self.formLayout.addRow(duration_label, duration_spin)
        
        variance_spin = self._create_spinbox(
            value=getattr(action, variance_attr),
            on_change=lambda val: setattr(action, variance_attr, val)
        )
        self.formLayout.addRow(variance_label, variance_spin)

    def show_properties(self, action):
        self.clear_layout_content(self.formLayout)
        self.current_action_being_edited = action
        
        self._update_list_selection(action)
        self._add_common_properties(action)
        
        if isinstance(action, ClickAction):
            self._show_click_properties(action)
        elif isinstance(action, WaitAction):
            self._show_wait_properties(action)
        elif isinstance(action, ClickImageAction):
            self._show_click_image_properties(action)
        elif isinstance(action, OCRAction):
            self._show_ocr_properties(action)
        elif isinstance(action, VarAction):
            self._show_var_properties(action)
        elif isinstance(action, ConditionAction):
            self._show_condition_properties(action)
        elif isinstance(action, SwipeAction):
            self._show_swipe_properties(action)
        elif isinstance(action, LoopStartAction):
            self._show_loop_start_properties(action)
        elif isinstance(action, LoopEndAction):
            self._show_loop_end_properties(action)
        elif isinstance(action, MultiAction):
            self._show_multi_action_properties(action)
        elif isinstance(action, ScreenshotAction):
            self._show_screenshot_properties(action)
            
        self._add_debug_section()

    def _update_list_selection(self, action):
        for i in range(self.editor.actionList.count()):
            item = self.editor.actionList.item(i)
            item_action = item.data(Qt.ItemDataRole.UserRole)
            widget = self.editor.actionList.itemWidget(item)
            
            if item_action == action:
                widget.set_editing_state(True)
                item.setSelected(True)
            else:
                widget.set_editing_state(False)
                item.setSelected(False)

    def _add_common_properties(self, action):
        desc_edit = LineEdit()
        desc_edit.setText(action.description)
        desc_edit.textChanged.connect(lambda text: setattr(action, 'description', text))
        self.formLayout.addRow("Description:", desc_edit)
        
        logic_btn = PushButton("Advanced Logic / Variables")
        logic_btn.clicked.connect(lambda: self.open_logic_editor(action))
        self.formLayout.addRow(logic_btn)

    def _show_click_properties(self, action):
        self._add_duration_variance_fields(action, 'duration_ms', 'random_duration_variance',
                                            "Press Duration (ms):", "Variance (ms):")
        
        type_combo = ComboBox()
        type_combo.addItems(["Point", "Asset"])
        current_type = "Point"
        if isinstance(action.target, (Region, MultiRegion)) or hasattr(action.target, 'points'):
                current_type = "Asset"
        
        type_combo.setCurrentText(current_type)
        self.formLayout.addRow("Target Type:", type_combo)
        
        self.target_ui_container = QWidget()
        self.target_ui_layout = QFormLayout(self.target_ui_container)
        self.target_ui_layout.setContentsMargins(0,0,0,0)
        self.formLayout.addRow(self.target_ui_container)
        
        type_combo.currentTextChanged.connect(lambda t: self.update_target_ui(t, action))
        self.update_target_ui(current_type, action)

    def _show_wait_properties(self, action):
        type_combo = ComboBox()
        type_combo.addItems(["Time", "Image"])
        current_type = "Image" if action.wait_type == "image" else "Time"
        type_combo.setCurrentText(current_type)
        type_combo.currentTextChanged.connect(lambda t: self.update_wait_ui(t, action))
        self.formLayout.addRow("Wait Type:", type_combo)
        
        self.wait_ui_container = QWidget()
        self.wait_ui_layout = QFormLayout(self.wait_ui_container)
        self.wait_ui_layout.setContentsMargins(0,0,0,0)
        self.formLayout.addRow(self.wait_ui_container)
        
        self.update_wait_ui(current_type, action)

    def _show_click_image_properties(self, action):
        image_combo = ComboBox()
        if os.path.exists("assets/images"):
            images = [f for f in os.listdir("assets/images") if f.endswith(('.png', '.jpg'))]
            image_combo.addItems([os.path.splitext(f)[0] for f in images])
        
        image_combo.setCurrentText(action.image_name)
        image_combo.currentTextChanged.connect(lambda text: setattr(action, 'image_name', text))
        self.formLayout.addRow("Image Asset:", image_combo)
        
        threshold_spin = self._create_double_spinbox(
            value=action.threshold, min_val=0.1, max_val=1.0, step=0.1,
            on_change=lambda val: setattr(action, 'threshold', val)
        )
        self.formLayout.addRow("Match Threshold:", threshold_spin)
        
        refresh_img_btn = PushButton("Refresh Images")
        refresh_img_btn.clicked.connect(lambda: self.refresh_image_combo(image_combo))
        self.formLayout.addRow(refresh_img_btn)
        
        self._add_duration_variance_fields(action, 'duration_ms', 'random_duration_variance',
                                            "Press Duration (ms):", "Variance (ms):")

    def _show_screenshot_properties(self, action):
        filename_edit = LineEdit()
        filename_edit.setText(action.filename_pattern)
        filename_edit.textChanged.connect(lambda text: setattr(action, 'filename_pattern', text))
        self.formLayout.addRow("Filename Pattern:", filename_edit)
        self.formLayout.addRow(BodyLabel("Use {timestamp} for auto-naming", self))
        
        path_edit = LineEdit()
        path_edit.setText(action.save_path)
        path_edit.textChanged.connect(lambda text: setattr(action, 'save_path', text))
        self.formLayout.addRow("Save Path:", path_edit)

    def _show_ocr_properties(self, action):
        region_combo = ComboBox()
        regions = self.assets.load_regions()
        region_combo.addItems(list(regions.keys()))
        region_combo.setCurrentText(action.region_name)
        region_combo.currentTextChanged.connect(lambda text: setattr(action, 'region_name', text))
        self.formLayout.addRow("Region:", region_combo)
        
        var_edit = LineEdit()
        var_edit.setText(action.variable_name)
        var_edit.textChanged.connect(lambda text: setattr(action, 'variable_name', text))
        self.formLayout.addRow("Save to Variable:", var_edit)
        
        lang_edit = LineEdit()
        lang_edit.setText(action.language)
        lang_edit.textChanged.connect(lambda text: setattr(action, 'language', text))
        self.formLayout.addRow("Language:", lang_edit)
        
        # Preprocess Mode
        mode_combo = ComboBox()
        mode_combo.addItems(["default", "game", "white_text", "number", "raw", "adaptive", "clean"])
        mode_combo.setCurrentText(action.preprocess_mode)
        mode_combo.currentTextChanged.connect(lambda text: setattr(action, 'preprocess_mode', text))
        self.formLayout.addRow("OCR Mode:", mode_combo)
        
        # Text Type
        type_combo = ComboBox()
        type_combo.addItems(["text", "number"])
        type_combo.setCurrentText(action.text_type)
        type_combo.currentTextChanged.connect(lambda text: setattr(action, 'text_type', text))
        self.formLayout.addRow("Text Type:", type_combo)

    def _show_var_properties(self, action):
        name_edit = QLineEdit(action.var_name)
        name_edit.textChanged.connect(lambda text: setattr(action, 'var_name', text))
        self.formLayout.addRow("Variable Name:", name_edit)
        
        op_combo = ComboBox()
        op_combo.addItems(["set", "increment"])
        op_combo.setCurrentText(action.operation)
        op_combo.currentTextChanged.connect(lambda text: setattr(action, 'operation', text))
        self.formLayout.addRow("Operation:", op_combo)
        
        val_edit = QLineEdit(str(action.value))
        val_edit.textChanged.connect(lambda text: setattr(action, 'value', text))
        self.formLayout.addRow("Value:", val_edit)

    def _show_condition_properties(self, action):
        type_combo = ComboBox()
        type_combo.addItems(["variable", "image_found"])
        type_combo.setCurrentText(action.condition_type)
        type_combo.currentTextChanged.connect(lambda text: setattr(action, 'condition_type', text))
        self.formLayout.addRow("Condition Type:", type_combo)
        
        target_edit = QLineEdit(action.target)
        target_edit.textChanged.connect(lambda text: setattr(action, 'target', text))
        self.formLayout.addRow("Target (Var/Image):", target_edit)
        
        op_combo = ComboBox()
        op_combo.addItems(["==", "!=", ">", "<", "exists"])
        op_combo.setCurrentText(action.operator)
        op_combo.currentTextChanged.connect(lambda text: setattr(action, 'operator', text))
        self.formLayout.addRow("Operator:", op_combo)
        
        val_edit = LineEdit()
        val_edit.setText(str(action.value))
        val_edit.textChanged.connect(lambda text: setattr(action, 'value', text))
        self.formLayout.addRow("Value:", val_edit)

    def _show_swipe_properties(self, action):
        self.formLayout.addRow(BodyLabel("Start Position:", self))
        start_type_combo = ComboBox()
        start_type_combo.addItems(["Point", "Asset"])
        current_start_type = "Asset" if isinstance(action.start_point, (Region, PolygonRegion, MultiRegion)) else "Point"
        start_type_combo.setCurrentText(current_start_type)
        self.formLayout.addRow("Type:", start_type_combo)
        
        self.start_ui_container = QWidget()
        self.start_ui_layout = QFormLayout(self.start_ui_container)
        self.start_ui_layout.setContentsMargins(0,0,0,0)
        self.formLayout.addRow(self.start_ui_container)
        
        start_type_combo.currentTextChanged.connect(lambda t: self.update_swipe_target_ui(t, action, "start"))
        self.update_swipe_target_ui(current_start_type, action, "start")

        self.formLayout.addRow(BodyLabel("End Position:", self))
        end_type_combo = ComboBox()
        end_type_combo.addItems(["Point", "Asset"])
        current_end_type = "Asset" if isinstance(action.end_point, (Region, PolygonRegion, MultiRegion)) else "Point"
        end_type_combo.setCurrentText(current_end_type)
        self.formLayout.addRow("Type:", end_type_combo)
        
        self.end_ui_container = QWidget()
        self.end_ui_layout = QFormLayout(self.end_ui_container)
        self.end_ui_layout.setContentsMargins(0,0,0,0)
        self.formLayout.addRow(self.end_ui_container)
        
        end_type_combo.currentTextChanged.connect(lambda t: self.update_swipe_target_ui(t, action, "end"))
        self.update_swipe_target_ui(current_end_type, action, "end")
        
        dur_spin = SpinBox()
        dur_spin.setRange(0, 10000)
        dur_spin.setValue(action.duration_ms)
        dur_spin.valueChanged.connect(lambda val: setattr(action, 'duration_ms', val))
        self.formLayout.addRow("Swipe Duration (ms):", dur_spin)
        
        dur_var_spin = SpinBox()
        dur_var_spin.setRange(0, 10000)
        dur_var_spin.setValue(action.duration_variance_ms)
        dur_var_spin.valueChanged.connect(lambda val: setattr(action, 'duration_variance_ms', val))
        self.formLayout.addRow("Duration Variance (ms):", dur_var_spin)
        
        hold_start_spin = SpinBox()
        hold_start_spin.setRange(0, 10000)
        hold_start_spin.setValue(action.hold_start_ms)
        hold_start_spin.valueChanged.connect(lambda val: setattr(action, 'hold_start_ms', val))
        self.formLayout.addRow("Hold at Start (ms):", hold_start_spin)
        
        hold_start_var_spin = SpinBox()
        hold_start_var_spin.setRange(0, 10000)
        hold_start_var_spin.setValue(action.hold_start_variance_ms)
        hold_start_var_spin.valueChanged.connect(lambda val: setattr(action, 'hold_start_variance_ms', val))
        self.formLayout.addRow("Hold Start Variance (ms):", hold_start_var_spin)
        
        hold_end_spin = SpinBox()
        hold_end_spin.setRange(0, 10000)
        hold_end_spin.setValue(action.hold_end_ms)
        hold_end_spin.valueChanged.connect(lambda val: setattr(action, 'hold_end_ms', val))
        self.formLayout.addRow("Hold at End (ms):", hold_end_spin)
        
        hold_end_var_spin = SpinBox()
        hold_end_var_spin.setRange(0, 10000)
        hold_end_var_spin.setValue(action.hold_end_variance_ms)
        hold_end_var_spin.valueChanged.connect(lambda val: setattr(action, 'hold_end_variance_ms', val))
        self.formLayout.addRow("Hold End Variance (ms):", hold_end_var_spin)

    def _show_loop_start_properties(self, action):
        type_combo = ComboBox()
        type_combo.addItems(["count", "infinite", "condition"])
        type_combo.setCurrentText(action.loop_type)
        type_combo.currentTextChanged.connect(lambda t: self.update_loop_ui(t, action))
        self.formLayout.addRow("Loop Type:", type_combo)
        
        self.loop_ui_container = QWidget()
        self.loop_ui_layout = QFormLayout(self.loop_ui_container)
        self.loop_ui_layout.setContentsMargins(0,0,0,0)
        self.formLayout.addRow(self.loop_ui_container)
        
        self.update_loop_ui(action.loop_type, action)

    def _show_loop_end_properties(self, action):
        self.formLayout.addRow(BodyLabel(f"Linked to Loop ID: {action.linked_loop_id}", self))
        self.formLayout.addRow(BodyLabel("This action marks the end of the loop.", self))

    def _show_multi_action_properties(self, action):
        header_layout = QHBoxLayout()
        header_layout.addWidget(BodyLabel("🔄 Simultaneous Actions", self))
        header_layout.addStretch()
        
        strict_cb = CheckBox("Strict Mode")
        strict_cb.setToolTip("Abort if any action fails")
        strict_cb.setChecked(action.strict_mode)
        strict_cb.stateChanged.connect(lambda state: setattr(action, 'strict_mode', state == Qt.CheckState.Checked.value))
        header_layout.addWidget(strict_cb)
        
        self.formLayout.addRow(header_layout)
        
        multi_container = QWidget()
        multi_layout = QVBoxLayout(multi_container)
        multi_layout.setContentsMargins(0, 0, 0, 0)
        
        self.multiaction_list = QListWidget()
        self.multiaction_list.setMaximumHeight(200)
        for idx, sub_action in enumerate(action.actions):
            item = QListWidgetItem(self.multiaction_list)
            item.setSizeHint(QSize(0, 50))
            
            widget = ActionItemWidget(sub_action)
            widget.edit_callback = lambda a, r=idx: self.show_subaction_properties(action, r)
            widget.test_callback = self.editor.test_single_action
            widget.stop_callback = self.editor.stop_action_test
            widget.duplicate_callback = lambda a: self.duplicate_action_in_multi(action, a)
            widget.delete_callback = lambda a: self.remove_action_from_multi(action, a)
            
            self.multiaction_list.setItemWidget(item, widget)

        multi_layout.addWidget(self.multiaction_list)
        
        add_layout = QHBoxLayout()
        add_layout.setContentsMargins(0, 5, 0, 0)
        
        action_type_combo = ComboBox()
        action_type_combo.addItems([
            "Click", 
            "Wait", 
            "Click Image", 
            "Swipe",
            "Variable"
        ])
        add_layout.addWidget(action_type_combo)
        
        add_btn = PrimaryPushButton("Add", self)
        add_btn.setFixedWidth(60)
        add_layout.addWidget(add_btn)
        
        multi_layout.addLayout(add_layout)
        
        self.formLayout.addRow(multi_container)
        
        add_btn.clicked.connect(lambda: self.add_action_to_multi(action, action_type_combo.currentText()))
        
        separator = BodyLabel("─" * 50)
        separator.setStyleSheet("color: #444;")
        self.formLayout.addRow(separator)

    def _add_debug_section(self):
        self.formLayout.addRow(BodyLabel("─" * 50))
        
        debug_header_layout = QHBoxLayout()
        debug_label = BodyLabel("📝 Action Debugger")
        debug_toggle_btn = PushButton("Show/Hide")
        debug_toggle_btn.setCheckable(True)
        debug_toggle_btn.setChecked(True)
        debug_header_layout.addWidget(debug_label)
        debug_header_layout.addWidget(debug_toggle_btn)
        self.formLayout.addRow(debug_header_layout)
        
        self.action_log_viewer = QTextEdit()
        self.action_log_viewer.setReadOnly(True)
        self.action_log_viewer.setStyleSheet("font-family: Consolas; font-size: 9pt; color: #ccc; background-color: #1e1e1e; border: 1px solid #333;")
        self.action_log_viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.action_log_viewer.setMinimumHeight(150)
        self.formLayout.addRow(self.action_log_viewer)
        
        debug_toggle_btn.clicked.connect(lambda checked: self.action_log_viewer.setVisible(checked))
        
        try:
            app_logger.log_signal.disconnect(self.update_action_log)
        except: pass
        app_logger.log_signal.connect(self.update_action_log)

    def update_action_log(self, msg):
        if hasattr(self, 'action_log_viewer') and self.action_log_viewer:
            self.action_log_viewer.append(msg)
            self.action_log_viewer.verticalScrollBar().setValue(
                self.action_log_viewer.verticalScrollBar().maximum()
            )

    def open_logic_editor(self, action):
        dialog = LogicEditorDialog(action, self)
        dialog.exec()

    def show_subaction_properties(self, multi_action, row):
        if row < 0 or row >= len(multi_action.actions):
            while self.formLayout.count():
                child = self.formLayout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            return
        
        sub_action = multi_action.actions[row]
        
        self._editing_subaction = True
        self._parent_multi_action = multi_action
        self._current_subaction = sub_action
        
        self.show_properties(sub_action)
        
        back_btn = PushButton("⬅ Back to Multi-Action")
        back_btn.clicked.connect(lambda: self.back_to_multi_action())
        self.formLayout.addRow(back_btn)

    def back_to_multi_action(self):
        if hasattr(self, '_parent_multi_action'):
            self._editing_subaction = False
            self.show_properties(self._parent_multi_action)
            delattr(self, '_parent_multi_action')

    def add_action_to_multi(self, multi_action, action_type):
        new_action = None
        action_id = str(time.time())
        
        if action_type == "Click":
            new_action = ClickAction(
                id=action_id, 
                type="click", 
                target=Point(100, 100),
                duration_ms=100,
                advanced_logic=[]
            )
        elif action_type == "Wait":
            new_action = WaitAction(
                id=action_id,
                type="wait",
                duration_ms=1000,
                advanced_logic=[]
            )
        elif action_type == "Click Image":
            new_action = ClickImageAction(
                id=action_id,
                type="click_image",
                image_name="",
                threshold=0.8,
                advanced_logic=[]
            )
        elif action_type == "Swipe":
            new_action = SwipeAction(
                id=action_id,
                type="swipe",
                start_point=Point(100, 100),
                end_point=Point(500, 500),
                duration_ms=300,
                advanced_logic=[]
            )
        elif action_type == "Variable":
            new_action = VarAction(
                id=action_id,
                type="variable",
                var_name="new_var",
                operation="set",
                value="0",
                advanced_logic=[]
            )
        
        if new_action:
            multi_action.actions.append(new_action)
            self.show_properties(multi_action)

    def duplicate_action_in_multi(self, multi_action, sub_action):
        if not sub_action or sub_action not in multi_action.actions:
            return

        try:
            idx = multi_action.actions.index(sub_action)
            data = sub_action.to_dict()
            
            new_id = str(time.time())
            data['id'] = new_id
            
            new_action = ActionFactory.create_action(data)
            
            if new_action:
                multi_action.actions.insert(idx + 1, new_action)
                self.show_properties(multi_action)
                app_logger.info(f"Sub-action {sub_action.id} duplicated as {new_action.id} in MultiAction")
                
        except Exception as e:
            app_logger.error(f"Failed to duplicate sub-action: {e}")
            MessageBoxBase(self, "Error", f"Failed to duplicate sub-action: {e}").exec()

    def remove_action_from_multi(self, multi_action, sub_action):
        if sub_action in multi_action.actions:
            multi_action.actions.remove(sub_action)
            self.show_properties(multi_action)
        else:
            MessageBoxBase(self, "Error", "Could not find action to remove.").exec()

    def update_target_ui(self, type, action):
        while self.target_ui_layout.count():
            child = self.target_ui_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        if type == "Point":
            if not isinstance(action.target, Point):
                action.target = Point(100, 100)
            
            x_spin = SpinBox()
            x_spin.setRange(0, 10000)
            y_spin = SpinBox()
            y_spin.setRange(0, 10000)
            
            x_spin.setValue(action.target.x)
            y_spin.setValue(action.target.y)
            
            x_spin.valueChanged.connect(lambda val: self.update_point(action, x=val))
            y_spin.valueChanged.connect(lambda val: self.update_point(action, y=val))
            
            self.target_ui_layout.addRow("X:", x_spin)
            self.target_ui_layout.addRow("Y:", y_spin)
            
        elif type == "Asset":
            self._setup_asset_target_ui(action, self.target_ui_layout, "target")

    def _setup_asset_target_ui(self, action, layout, attr_name, point_type=None):
        asset_combo = ComboBox()
        regions = self.assets.load_regions()
        region_names = list(regions.keys())
        
        if not region_names:
            layout.addRow(BodyLabel("No regions found. Create one in Inspector."))
            return
        
        asset_combo.addItems(region_names)
        
        # Find current match
        current_selection = None
        target_point = getattr(action, attr_name) if not point_type else (action.start_point if point_type == "start" else action.end_point)

        if isinstance(target_point, (Region, PolygonRegion, MultiRegion)):
             for name in region_names:
                 data = regions[name]
                 r_data = data["region"] if isinstance(data, dict) else data
                 
                 if r_data == target_point:
                     current_selection = name
                     break
                 if isinstance(target_point, MultiRegion) and isinstance(r_data, MultiRegion):
                      if len(target_point.regions) == len(r_data.regions):
                           current_selection = name
                           break
        
        asset_combo.blockSignals(True)
        if current_selection:
             asset_combo.setCurrentText(current_selection)
        else:
             asset_combo.setCurrentText(region_names[0]) # Default to first
             if target_point is None:
                  if point_type:
                       self.set_swipe_target_from_asset(action, region_names[0], point_type)
                  else:
                       self.set_action_target_from_asset(action, region_names[0])
        asset_combo.blockSignals(False)
        
        if point_type:
             asset_combo.currentTextChanged.connect(lambda name: self.set_swipe_target_from_asset(action, name, point_type))
        else:
             asset_combo.currentTextChanged.connect(lambda name: self.set_action_target_from_asset(action, name))
             
        layout.addRow("Select Region:", asset_combo)

    def update_point(self, action, x=None, y=None):
         if isinstance(action.target, Point):
              if x is not None: action.target.x = x
              if y is not None: action.target.y = y

    def update_wait_ui(self, type_text, action):
        while self.wait_ui_layout.count():
            child = self.wait_ui_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        action.wait_type = "image" if type_text == "Image" else "time"
        
        if action.wait_type == "time":
            duration_spin = SpinBox()
            duration_spin.setRange(0, 3600000)
            duration_spin.setValue(action.duration_ms)
            duration_spin.valueChanged.connect(lambda val: setattr(action, 'duration_ms', val))
            self.wait_ui_layout.addRow("Duration (ms):", duration_spin)
            
            variance_spin = SpinBox()
            variance_spin.setRange(0, 10000)
            variance_spin.setValue(action.random_variance_ms)
            variance_spin.valueChanged.connect(lambda val: setattr(action, 'random_variance_ms', val))
            self.wait_ui_layout.addRow("Variance (ms):", variance_spin)
            
        elif action.wait_type == "image":
            image_combo = ComboBox()
            if os.path.exists("assets/images"):
                images = [f for f in os.listdir("assets/images") if f.endswith(('.png', '.jpg'))]
                image_combo.addItems([os.path.splitext(f)[0] for f in images])
            
            image_combo.setCurrentText(action.image_name if action.image_name else "")
            image_combo.currentTextChanged.connect(lambda text: setattr(action, 'image_name', text))
            self.wait_ui_layout.addRow("Image Asset:", image_combo)
            
            interval_spin = SpinBox()
            interval_spin.setRange(100, 60000)
            interval_spin.setValue(action.check_interval_ms)
            interval_spin.valueChanged.connect(lambda val: setattr(action, 'check_interval_ms', val))
            self.wait_ui_layout.addRow("Check Interval (ms):", interval_spin)
            
            timeout_spin = SpinBox()
            timeout_spin.setRange(0, 3600000)
            timeout_spin.setValue(action.duration_ms)
            timeout_spin.setToolTip("0 for infinite wait")
            timeout_spin.valueChanged.connect(lambda val: setattr(action, 'duration_ms', val))
            self.wait_ui_layout.addRow("Timeout (ms):", timeout_spin)

    def update_loop_ui(self, loop_type, action):
        while self.loop_ui_layout.count():
            child = self.loop_ui_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        action.loop_type = loop_type
        
        if loop_type == "count":
            iter_spin = SpinBox()
            iter_spin.setRange(1, 100000)
            iter_spin.setValue(action.iterations)
            iter_spin.valueChanged.connect(lambda val: setattr(action, 'iterations', val))
            self.loop_ui_layout.addRow("Iterations:", iter_spin)
        elif loop_type == "condition":
            var_edit = LineEdit()
            var_edit.setText(action.condition_var)
            var_edit.setPlaceholderText("Variable Name")
            var_edit.textChanged.connect(lambda text: setattr(action, 'condition_var', text))
            self.loop_ui_layout.addRow("Variable:", var_edit)
            
            op_combo = ComboBox()
            op_combo.addItems(["==", "!=", ">", "<"])
            op_combo.setCurrentText(action.condition_op)
            op_combo.currentTextChanged.connect(lambda text: setattr(action, 'condition_op', text))
            self.loop_ui_layout.addRow("Operator:", op_combo)
            
            val_edit = LineEdit()
            val_edit.setText(action.condition_value)
            val_edit.setPlaceholderText("Value")
            val_edit.textChanged.connect(lambda text: setattr(action, 'condition_value', text))
            self.loop_ui_layout.addRow("Value:", val_edit)

    def update_swipe_target_ui(self, type, action, point_type):
        container = self.start_ui_container if point_type == "start" else self.end_ui_container
        layout = self.start_ui_layout if point_type == "start" else self.end_ui_layout
        
        while layout.count():
            child = layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        target_point = action.start_point if point_type == "start" else action.end_point
        
        if type == "Point":
            if not isinstance(target_point, Point):
                target_point = Point(100, 100)
                if point_type == "start": action.start_point = target_point
                else: action.end_point = target_point
            
            x_spin = SpinBox()
            x_spin.setRange(0, 10000)
            y_spin = SpinBox()
            y_spin.setRange(0, 10000)
            
            x_spin.setValue(target_point.x)
            y_spin.setValue(target_point.y)
            
            def update_coord(val, axis):
                pt = action.start_point if point_type == "start" else action.end_point
                if isinstance(pt, Point):
                    if axis == 'x': pt.x = val
                    else: pt.y = val
            
            x_spin.valueChanged.connect(lambda val: update_coord(val, 'x'))
            y_spin.valueChanged.connect(lambda val: update_coord(val, 'y'))
            
            layout.addRow("X:", x_spin)
            layout.addRow("Y:", y_spin)
            
        elif type == "Asset":
            self._setup_asset_target_ui(action, layout, "start" if point_type == "start" else "end", point_type)

    def set_action_target_from_asset(self, action, asset_name):
        regions = self.assets.load_regions()
        if asset_name in regions:
            data = regions[asset_name]
            region = data["region"] if isinstance(data, dict) else data
            if isinstance(region, Region):
                action.target = Region(region.x, region.y, region.width, region.height)
            elif isinstance(region, PolygonRegion):
                action.target = PolygonRegion([Point(p.x, p.y) for p in region.points])
            elif isinstance(region, MultiRegion):
                new_regions = []
                for r in region.regions:
                    if isinstance(r, Region):
                        new_regions.append(Region(r.x, r.y, r.width, r.height))
                    elif isinstance(r, PolygonRegion):
                        new_regions.append(PolygonRegion([Point(p.x, p.y) for p in r.points]))
                action.target = MultiRegion(new_regions)
    
    def set_swipe_target_from_asset(self, action, asset_name, point_type):
         regions = self.assets.load_regions()
         if asset_name in regions:
            data = regions[asset_name]
            region = data["region"] if isinstance(data, dict) else data
            
            # Create a copy/new instance for the action
            new_target = None
            if isinstance(region, Region):
                new_target = Region(region.x, region.y, region.width, region.height)
            elif isinstance(region, PolygonRegion):
                new_target = PolygonRegion([Point(p.x, p.y) for p in region.points])
            elif isinstance(region, MultiRegion):
                # Copy multi region logic
                new_regions = []
                for r in region.regions:
                    if isinstance(r, Region):
                        new_regions.append(Region(r.x, r.y, r.width, r.height))
                new_target = MultiRegion(new_regions)
            
            if new_target:
                if point_type == "start":
                    action.start_point = new_target
                else:
                    action.end_point = new_target
    
    def refresh_image_combo(self, combo):
        combo.clear()
        if os.path.exists("assets/images"):
            images = [f for f in os.listdir("assets/images") if f.endswith(('.png', '.jpg'))]
            combo.addItems([os.path.splitext(f)[0] for f in images])

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QVBoxLayout,
                             QWidget)
from qfluentwidgets import (BodyLabel, CardWidget, ComboBox, PrimaryPushButton,
                            PushButton, SubtitleLabel, ToggleButton)

from ..core.adb_manager import AdbManager
from ..core.asset_manager import AssetManager
from ..core.models import MultiRegion, Point, PolygonRegion, Region
from ..utils.logger import app_logger
from .widgets.screen_viewer import ScreenViewer


class ScreenInspector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("inspectorInterface")
        self.adb = AdbManager()
        self.assets = AssetManager()
        self.current_selection = None
        self.setupUI()
        self.setupConnections()

    def setupUI(self):
        self.hBoxLayout = QHBoxLayout(self)
        
        self._setup_control_panel()
        self._setup_viewer_panel()

    def _setup_control_panel(self):
        # Left Panel: Controls
        self.controlPanel = CardWidget(self)
        self.controlPanel.setFixedWidth(300)
        self.controlLayout = QVBoxLayout(self.controlPanel)
        
        self.controlLayout.addWidget(SubtitleLabel('Inspector Controls', self.controlPanel))
        
        # Device Selection
        self.deviceCombo = ComboBox(self.controlPanel)
        self.deviceCombo.setMinimumWidth(200)
        self.refreshBtn = PrimaryPushButton('Refresh Devices', self.controlPanel)
        self.refreshBtn.setMinimumWidth(200)
        self.controlLayout.addWidget(BodyLabel('Device:', self.controlPanel))
        self.controlLayout.addWidget(self.deviceCombo)
        self.controlLayout.addWidget(self.refreshBtn)
        
        # Capture
        self.captureBtn = PrimaryPushButton('Capture Screen', self.controlPanel)
        self.captureBtn.setMinimumWidth(200)
        self.controlLayout.addWidget(self.captureBtn)
        
        # Mode Selection
        self.modeLabel = BodyLabel('Selection Mode:', self.controlPanel)
        self.modeCombo = ComboBox(self.controlPanel)
        self.modeCombo.addItems(['Rectangle', 'Polygon', 'Multi-Region', 'Image Template'])
        self.controlLayout.addWidget(self.modeLabel)
        self.controlLayout.addWidget(self.modeCombo)
        
        self._setup_multi_region_controls()
        
        # Selection Info
        self.infoLabel = BodyLabel('Selection: None', self.controlPanel)
        self.controlLayout.addWidget(self.infoLabel)
        
        self.saveBtn = PushButton('Save Region', self.controlPanel)
        self.saveBtn.setEnabled(False)
        self.controlLayout.addWidget(self.saveBtn)
        
        self.controlLayout.addStretch(1)
        
        self.hBoxLayout.addWidget(self.controlPanel)

    def _setup_multi_region_controls(self):
        # Multi-Region Controls (Hidden by default)
        self.multiControls = QWidget()
        self.multiLayout = QVBoxLayout(self.multiControls)
        self.multiLayout.setContentsMargins(0, 0, 0, 0)
        
        self.multiSubMode = ComboBox()
        self.multiSubMode.addItems(['Rectangle', 'Polygon'])
        self.multiSubMode.currentTextChanged.connect(self.change_multi_submode)
        self.multiLayout.addWidget(BodyLabel("Sub Mode:"))
        self.multiLayout.addWidget(self.multiSubMode)
        
        self.clearMultiBtn = PushButton("Clear Selections")
        self.clearMultiBtn.clicked.connect(self.clear_multi_selections)
        self.multiLayout.addWidget(self.clearMultiBtn)
        
        self.controlLayout.addWidget(self.multiControls)
        self.multiControls.hide()

    def _setup_viewer_panel(self):
        # Right Panel: Viewer
        self.viewerContainer = QWidget(self)
        self.viewerLayout = QVBoxLayout(self.viewerContainer)
        self.viewer = ScreenViewer(self.viewerContainer)
        self.viewerLayout.addWidget(self.viewer)
        
        self.hBoxLayout.addWidget(self.viewerContainer, 1)

    def setupConnections(self):
        self.refreshBtn.clicked.connect(self.refresh_devices)
        self.captureBtn.clicked.connect(self.capture_screen)
        self.modeCombo.currentTextChanged.connect(self.change_mode)
        self.viewer.regionSelected.connect(self.on_region_selected)
        self.viewer.polygonSelected.connect(self.on_polygon_selected)
        self.saveBtn.clicked.connect(self.save_region)

    def save_region(self):
        if not self.current_selection and self.modeCombo.currentText() != "Multi-Region":
            return
        
        if self.modeCombo.currentText() == "Multi-Region" and not self.viewer.multi_regions:
            return
            
        name, ok = QInputDialog.getText(self, 'Save Region', 'Enter region name:')
        if ok and name:
            source_resolution = self._get_current_device_resolution()
            
            if self.modeCombo.currentText() == "Image Template":
                self._save_image_template(name)
            elif self.modeCombo.currentText() == "Multi-Region":
                self._save_multi_region(name, source_resolution)
            else:
                self.assets.save_region(name, self.current_selection, source_resolution)
                app_logger.info(f"Region '{name}' saved with resolution {source_resolution}.")

    def _get_current_device_resolution(self):
        serial = self.deviceCombo.currentText()
        if serial:
            device = self.adb.connect_device(serial)
            if device:
                res = self.adb.get_screen_resolution(device)
                return {"width": res.width, "height": res.height}
        return None

    def _save_image_template(self, name):
        # Crop and save image
        if hasattr(self, 'current_image_crop') and self.current_image_crop is not None:
            self.assets.save_image_asset(name, self.current_image_crop)
            app_logger.info(f"Image asset '{name}' saved.")
        else:
            app_logger.error("No image data to save.")

    def _save_multi_region(self, name, source_resolution):
        sub_regions = []
        for r_type, data in self.viewer.multi_regions:
            if r_type == "rect":
                sub_regions.append(Region(data.x(), data.y(), data.width(), data.height()))
            elif r_type == "poly":
                points = [Point(p.x(), p.y()) for p in data]
                sub_regions.append(PolygonRegion(points))
        
        multi_region = MultiRegion(sub_regions)
        self.assets.save_region(name, multi_region, source_resolution)
        app_logger.info(f"Multi-Region '{name}' saved with {len(sub_regions)} sub-regions.")

    def refresh_devices(self):
        devices = self.adb.get_devices()
        self.deviceCombo.clear()
        for device in devices:
            self.deviceCombo.addItem(f"{device.serial}")

    def capture_screen(self):
        serial = self.deviceCombo.currentText()
        if not serial:
            return
            
        device = self.adb.connect_device(serial)
        if device:
            img = self.adb.take_screenshot(device)
            if img is not None:
                self.viewer.set_image(img)
                app_logger.info(f"Screenshot captured from {serial}")

    def change_mode(self, mode):
        # Map display names to internal mode names
        mode_mapping = {
            "Rectangle": "rectangle",
            "Polygon": "polygon",
            "Image Template": "image_template",
            "Multi-Region": "multi"
        }
        internal_mode = mode_mapping.get(mode, mode.lower())
        self.viewer.mode = internal_mode
        self.infoLabel.setText(f"Mode: {mode}")
        
        if internal_mode == "multi":
            self.multiControls.show()
            self.viewer.multi_regions = [] # Clear on mode switch
            self.viewer.update()
            self.saveBtn.setEnabled(False)
        else:
            self.multiControls.hide()

    def change_multi_submode(self, mode):
        self.viewer.current_multi_mode = mode.lower()

    def clear_multi_selections(self):
        self.viewer.multi_regions = []
        self.viewer.update()
        self.infoLabel.setText("Multi-Region: Cleared")
        self.saveBtn.setEnabled(False)

    def on_region_selected(self, rect):
        
        if self.viewer.mode == "multi":
            count = len(self.viewer.multi_regions)
            self.infoLabel.setText(f"Multi-Region: {count} selections")
            self.saveBtn.setEnabled(True)
        else:
            self.infoLabel.setText(f"Rect: x={rect.x()}, y={rect.y()}, w={rect.width()}, h={rect.height()}")
            self.current_selection = Region(rect.x(), rect.y(), rect.width(), rect.height())
            
            # Store crop for image saving
            if self.viewer.image is not None:
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                # Ensure bounds
                img_h, img_w = self.viewer.image.shape[:2]
                x = max(0, min(x, img_w))
                y = max(0, min(y, img_h))
                w = max(0, min(w, img_w - x))
                h = max(0, min(h, img_h - y))
                if w > 0 and h > 0:
                    self.current_image_crop = self.viewer.image[y:y+h, x:x+w].copy()
            
            self.saveBtn.setEnabled(True)

    def on_polygon_selected(self, points):
        
        if self.viewer.mode == "multi":
            count = len(self.viewer.multi_regions)
            self.infoLabel.setText(f"Multi-Region: {count} selections")
            self.saveBtn.setEnabled(True)
        else:
            pts_str = ", ".join([f"({p.x()}, {p.y()})" for p in points])
            self.infoLabel.setText(f"Polygon: {len(points)} points")
            
            model_points = [Point(p.x(), p.y()) for p in points]
            self.current_selection = PolygonRegion(model_points)
            self.saveBtn.setEnabled(True)
            app_logger.info(f"Polygon selected: {pts_str}")

import os

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFileDialog, QFormLayout, QHBoxLayout,
                             QHeaderView, QListWidget, QListWidgetItem,
                             QMessageBox, QSlider, QSplitter, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CardWidget, CheckBox, ComboBox,
                            LineEdit, PrimaryPushButton, PushButton, SpinBox,
                            SubtitleLabel)

from ..core.adb_manager import AdbManager
from ..core.asset_manager import AssetManager
from ..core.models import MultiRegion, Point, PolygonRegion, Region
from ..core.vision import VisionEngine
from ..utils.logger import app_logger
from .dialogs.ocr_result_dialog import OCRResultDialog
from .styles import COMMON_STYLE
from .widgets.region_overlay import RegionOverlay


class RegionManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("regionManagerInterface")
        self.adb = AdbManager()
        self.assets = AssetManager()
        self.vision = VisionEngine()
        self.current_region_name = None
        self.setupUI()
        self.setupConnections()
        self.refresh_regions()
        self.setStyleSheet(COMMON_STYLE)
        
    def setupUI(self):
        self.hBoxLayout = QHBoxLayout(self)
        
        # Splitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.hBoxLayout.addWidget(self.splitter)
        
        # Left Panel: Region List
        self.listPanel = CardWidget(self)
        self.listLayout = QVBoxLayout(self.listPanel)
        
        self.listLayout.addWidget(SubtitleLabel('Regions & Images', self.listPanel))
        
        # Region List
        self.regionList = QListWidget(self.listPanel)
        self.listLayout.addWidget(self.regionList)
        
        # Buttons
        btnLayout = QHBoxLayout()
        self.refreshBtn = PushButton('Refresh', self.listPanel)
        self.deleteBtn = PushButton('Delete', self.listPanel)
        btnLayout.addWidget(self.refreshBtn)
        btnLayout.addWidget(self.deleteBtn)
        self.listLayout.addLayout(btnLayout)
        
        self.splitter.addWidget(self.listPanel)
        
        # Center Panel: Visual Preview
        self.previewPanel = CardWidget(self)
        self.previewLayout = QVBoxLayout(self.previewPanel)
        
        self.previewLayout.addWidget(SubtitleLabel('Visual Preview', self.previewPanel))
        
        # Device and capture controls
        controlLayout = QHBoxLayout()
        self.deviceCombo = ComboBox(self.previewPanel)
        self.deviceCombo.setMinimumWidth(150)
        self.refreshDevicesBtn = PushButton('Refresh Devices', self.previewPanel)
        self.refreshDevicesBtn.setMinimumWidth(120)
        self.captureBtn = PrimaryPushButton('Capture Screenshot', self.previewPanel)
        self.captureBtn.setMinimumWidth(150)
        self.loadImageBtn = PushButton('Load Image', self.previewPanel)
        self.loadImageBtn.setMinimumWidth(100)
        
        controlLayout.addWidget(BodyLabel('Device:', self.previewPanel))
        controlLayout.addWidget(self.deviceCombo)
        controlLayout.addWidget(self.refreshDevicesBtn)
        controlLayout.addWidget(self.captureBtn)
        controlLayout.addWidget(self.loadImageBtn)
        
        self.hideNonSelectedChk = CheckBox("Hide Unselected", self.previewPanel)
        self.hideNonSelectedChk.stateChanged.connect(self.on_hide_non_selected_changed)
        controlLayout.addWidget(self.hideNonSelectedChk)
        
        self.previewLayout.addLayout(controlLayout)
        
        # Overlay viewer
        self.overlay = RegionOverlay(self.previewPanel)
        self.previewLayout.addWidget(self.overlay, 1)
        
        self.splitter.addWidget(self.previewPanel)
        
        # Right Panel: Properties
        self.propPanel = CardWidget(self)
        self.propLayout = QVBoxLayout(self.propPanel)
        
        self.propLayout.addWidget(SubtitleLabel('Properties', self.propPanel))
        
        # Form for editing
        self.formLayout = QFormLayout()
        self.propLayout.addLayout(self.formLayout)
        
        # Test button
        self.testBtn = PrimaryPushButton('Test on Device', self.propPanel)
        self.testBtn.setEnabled(False)
        self.propLayout.addWidget(self.testBtn)
        
        self.testOCRBtn = PushButton('Test OCR', self.propPanel)
        self.testOCRBtn.setEnabled(False)
        self.propLayout.addWidget(self.testOCRBtn)
        
        # Save button
        self.saveBtn = PrimaryPushButton('Save Changes', self.propPanel)
        self.saveBtn.setEnabled(False)
        self.propLayout.addWidget(self.saveBtn)
        
        self.propLayout.addStretch(1)
        
        self.splitter.addWidget(self.propPanel)
        
        # Set initial sizes
        self.splitter.setSizes([250, 600, 350])

    def setupConnections(self):
        self.refreshBtn.clicked.connect(self.refresh_regions)
        self.deleteBtn.clicked.connect(self.delete_region)
        self.regionList.currentRowChanged.connect(self.on_region_selected)
        self.overlay.regionClicked.connect(self.on_region_clicked_visual)
        self.refreshDevicesBtn.clicked.connect(self.refresh_devices)
        self.captureBtn.clicked.connect(self.capture_screenshot)
        self.loadImageBtn.clicked.connect(self.load_image_file)
        self.testBtn.clicked.connect(self.test_region)
        self.testOCRBtn.clicked.connect(self.test_ocr)
        self.saveBtn.clicked.connect(self.save_changes)
        
    def on_hide_non_selected_changed(self, state):
        self.overlay.set_hide_non_selected(state == 2)
        
    def refresh_devices(self):
        self.deviceCombo.clear()
        devices = self.adb.get_devices()
        for device in devices:
            self.deviceCombo.addItem(device.serial)
    
    def capture_screenshot(self):
        serial = self.deviceCombo.currentText()
        if not serial:
            QMessageBox.warning(self, "Warning", "Select a device first.")
            return
        
        device = self.adb.connect_device(serial)
        if device:
            img = self.adb.take_screenshot(device)
            if img is not None:
                self.overlay.set_image(img)
                app_logger.info(f"Screenshot captured from {serial}")
    
    def load_image_file(self):
        """Load an image from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Image", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            img = cv2.imread(file_path)
            if img is not None:
                self.overlay.set_image(img)
                app_logger.info(f"Image loaded from {file_path}")

    def refresh_regions(self):
        """Load and display all regions"""
        self.regionList.clear()
        
        # Load regions
        regions = self.assets.load_regions()
        self.overlay.set_regions(regions)
        
        for name in regions.keys():
            item = QListWidgetItem(f"📍 {name}")
            item.setData(Qt.ItemDataRole.UserRole, ("region", name))
            self.regionList.addItem(item)
        
        # Load images
        if os.path.exists("assets/images"):
            images = [f for f in os.listdir("assets/images") if f.endswith(('.png', '.jpg'))]
            for img_name in images:
                name_without_ext = os.path.splitext(img_name)[0]
                item = QListWidgetItem(f"🖼️ {name_without_ext}")
                item.setData(Qt.ItemDataRole.UserRole, ("image", name_without_ext))
                self.regionList.addItem(item)
    
    def on_region_selected(self, row):
        """When a region is selected from the list"""
        if row < 0:
            return
        
        item = self.regionList.item(row)
        data = item.data(Qt.ItemDataRole.UserRole)
        
        if data[0] == "region":
            region_name = data[1]
            self.current_region_name = region_name
            self.current_item_type = "region"
            self.overlay.set_selected_region(region_name)
            self.show_region_properties(region_name)
        elif data[0] == "image":
            self.current_region_name = data[1]
            self.current_item_type = "image"
            self.show_image_properties(data[1])
    
    def on_region_clicked_visual(self, region_name):
        """When a region is clicked in the visual overlay"""
        # Find and select in list
        for i in range(self.regionList.count()):
            item = self.regionList.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data[0] == "region" and data[1] == region_name:
                self.regionList.setCurrentRow(i)
                break
    
    def delete_region(self):
        """Delete selected region"""
        current_item = self.regionList.currentItem()
        if not current_item:
            return
        
        data = current_item.data(Qt.ItemDataRole.UserRole)
        if data[0] != "region":
            QMessageBox.warning(self, "Warning", "Select a region to delete")
            return
        
        name = data[1]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete region '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            regions = self.assets.load_regions()
            if name in regions:
                del regions[name]
                # Save back
                self.assets.regions = regions
                self.assets._persist_regions()
                app_logger.info(f"Region '{name}' deleted")
                self.refresh_regions()

    def show_image_properties(self, name):
        """Show properties for a selected image template"""
        self.clear_layout(self.formLayout)
        
        self.formLayout.addRow(SubtitleLabel(f"Image: {name}"))
        
        # Name Edit
        name_edit = LineEdit()
        name_edit.setText(name)
        name_edit.setObjectName("nameEdit")
        self.formLayout.addRow("Name:", name_edit)
        
        self.formLayout.addRow(BodyLabel("Image templates are managed via assets folder."))
        
        self.testBtn.setEnabled(True)
        self.testOCRBtn.setEnabled(False) # OCR not relevant for template images usually
        self.saveBtn.setEnabled(True)

    def clear_layout(self, layout):
        """Clear all items from a layout"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def show_region_properties(self, name):
        """Display region properties in the editor"""
        # Clear form
        self.clear_layout(self.formLayout)
        
        regions = self.assets.load_regions()
        if name not in regions:
            return
        
        region_data = regions[name]
        if isinstance(region_data, dict):
            region = region_data["region"]
            source_res = region_data.get("source_resolution")
        else:
            region = region_data
            source_res = None
        
        # Name
        name_edit = LineEdit()
        name_edit.setText(name)
        name_edit.setObjectName("nameEdit")
        self.formLayout.addRow("Name:", name_edit)
        
        # Type
        type_str = "Unknown"
        if isinstance(region, Region): type_str = "Rectangle"
        elif isinstance(region, PolygonRegion): type_str = "Polygon"
        elif isinstance(region, MultiRegion): type_str = "Multi-Region"
        
        type_label = BodyLabel(type_str)
        self.formLayout.addRow("Type:", type_label)
        
        # Resolution
        if source_res:
            res_label = BodyLabel(f"{source_res['width']}x{source_res['height']}")
            self.formLayout.addRow("Source Resolution:", res_label)
        
        # Region specific UI
        if isinstance(region, Region):
            self._show_rect_properties(region)
        elif isinstance(region, PolygonRegion):
             self._show_poly_properties(region)
        elif isinstance(region, MultiRegion):
             self._show_multi_region_properties(region)
        
        # OCR Mode Selection
        self.ocrModeCombo = ComboBox()
        self.ocrModeCombo.addItems(["default", "game", "number", "raw", "adaptive", "clean", "white_text"])
        self.ocrModeCombo.setToolTip("Select preprocessing mode for OCR testing")
        self.formLayout.addRow("OCR Mode:", self.ocrModeCombo)
        
        self.testBtn.setEnabled(True)
        self.testOCRBtn.setEnabled(True)
        self.saveBtn.setEnabled(True)

    def _show_rect_properties(self, region: Region):
            x_spin = SpinBox()
            x_spin.setRange(0, 10000)
            x_spin.setValue(region.x)
            x_spin.setObjectName("xSpin")
            self.formLayout.addRow("X:", x_spin)
            
            y_spin = SpinBox()
            y_spin.setRange(0, 10000)
            y_spin.setValue(region.y)
            y_spin.setObjectName("ySpin")
            self.formLayout.addRow("Y:", y_spin)
            
            w_spin = SpinBox()
            w_spin.setRange(1, 10000)
            w_spin.setValue(region.width)
            w_spin.setObjectName("wSpin")
            self.formLayout.addRow("Width:", w_spin)
            
            h_spin = SpinBox()
            h_spin.setRange(1, 10000)
            h_spin.setValue(region.height)
            h_spin.setObjectName("hSpin")
            self.formLayout.addRow("Height:", h_spin)

    def _show_poly_properties(self, region: PolygonRegion):
            # Show points in a table
            table = QTableWidget(len(region.points), 2)
            table.setHorizontalHeaderLabels(["X", "Y"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setObjectName("pointsTable")
            
            for i, point in enumerate(region.points):
                table.setItem(i, 0, QTableWidgetItem(str(point.x)))
                table.setItem(i, 1, QTableWidgetItem(str(point.y)))
            
            self.formLayout.addRow(BodyLabel("Points:"))
            self.formLayout.addRow(table)

    def _show_multi_region_properties(self, region: MultiRegion):
            # Show list of sub-regions
            count_label = BodyLabel(f"{len(region.regions)} sub-regions")
            self.formLayout.addRow("Count:", count_label)
            
            list_widget = QListWidget()
            list_widget.setFixedHeight(150)
            for i, sub in enumerate(region.regions):
                if isinstance(sub, Region):
                    list_widget.addItem(f"#{i+1}: Rect ({sub.x}, {sub.y}, {sub.width}x{sub.height})")
                elif isinstance(sub, PolygonRegion):
                    list_widget.addItem(f"#{i+1}: Poly ({len(sub.points)} points)")
            note_label = BodyLabel("(Editing sub-regions not supported in this view)")
            note_label.setStyleSheet("color: gray;")
            self.formLayout.addRow("", note_label)

    def save_changes(self):
        """Save edited region properties"""
        if not self.current_region_name:
            return
        
        regions = self.assets.load_regions()
        if self.current_region_name not in regions:
            return
        
        region_data = regions[self.current_region_name]
        if isinstance(region_data, dict):
            region = region_data["region"]
            source_res = region_data.get("source_resolution")
        else:
            region = region_data
            source_res = None
        
        # Get new name
        name_edit = self.propPanel.findChild(LineEdit, "nameEdit")
        new_name = name_edit.text() if name_edit else self.current_region_name
        
        # Update region
        if isinstance(region, Region):
            x_spin = self.propPanel.findChild(SpinBox, "xSpin")
            y_spin = self.propPanel.findChild(SpinBox, "ySpin")
            w_spin = self.propPanel.findChild(SpinBox, "wSpin")
            h_spin = self.propPanel.findChild(SpinBox, "hSpin")
            
            if x_spin and y_spin and w_spin and h_spin:
                new_region = Region(
                    x=x_spin.value(),
                    y=y_spin.value(),
                    width=w_spin.value(),
                    height=h_spin.value()
                )
                
                # Remove old if name changed
                if new_name != self.current_region_name:
                    del regions[self.current_region_name]
                
                regions[new_name] = {"region": new_region, "source_resolution": source_res}
                
        elif isinstance(region, PolygonRegion):
            table = self.propPanel.findChild(QTableWidget, "pointsTable")
            if table:
                points = []
                for i in range(table.rowCount()):
                    x = int(table.item(i, 0).text())
                    y = int(table.item(i, 1).text())
                    points.append(Point(x, y))
                
                new_region = PolygonRegion(points)
                
                # Remove old if name changed
                if new_name != self.current_region_name:
                    del regions[self.current_region_name]
                
                regions[new_name] = {"region": new_region, "source_resolution": source_res}

        elif isinstance(region, MultiRegion):
            # For MultiRegion, we only support renaming for now in this view
            if new_name != self.current_region_name:
                del regions[self.current_region_name]
                regions[new_name] = {"region": region, "source_resolution": source_res}
        
        # Save
        self.assets.regions = regions
        self.assets._persist_regions()
        self.current_region_name = new_name
        app_logger.info(f"Region '{new_name}' saved")
        self.refresh_regions()
        QMessageBox.information(self, "Success", "Changes saved successfully")
    
    def test_region(self):
        """Test region by clicking on device or test image matching"""
        if not self.current_region_name:
            return
        
        serial = self.deviceCombo.currentText()
        if not serial:
            QMessageBox.warning(self, "Warning", "Select a device first")
            return
        
        device = self.adb.connect_device(serial)
        if not device:
            return
        
        # Check if it's an image or region
        if hasattr(self, 'current_item_type') and self.current_item_type == "image":
            # Test image matching
            self.test_image_matching(device)
        else:
            # Test region clicking
            regions = self.assets.load_regions()
            if self.current_region_name not in regions:
                return
            
            region_data = regions[self.current_region_name]
            if isinstance(region_data, dict):
                region = region_data["region"]
            else:
                region = region_data
            
            # Get a point to click
            try:
                point = region.get_random_point()
                
                # Click on device
                self.adb.tap(device, point, duration_ms=100)
                app_logger.info(f"Tested region '{self.current_region_name}' at ({point.x}, {point.y})")
                QMessageBox.information(self, "Test Complete", f"Clicked at ({point.x}, {point.y})")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to test region: {str(e)}")
    
    def test_image_matching(self, device):
        """Test image template matching on current screenshot"""
        
        # Get threshold from slider if available
        threshold_slider = self.propPanel.findChild(QSlider, "thresholdSlider")
        threshold = (threshold_slider.value() / 100.0) if threshold_slider else 0.8
        
        # Get image template
        image_path = self.assets.get_image_path(self.current_region_name)
        if not image_path or not os.path.exists(image_path):
            QMessageBox.warning(self, "Error", "Image template not found")
            return
        
        # Take screenshot
        screen = self.adb.take_screenshot(device)
        if screen is None:
            QMessageBox.warning(self, "Error", "Failed to capture screenshot")
            return
        
        # Load template
        template = cv2.imread(image_path)
        if template is None:
            QMessageBox.warning(self, "Error", "Failed to load template image")
            return
        
        # Find image
        rect = self.vision.find_image_rect(screen, template, threshold=threshold)
        
        if rect:
            # Calculate center point
            center_x = rect.x + rect.width // 2
            center_y = rect.y + rect.height // 2
            
            # Update overlay to show the screenshot
            self.overlay.set_image(screen)
            
            # Click on the found location
            point = Point(center_x, center_y)
            self.adb.tap(device, point, duration_ms=100)
            
            app_logger.info(f"Image '{self.current_region_name}' found at ({center_x}, {center_y})")
            QMessageBox.information(
                self, 
                "Image Found!", 
                f"Image found at ({center_x}, {center_y})\n"
                f"Size: {rect.width}x{rect.height}\n"
                f"Threshold: {threshold:.2f}\n"
                f"Clicked on found location."
            )
        else:
            # Show screenshot anyway
            self.overlay.set_image(screen)
            QMessageBox.warning(
                self, 
                "Image Not Found", 
                f"Image template '{self.current_region_name}' not found on screen.\n"
                f"Threshold: {threshold:.2f}\n"
                f"Try adjusting the threshold slider."
            )

    def test_ocr(self):
        """Test OCR on the selected region"""
        if not self.current_region_name:
            return
            
        serial = self.deviceCombo.currentText()
        if not serial:
            QMessageBox.warning(self, "Warning", "Select a device first")
            return
            
        device = self.adb.connect_device(serial)
        if not device:
            return
            
        regions = self.assets.load_regions()
        if self.current_region_name not in regions:
            return
            
        region_data = regions[self.current_region_name]
        if isinstance(region_data, dict):
            region = region_data["region"]
        else:
            region = region_data
            
        # Take screenshot
        screen = self.adb.take_screenshot(device)
        if screen is None:
            QMessageBox.warning(self, "Error", "Failed to capture screenshot")
            return
            
        # Get selected mode
        mode = self.ocrModeCombo.currentText()
        app_logger.info(f"Testing OCR with mode: {mode}")
        
        try:
            target_region = None
            if isinstance(region, Region):
                target_region = region
            elif isinstance(region, PolygonRegion):
                pass
            
            if target_region:
                # 1. Get Preprocessed Image for Preview
                # Crop first
                x, y, w, h = target_region.x, target_region.y, target_region.width, target_region.height
                cropped = screen[y:y+h, x:x+w]
                preprocessed = self.vision.preprocess_image(cropped, method=mode)
                
                # 2. Run OCR
                text = self.vision.read_text(screen, target_region, preprocess=mode)
                
                # 3. Show Result with Image Preview
                w = OCRResultDialog(text, preprocessed, self)
                w.exec()
                
            else:
                 QMessageBox.warning(self, "Error", "OCR currently supports Rectangular regions only for testing.")
                 
        except Exception as e:
            QMessageBox.critical(self, "Error", f"OCR Failed: {str(e)}")

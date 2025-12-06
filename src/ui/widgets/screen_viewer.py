from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon
import cv2
import numpy as np

class ScreenViewer(QLabel):
    # Signals
    regionSelected = pyqtSignal(QRect)
    polygonSelected = pyqtSignal(list) # List of QPoint

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #202020; border: 1px solid #404040;")
        
        self.image = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        # Selection state
        self.mode = "rectangle" # or "polygon", "image_template", "multi"
        self.drawing = False
        self.start_point = QPoint()
        self.current_point = QPoint()
        self.polygon_points = []
        
        # For Multi-Region
        self.multi_regions = [] # List of (type, data) tuples. type="rect"|"poly"
        self.current_multi_mode = "rectangle" # Sub-mode for multi selection

    def set_image(self, cv_img):
        if cv_img is None:
            return
            
        self.image = cv_img
        h, w, ch = cv_img.shape
        bytes_per_line = ch * w
        qt_img = QImage(cv_img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
        self.original_pixmap = QPixmap.fromImage(qt_img)
        self.update_display()

    def update_display(self):
        if not hasattr(self, 'original_pixmap'):
            return
            
        # Scale to fit while maintaining aspect ratio
        scaled_pixmap = self.original_pixmap.scaled(
            self.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Calculate scale factor and offsets for coordinate mapping
        self.scale_factor = scaled_pixmap.width() / self.original_pixmap.width()
        self.offset_x = (self.width() - scaled_pixmap.width()) // 2
        self.offset_y = (self.height() - scaled_pixmap.height()) // 2
        
        self.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if self.image is None:
            return
            
        # Map widget coordinates to image coordinates
        img_x = int((event.pos().x() - self.offset_x) / self.scale_factor)
        img_y = int((event.pos().y() - self.offset_y) / self.scale_factor)
        
        # Clamp to image bounds
        h, w, _ = self.image.shape
        img_x = max(0, min(img_x, w))
        img_y = max(0, min(img_y, h))
        
        # Determine effective mode
        effective_mode = self.mode
        if self.mode == "multi":
            effective_mode = self.current_multi_mode

        if effective_mode in ["rectangle", "image_template"]:
            self.drawing = True
            self.start_point = QPoint(img_x, img_y)
            self.current_point = QPoint(img_x, img_y)
            
        elif effective_mode == "polygon":
            if event.button() == Qt.MouseButton.LeftButton:
                self.polygon_points.append(QPoint(img_x, img_y))
                self.update()
            elif event.button() == Qt.MouseButton.RightButton:
                # Finish polygon
                if len(self.polygon_points) >= 3:
                    if self.mode == "multi":
                        self.multi_regions.append(("poly", list(self.polygon_points)))
                        self.polygonSelected.emit(self.polygon_points) # Emit just for feedback
                    else:
                        self.polygonSelected.emit(self.polygon_points)
                    
                    self.polygon_points = []
                    self.update()

    def mouseMoveEvent(self, event):
        effective_mode = self.mode
        if self.mode == "multi":
            effective_mode = self.current_multi_mode

        if self.drawing and effective_mode in ["rectangle", "image_template"]:
            img_x = int((event.pos().x() - self.offset_x) / self.scale_factor)
            img_y = int((event.pos().y() - self.offset_y) / self.scale_factor)
            
            h, w, _ = self.image.shape
            img_x = max(0, min(img_x, w))
            img_y = max(0, min(img_y, h))
            
            self.current_point = QPoint(img_x, img_y)
            self.update()

    def mouseReleaseEvent(self, event):
        effective_mode = self.mode
        if self.mode == "multi":
            effective_mode = self.current_multi_mode

        if self.drawing and effective_mode in ["rectangle", "image_template"]:
            self.drawing = False
            rect = QRect(self.start_point, self.current_point).normalized()
            if rect.width() > 5 and rect.height() > 5:
                if self.mode == "multi":
                    self.multi_regions.append(("rect", rect))
                    self.regionSelected.emit(rect) # Emit just for feedback
                else:
                    self.regionSelected.emit(rect)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        
        if self.image is None:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Multi-Regions
        if self.mode == "multi":
            pen = QPen(QColor(0, 200, 255), 2)
            painter.setPen(pen)
            
            for r_type, data in self.multi_regions:
                if r_type == "rect":
                    rect = data
                    x1 = int(rect.x() * self.scale_factor) + self.offset_x
                    y1 = int(rect.y() * self.scale_factor) + self.offset_y
                    w = int(rect.width() * self.scale_factor)
                    h = int(rect.height() * self.scale_factor)
                    painter.drawRect(x1, y1, w, h)
                elif r_type == "poly":
                    points = []
                    for p in data:
                        x = int(p.x() * self.scale_factor) + self.offset_x
                        y = int(p.y() * self.scale_factor) + self.offset_y
                        points.append(QPoint(x, y))
                    if points:
                        painter.drawPolygon(QPolygon(points))

        # Draw current selection being drawn
        pen = QPen(QColor(0, 255, 0), 2)
        painter.setPen(pen)
        
        effective_mode = self.mode
        if self.mode == "multi":
            effective_mode = self.current_multi_mode
        
        if effective_mode in ["rectangle", "image_template"] and self.drawing:
            # Convert back to widget coordinates for drawing
            x1 = int(self.start_point.x() * self.scale_factor) + self.offset_x
            y1 = int(self.start_point.y() * self.scale_factor) + self.offset_y
            x2 = int(self.current_point.x() * self.scale_factor) + self.offset_x
            y2 = int(self.current_point.y() * self.scale_factor) + self.offset_y
            
            painter.drawRect(QRect(QPoint(x1, y1), QPoint(x2, y2)))
            
        elif effective_mode == "polygon" and self.polygon_points:
            points = []
            for p in self.polygon_points:
                x = int(p.x() * self.scale_factor) + self.offset_x
                y = int(p.y() * self.scale_factor) + self.offset_y
                points.append(QPoint(x, y))
            
            if len(points) > 0:
                painter.drawPolyline(QPolygon(points))
                # Draw line to cursor
                last_pt = points[-1]
                cursor_pt = self.mapFromGlobal(self.cursor().pos())
                painter.drawLine(last_pt, cursor_pt)

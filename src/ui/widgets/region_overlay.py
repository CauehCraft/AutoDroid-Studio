from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon, QBrush
import cv2
import numpy as np
from shapely.geometry import Point as ShapelyPoint, Polygon

from ...core.models import Region, PolygonRegion, MultiRegion

class RegionOverlay(QLabel):
    """Widget for displaying screenshot with region overlays"""
    regionClicked = pyqtSignal(str)  # Emits region name when clicked
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #202020; border: 1px solid #404040;")
        
        self.image = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        # Regions to display
        self.regions = {}  # {name: {"region": Region/PolygonRegion, "source_resolution": {...}}}
        self.selected_region = None
        self.hide_non_selected = False
        
    def set_image(self, cv_img):
        """Set the background screenshot"""
        if cv_img is None:
            return
            
        self.image = cv_img
        h, w, ch = cv_img.shape
        bytes_per_line = ch * w
        qt_img = QImage(cv_img.data, w, h, bytes_per_line, QImage.Format.Format_BGR888)
        self.original_pixmap = QPixmap.fromImage(qt_img)
        self.update_display()

    def update_display(self):
        """Update the display with current image"""
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
        self.update()

    def set_regions(self, regions):
        """Set regions to display"""
        self.regions = regions
        self.update()
    
    def set_selected_region(self, name):
        """Highlight a specific region"""
        self.selected_region = name
        self.update()

    def set_hide_non_selected(self, hide):
        """Set whether to hide non-selected regions"""
        self.hide_non_selected = hide
        self.update()

    def resizeEvent(self, event):
        self.update_display()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Detect clicks on regions"""
        if self.image is None:
            return
        
        # Map widget coordinates to image coordinates
        img_x = int((event.pos().x() - self.offset_x) / self.scale_factor)
        img_y = int((event.pos().y() - self.offset_y) / self.scale_factor)
        
        # Check which region was clicked        
        for name, region_data in self.regions.items():
            if isinstance(region_data, dict):
                region = region_data["region"]
            else:
                region = region_data
            
            # Helper to check single region
            def check_hit(r, x, y):
                if isinstance(r, Region):
                    return (r.x <= x <= r.x + r.width and
                            r.y <= y <= r.y + r.height)
                elif isinstance(r, PolygonRegion):
                    poly = Polygon([(p.x, p.y) for p in r.points])
                    point = ShapelyPoint(x, y)
                    return poly.contains(point)
                return False

            if isinstance(region, MultiRegion):
                for sub in region.regions:
                    if check_hit(sub, img_x, img_y):
                        self.regionClicked.emit(name)
                        return
            elif check_hit(region, img_x, img_y):
                self.regionClicked.emit(name)
                return

    def paintEvent(self, event):
        super().paintEvent(event)
        
        if self.image is None:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        
        # Draw all regions
        for name, region_data in self.regions.items():
            if isinstance(region_data, dict):
                region = region_data["region"]
            else:
                region = region_data
            
            # Color based on selection
            is_selected = (name == self.selected_region)
            
            if self.hide_non_selected and not is_selected:
                continue
                
            color = QColor(0, 255, 0) if not is_selected else QColor(255, 165, 0)
            pen = QPen(color, 3 if is_selected else 2)
            painter.setPen(pen)
            
            # Semi-transparent fill for selected
            if is_selected:
                brush = QBrush(QColor(255, 165, 0, 50))
                painter.setBrush(brush)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # Helper to draw single region
            def draw_region(r):
                if isinstance(r, Region):
                    # Draw rectangle
                    x1 = int(r.x * self.scale_factor) + self.offset_x
                    y1 = int(r.y * self.scale_factor) + self.offset_y
                    width = int(r.width * self.scale_factor)
                    height = int(r.height * self.scale_factor)
                    
                    painter.drawRect(x1, y1, width, height)
                    
                elif isinstance(r, PolygonRegion):
                    # Draw polygon
                    points = []
                    for p in r.points:
                        x = int(p.x * self.scale_factor) + self.offset_x
                        y = int(p.y * self.scale_factor) + self.offset_y
                        points.append(QPoint(x, y))
                    
                    if points:
                        painter.drawPolygon(QPolygon(points))

            if isinstance(region, MultiRegion):
                for sub in region.regions:
                    draw_region(sub)
                # Draw label on the first sub-region
                if region.regions:
                    first = region.regions[0]
                    if isinstance(first, Region):
                        lx = int(first.x * self.scale_factor) + self.offset_x
                        ly = int(first.y * self.scale_factor) + self.offset_y
                    elif isinstance(first, PolygonRegion) and first.points:
                        lx = int(first.points[0].x * self.scale_factor) + self.offset_x
                        ly = int(first.points[0].y * self.scale_factor) + self.offset_y
                    else:
                        lx, ly = 0, 0
                    
                    painter.setPen(QPen(color))
                    painter.drawText(lx + 5, ly - 5, name)
                    
            else:
                draw_region(region)
                # Draw label
                if isinstance(region, Region):
                    lx = int(region.x * self.scale_factor) + self.offset_x
                    ly = int(region.y * self.scale_factor) + self.offset_y
                elif isinstance(region, PolygonRegion) and region.points:
                    lx = int(region.points[0].x * self.scale_factor) + self.offset_x
                    ly = int(region.points[0].y * self.scale_factor) + self.offset_y
                else:
                    lx, ly = 0, 0
                
                painter.setPen(QPen(color))
                painter.drawText(lx + 5, ly - 5, name)

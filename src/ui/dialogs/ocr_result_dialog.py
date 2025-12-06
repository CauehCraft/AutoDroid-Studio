from qfluentwidgets import MessageBoxBase, SubtitleLabel, BodyLabel
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

class OCRResultDialog(MessageBoxBase):
    def __init__(self, text, image_data, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("OCR Result", self)
        
        # Image Preview
        self.imgLabel = QLabel(self)
        self.imgLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imgLabel.setStyleSheet("border: 1px solid #444; background: #000;")
        
        # Convert numpy image to QPixmap
        h, w = image_data.shape
        qimg = QImage(image_data.data, w, h, w, QImage.Format.Format_Grayscale8)
        pixmap = QPixmap.fromImage(qimg)
        
        # Scale if too small
        if w < 200:
            pixmap = pixmap.scaled(w*2, h*2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        
        self.imgLabel.setPixmap(pixmap)
        
        self.textLabel = BodyLabel(f"Detected Text:\n\n'{text}'", self)
        self.textLabel.setStyleSheet("font-size: 14px; font-weight: bold; color: #00A6FB;")
        
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.imgLabel)
        self.viewLayout.addWidget(self.textLabel)
        
        self.widget.setMinimumWidth(300)
        self.yesButton.setText("OK")
        self.cancelButton.hide()

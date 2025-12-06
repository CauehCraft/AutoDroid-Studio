import sys
import os
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    # Enable High DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()

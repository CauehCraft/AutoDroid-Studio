from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QStackedWidget
from PyQt6.QtCore import Qt
from qfluentwidgets import (NavigationInterface, NavigationItemPosition, 
                            FluentWindow, SubtitleLabel, setTheme, Theme)
from qfluentwidgets import FluentIcon as FIF

from .dashboard import Dashboard
from .editor import MacroEditor
from .inspector import ScreenInspector
from .region_manager import RegionManager

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.initWindow()

        # Create sub-interfaces
        self.dashboard = Dashboard(self)
        self.editor = MacroEditor(self)
        self.inspector = ScreenInspector(self)
        self.region_manager = RegionManager(self)

        # Add sub-interfaces to navigation
        self.addSubInterface(self.dashboard, FIF.HOME, 'Dashboard')
        self.addSubInterface(self.editor, FIF.EDIT, 'Macro Editor')
        self.addSubInterface(self.inspector, FIF.CAMERA, 'Screen Inspector')
        self.addSubInterface(self.region_manager, FIF.TILES, 'Region Manager')
        
        # Connect signals
        self.dashboard.macroSelected.connect(self.on_macro_selected)

    def on_macro_selected(self, path):
        self.editor.load_macro(path)
        self.switchTo(self.editor)
        
        # Add settings (placeholder for now)
        # self.addSubInterface(self.settings, FIF.SETTING, 'Settings', NavigationItemPosition.BOTTOM)

    def initWindow(self):
        self.resize(1200, 800)
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self.setWindowTitle('AutoDroid Studio')
        
        # Center on screen
        desktop = QApplication.primaryScreen().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)
        
        # Set theme
        setTheme(Theme.DARK)

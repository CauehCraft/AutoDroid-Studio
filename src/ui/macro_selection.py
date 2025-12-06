import os
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QListWidgetItem, QMessageBox, QInputDialog)
from qfluentwidgets import (SubtitleLabel, PrimaryPushButton, PushButton, 
                            CardWidget, SearchLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal
from ..core.models import Macro, Size

class MacroSelection(QWidget):
    macroSelected = pyqtSignal(str, object) # filename, macro_object

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("macroSelectionInterface")
        self.macros_dir = "macros"
        if not os.path.exists(self.macros_dir):
            os.makedirs(self.macros_dir)
        self.setupUI()
        self.refresh_macros()
        self.applyStyles()

    def applyStyles(self):
        self.setStyleSheet("""
            QListWidget {
                background-color: rgb(32, 32, 32);
                color: white;
                border: 1px solid rgb(50, 50, 50);
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: rgb(0, 120, 215);
            }
            QLabel {
                color: white;
            }
        """)

    def setupUI(self):
        self.vBoxLayout = QVBoxLayout(self)
        
        self.headerLabel = SubtitleLabel('Macro Manager', self)
        self.vBoxLayout.addWidget(self.headerLabel)
        
        # Search
        self.searchBar = SearchLineEdit(self)
        self.searchBar.setPlaceholderText("Search macros...")
        self.searchBar.textChanged.connect(self.filter_macros)
        self.vBoxLayout.addWidget(self.searchBar)
        
        # List
        self.macroList = QListWidget(self)
        self.vBoxLayout.addWidget(self.macroList)
        
        # Buttons
        self.btnLayout = QHBoxLayout()
        self.newBtn = PrimaryPushButton('New Macro', self)
        self.editBtn = PushButton('Edit Selected', self)
        self.deleteBtn = PushButton('Delete', self)
        self.refreshBtn = PushButton('Refresh', self)
        
        self.btnLayout.addWidget(self.newBtn)
        self.btnLayout.addWidget(self.editBtn)
        self.btnLayout.addWidget(self.deleteBtn)
        self.btnLayout.addWidget(self.refreshBtn)
        
        self.vBoxLayout.addLayout(self.btnLayout)
        
        self.newBtn.clicked.connect(self.create_macro)
        self.editBtn.clicked.connect(self.edit_macro)
        self.deleteBtn.clicked.connect(self.delete_macro)
        self.refreshBtn.clicked.connect(self.refresh_macros)
        self.macroList.itemDoubleClicked.connect(self.edit_macro)

    def refresh_macros(self):
        self.macroList.clear()
        if os.path.exists(self.macros_dir):
            for f in os.listdir(self.macros_dir):
                if f.endswith(".json"):
                    self.macroList.addItem(f)

    def filter_macros(self, text):
        for i in range(self.macroList.count()):
            item = self.macroList.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def create_macro(self):
        name, ok = QInputDialog.getText(self, "New Macro", "Enter macro name:")
        if ok and name:
            filename = f"{name.replace(' ', '_')}.json"
            path = os.path.join(self.macros_dir, filename)
            
            if os.path.exists(path):
                QMessageBox.warning(self, "Error", "Macro already exists!")
                return
            
            # Create default macro
            macro = Macro(name=name, target_resolution=Size(1080, 1920))
            try:
                with open(path, 'w') as f:
                    json.dump(macro.to_dict(), f, indent=2)
                self.refresh_macros()
                # Select the new item
                items = self.macroList.findItems(filename, Qt.MatchFlag.MatchExactly)
                if items:
                    self.macroList.setCurrentItem(items[0])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create macro: {e}")

    def edit_macro(self):
        item = self.macroList.currentItem()
        if not item:
            return
            
        filename = item.text()
        path = os.path.join(self.macros_dir, filename)
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                self.macroSelected.emit(path, None) 
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load macro: {e}")

    def delete_macro(self):
        item = self.macroList.currentItem()
        if not item:
            return
            
        filename = item.text()
        path = os.path.join(self.macros_dir, filename)
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete '{filename}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                self.refresh_macros()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete macro: {e}")

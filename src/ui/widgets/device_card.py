from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy
from qfluentwidgets import CardWidget, BodyLabel, CaptionLabel, PushButton, TableWidget, StrongBodyLabel, InfoBadge
from PyQt6.QtCore import Qt, pyqtSignal
from qfluentwidgets import ComboBox, ToolButton, FluentIcon as FIF

class DeviceCard(CardWidget):
    def __init__(self, serial, parent=None):
        super().__init__(parent=parent)
        self.serial = serial
        self.macros = []
        self.setupUI()
        self.applyStyles()

    def applyStyles(self):
        self.setStyleSheet("""
            DeviceCard {
                background-color: rgb(45, 45, 45);
                border: 1px solid rgb(60, 60, 60);
                border-radius: 8px;
            }
            QLabel {
                color: white;
            }
            QTableWidget {
                background-color: rgb(32, 32, 32);
                color: white;
                border: 1px solid rgb(50, 50, 50);
                gridline-color: rgb(60, 60, 60);
            }
            QHeaderView::section {
                background-color: rgb(40, 40, 40);
                color: white;
                border: none;
            QHeaderView::section {
                background-color: rgb(40, 40, 40);
                color: white;
                border: none;
                padding: 2px;
            }
            QTableWidget::item {
                padding: 2px;
            }
        """)
        
    def setupUI(self):
        self.vLayout = QVBoxLayout(self)
        
        # Header: Name + Status
        self.headerLayout = QHBoxLayout()
        self.nameLabel = StrongBodyLabel(f"Device: {self.serial}", self)
        self.statusBadge = InfoBadge.info("Idle")
        
        self.headerLayout.addWidget(self.nameLabel)
        self.headerLayout.addStretch(1)
        self.headerLayout.addWidget(self.statusBadge)
        
        self.vLayout.addLayout(self.headerLayout)
        
        # Macro Info
        self.macroInfoLayout = QHBoxLayout()
        self.macroLabel = BodyLabel("No Macro Running", self)
        self.macroLabel.setMaximumWidth(200)
        self.macroInfoLayout.addWidget(self.macroLabel)
        
        # Macro Controls
        self.macroCombo = ComboBox(self)
        self.macroCombo.setPlaceholderText("Select Macro")
        self.macroInfoLayout.addWidget(self.macroCombo)
        
        self.runBtn = ToolButton(FIF.PLAY, self)
        self.runBtn.setToolTip("Run Macro")
        self.runBtn.clicked.connect(self.on_run)
        self.macroInfoLayout.addWidget(self.runBtn)
        
        self.pauseBtn = ToolButton(FIF.PAUSE, self)
        self.pauseBtn.setToolTip("Pause Macro")
        self.pauseBtn.setEnabled(False)
        self.pauseBtn.clicked.connect(self.on_pause)
        self.macroInfoLayout.addWidget(self.pauseBtn)
        
        self.stopBtn = ToolButton(FIF.CLOSE, self)
        self.stopBtn.setToolTip("Stop Macro")
        self.stopBtn.setEnabled(False)
        self.stopBtn.clicked.connect(self.on_stop)
        self.macroInfoLayout.addWidget(self.stopBtn)
        
        self.vLayout.addLayout(self.macroInfoLayout)
        
        # Expand Button
        self.expandBtn = PushButton("Show Details", self)
        self.expandBtn.setCheckable(True)
        self.expandBtn.clicked.connect(self.toggle_details)
        self.vLayout.addWidget(self.expandBtn)
        
        # Expandable Section for Variables and Logs
        self.detailsContainer = QWidget(self)
        self.detailsLayout = QVBoxLayout(self.detailsContainer)
        self.detailsLayout.setContentsMargins(0, 0, 0, 0)
        
        # Variables Table
        # Variables Table
        self.detailsLayout.addWidget(CaptionLabel("Variables", self.detailsContainer))
        self.varTable = TableWidget(self.detailsContainer)
        self.varTable.setColumnCount(2)
        self.varTable.horizontalHeader().hide()
        self.varTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.varTable.verticalHeader().hide()
        self.varTable.setMinimumHeight(150)
        self.varTable.setMaximumHeight(300) # Limit max height to prevent taking over too much space
        self.varTable.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.detailsLayout.addWidget(self.varTable)
        
        self.vLayout.addWidget(self.detailsContainer)
        self.detailsContainer.hide() # Start hidden
        
    def toggle_details(self, checked):
        self.detailsContainer.setVisible(checked)
        self.expandBtn.setText("Hide Details" if checked else "Show Details")
        
    def update_status(self, status: str, macro_name: str = None):
        self.statusBadge.setText(status)
        if macro_name:
            self.macroLabel.setText(f"{macro_name}")
        else:
            self.macroLabel.setText("No Macro Running")
            
    def update_variables(self, variables: dict):
        self.varTable.setRowCount(len(variables))
        for i, (name, value) in enumerate(variables.items()):
            self.varTable.setItem(i, 0, QTableWidgetItem(str(name)))
            self.varTable.setItem(i, 1, QTableWidgetItem(str(value)))
        self.varTable.resizeRowsToContents()
        # row_height = self.varTable.rowHeight(0) if self.varTable.rowCount() > 0 else 30
        # total_height = (row_height * len(variables)) + 10
        # self.varTable.setFixedHeight(min(max(150, total_height), 400))

    # Signals
    run_signal = pyqtSignal(str, str) # serial, macro_filename
    pause_signal = pyqtSignal(str)    # serial
    stop_signal = pyqtSignal(str)     # serial

    def set_macros(self, macro_list):
        self.macros = macro_list
        current = self.macroCombo.currentText()
        self.macroCombo.clear()
        self.macroCombo.addItems(macro_list)
        if current in macro_list:
            self.macroCombo.setCurrentText(current)

    def on_run(self):
        macro_name = self.macroCombo.currentText()
        if macro_name:
            self.run_signal.emit(self.serial, macro_name)

    def on_pause(self):
        self.pause_signal.emit(self.serial)
        # Toggle icon based on current state (will be updated by status update, but for immediate feedback)
        if self.pauseBtn.icon().name() == FIF.PAUSE.name:
             self.pauseBtn.setIcon(FIF.PLAY)
             self.pauseBtn.setToolTip("Resume Macro")
        else:
             self.pauseBtn.setIcon(FIF.PAUSE)
             self.pauseBtn.setToolTip("Pause Macro")

    def on_stop(self):
        self.stop_signal.emit(self.serial)
        
    def set_running_state(self, is_running):
        self.runBtn.setEnabled(not is_running)
        self.pauseBtn.setEnabled(is_running)
        self.stopBtn.setEnabled(is_running)
        self.macroCombo.setEnabled(not is_running)
        
        if not is_running:
            self.pauseBtn.setIcon(FIF.PAUSE)
            self.pauseBtn.setToolTip("Pause Macro")


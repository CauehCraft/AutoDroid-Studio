
COMMON_STYLE = """
    QWidget {
        background-color: transparent;
        color: white;
    }
    
    QListWidget, QTableWidget, QTextEdit {
        background-color: rgb(32, 32, 32);
        border: 1px solid rgb(50, 50, 50);
        border-radius: 5px;
        outline: none;
    }
    
    QListWidget::item, QTableWidget::item {
        padding: 5px;
    }
    
    QListWidget::item:selected, QTableWidget::item:selected {
        background-color: #009faa;
        border-radius: 3px;
        border: none;
    }
    
    QListWidget::item:hover, QTableWidget::item:hover {
        background-color: rgb(45, 45, 45);
    }
    
    QHeaderView::section {
        background-color: rgb(45, 45, 45);
        color: white;
        border: none;
        padding: 4px;
        border-right: 1px solid rgb(60, 60, 60);
    }
    
    QTableCornerButton::section {
        background-color: rgb(45, 45, 45);
        border: 1px solid rgb(60, 60, 60);
    }
    
    QSplitter::handle {
        background-color: rgb(45, 45, 45);
        border: 1px solid rgb(60, 60, 60);
        width: 2px;
    }
    
    /* ScrollBar Styling to match Fluent Design */
    QScrollBar:vertical {
        background: transparent;
        width: 6px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: rgb(80, 80, 80);
        min-height: 20px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgb(120, 120, 120);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
    
    QScrollBar:horizontal {
        background: transparent;
        height: 6px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: rgb(80, 80, 80);
        min-width: 20px;
        border-radius: 3px;
    }
    QScrollBar::handle:horizontal:hover {
        background: rgb(120, 120, 120);
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: transparent;
    }
    
    /* GroupBox */
    QGroupBox {
        border: 1px solid rgb(60, 60, 60);
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        color: white;
    }
"""

DASHBOARD_STYLE = """
    QTextEdit, QListWidget {
        background-color: rgb(32, 32, 32);
        color: white;
        border: 1px solid rgb(50, 50, 50);
        border-radius: 5px;
    }
    QLabel {
        color: white;
    }
    QWidget#dashboardInterface, QScrollArea {
        background-color: rgb(32, 32, 32);
    }
    /* QWidget { background-color: transparent; }  -- Already in COMMON_STYLE */
    QListWidget::item {
        height: 60px;
        border-bottom: 1px solid rgb(45, 45, 45);
    }
    QListWidget::item:selected {
        background-color: rgb(45, 45, 45);
    }
    QListWidget::item:hover {
        background-color: rgb(40, 40, 40);
    }
"""

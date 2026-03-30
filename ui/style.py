# ui/style.py

DARK_THEME_QSS = """
/* 全局设定 */
QWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 10pt;
}

/* 按钮美化 */
QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 12px;
    color: #ffffff;
}
QPushButton:hover {
    background-color: #505050;
    border: 1px solid #007acc; /* 悬停时的高亮蓝 */
}
QPushButton:pressed {
    background-color: #1e1e1e;
}
QPushButton:checked {
    background-color: #007acc; /* 选中状态 */
    border: 1px solid #005f9e;
}

/* 强调色按钮 (比如加载、导出) */
QPushButton#primary_btn {
    background-color: #007acc;
    border: none;
    font-weight: bold;
}
QPushButton#primary_btn:hover {
    background-color: #008be0;
}

/* 下拉框 */
QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}

/* 输入框 & 数字框 */
QLineEdit, QDoubleSpinBox, QSpinBox {
    background-color: #1e1e1e;
    border: 1px solid #444;
    border-radius: 3px;
    padding: 4px;
    color: #fff;
    selection-background-color: #007acc;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: transparent;
    width: 16px;
}

/* 分组框 */
QGroupBox {
    border: 1px solid #444;
    border-radius: 6px;
    margin-top: 12px; /* 给标题留位置 */
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: #007acc; /* 标题蓝色高亮 */
}

/* 滚动条美化 */
QScrollBar:vertical {
    background: #2b2b2b;
    width: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #555;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #777;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* 文本框 (Log) */
QPlainTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #444;
    color: #00ff00; /* 极客绿文字 */
    font-family: Consolas, monospace;
}

/* 工具箱 (折叠面板) */
QToolBox::tab {
    background: #3c3c3c;
    border-radius: 4px;
    color: #e0e0e0;
    font-weight: bold;
    padding-left: 10px; 
}
QToolBox::tab:selected {
    background: #444;
    color: #007acc;
    font-style: italic;
}
"""
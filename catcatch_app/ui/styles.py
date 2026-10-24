"""
CatCatch Downloader - Professional Slate Theme (现代专业深色主题)
以 Zinc / Slate 中性现代灰为基底，搭配纯净极简的工程级蓝调设计，彻底告别花哨杂乱的 Emoji
"""

DARK_THEME = """
/* 全局基础设置 */
QMainWindow, QDialog {
    background-color: #121316;
    color: #e4e4e7;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: #121316;
    color: #e4e4e7;
}

/* 顶部主工具栏 */
QToolBar {
    background-color: #18191d;
    border-bottom: 1px solid #23252a;
    padding: 6px 12px;
    spacing: 6px;
}

QToolButton {
    background-color: transparent;
    color: #d4d4d8;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #27292f;
    border-color: #32353c;
    color: #ffffff;
}

QToolButton:pressed {
    background-color: #3875f6;
    color: #ffffff;
}

/* 按钮通用控件 */
QPushButton {
    background-color: #22242a;
    color: #d4d4d8;
    border: 1px solid #30333b;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #2c2f37;
    border-color: #3875f6;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #2b63db;
    color: #ffffff;
}

QPushButton:disabled {
    background-color: #18191d;
    color: #52525b;
    border-color: #23252a;
}

QPushButton.primary {
    background-color: #3875f6;
    color: #ffffff;
    border: 1px solid #3875f6;
    font-weight: 600;
}

QPushButton.primary:hover {
    background-color: #4f87ff;
    border-color: #4f87ff;
}

QPushButton.primary:pressed {
    background-color: #2b63db;
}

/* 文本与下拉输入 */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #1a1b20;
    color: #f4f4f5;
    border: 1px solid #2e3138;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #3875f6;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #3875f6;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

/* 左侧分类导航树 */
QTreeWidget {
    background-color: #16171b;
    border-right: 1px solid #23252a;
    border-top: none;
    border-bottom: none;
    border-left: none;
    padding: 8px 6px;
    outline: none;
}

QTreeWidget::item {
    padding: 7px 10px;
    border-radius: 6px;
    margin: 2px 2px;
    color: #a1a1aa;
    font-weight: 500;
}

QTreeWidget::item:hover {
    background-color: #202228;
    color: #f4f4f5;
}

QTreeWidget::item:selected {
    background-color: #272a32;
    color: #3875f6;
    font-weight: 600;
}

/* 中央多任务表格 */
QTableWidget {
    background-color: #121316;
    border: none;
    gridline-color: #1f2126;
    selection-background-color: #22252c;
    selection-color: #ffffff;
    outline: none;
}

QTableWidget::item {
    padding: 8px 6px;
    border-bottom: 1px solid #1c1d22;
}

QTableWidget::item:selected {
    background-color: #22252c;
}

QHeaderView::section {
    background-color: #16171b;
    color: #a1a1aa;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #23252a;
    border-right: 1px solid #1d1e23;
    font-weight: 600;
    font-size: 12px;
}

/* 优雅现代进度条 */
QProgressBar {
    border: 1px solid #282b32;
    border-radius: 4px;
    text-align: center;
    background-color: #18191d;
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
    min-height: 14px;
    max-height: 14px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3875f6, stop:1 #60a5fa);
    border-radius: 3px;
}

/* 细致滚动条 */
QScrollBar:vertical {
    border: none;
    background: #121316;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #272a31;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3b3f49;
}

QScrollBar:horizontal {
    border: none;
    background: #121316;
    height: 8px;
}

QScrollBar::handle:horizontal {
    background: #272a31;
    min-width: 24px;
    border-radius: 4px;
}

/* 选项卡 TabWidget */
QTabWidget::pane {
    border: 1px solid #23252a;
    border-radius: 6px;
    background-color: #16171b;
}

QTabBar::tab {
    background-color: #121316;
    color: #71717a;
    border: 1px solid #23252a;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 4px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #1a1b20;
    color: #3875f6;
    font-weight: 600;
    border-color: #3875f6;
}

/* 状态栏 */
QStatusBar {
    background-color: #16171b;
    color: #71717a;
    border-top: 1px solid #23252a;
    font-size: 12px;
    padding: 3px 8px;
}

/* 分组框 */
QGroupBox {
    border: 1px solid #26282e;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
    color: #e4e4e7;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #3875f6;
}

/* 右键上下文菜单 */
QMenu {
    background-color: #1c1d22;
    border: 1px solid #2e3138;
    border-radius: 6px;
    padding: 4px 0;
}

QMenu::item {
    padding: 6px 20px;
    color: #d4d4d8;
}

QMenu::item:selected {
    background-color: #272a31;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #26282e;
    margin: 4px 6px;
}
"""

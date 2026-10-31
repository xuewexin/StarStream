"""
CatCatch Downloader - Theme Engine & Custom Background Styling
支持多款精致主题切换 (暗黑曜石、暗夜星河、青黛碧玉、赛博暗金、皓月晨曦) 与自定义壁纸半透明毛玻璃特效
"""
import os
from catcatch_app.core.config import config


THEMES = {
    "dark": {
        "id": "dark",
        "name": "暗黑曜石 (经典深色)",
        "icon_color": "#3875f6",
        "bg_main": "#0f172a",
        "bg_panel": "#1e293b",
        "bg_tree": "#131b2e",
        "bg_card": "#1e293b",
        "bg_hover": "#334155",
        "bg_selected": "#2563eb",
        "border": "#334155",
        "border_subtle": "#1e293b",
        "border_focus": "#38bdf8",
        "accent": "#38bdf8",
        "accent_hover": "#60a5fa",
        "accent_gradient_end": "#818cf8",
        "text": "#f8fafc",
        "text_secondary": "#cbd5e1",
        "text_muted": "#94a3b8",
        "scroll_handle": "#334155",
        "scroll_handle_hover": "#475569",
        "is_light": False,
    },
    "midnight": {
        "id": "midnight",
        "name": "暗夜星河 (极客紫夜)",
        "icon_color": "#a855f7",
        "bg_main": "#0b0914",
        "bg_panel": "#171329",
        "bg_tree": "#120e20",
        "bg_card": "#1c1733",
        "bg_hover": "#2e2452",
        "bg_selected": "#433575",
        "border": "#2e2452",
        "border_subtle": "#201a36",
        "border_focus": "#c084fc",
        "accent": "#c084fc",
        "accent_hover": "#d8b4fe",
        "accent_gradient_end": "#38bdf8",
        "text": "#f8fafc",
        "text_secondary": "#e2e8f0",
        "text_muted": "#a5b4fc",
        "scroll_handle": "#2e2452",
        "scroll_handle_hover": "#433575",
        "is_light": False,
    },
    "emerald": {
        "id": "emerald",
        "name": "青黛碧玉 (翠绿护眼)",
        "icon_color": "#10b981",
        "bg_main": "#06120e",
        "bg_panel": "#0d241c",
        "bg_tree": "#0a1c16",
        "bg_card": "#122f25",
        "bg_hover": "#1d4738",
        "bg_selected": "#10b981",
        "border": "#1d4738",
        "border_subtle": "#14332a",
        "border_focus": "#34d399",
        "accent": "#34d399",
        "accent_hover": "#6ee7b7",
        "accent_gradient_end": "#a7f3d0",
        "text": "#f0fdf4",
        "text_secondary": "#bbf7d0",
        "text_muted": "#86efac",
        "scroll_handle": "#1d4738",
        "scroll_handle_hover": "#2a5445",
        "is_light": False,
    },
    "cyberpunk": {
        "id": "cyberpunk",
        "name": "赛博暗金 (琥珀暖金)",
        "icon_color": "#f59e0b",
        "bg_main": "#120e06",
        "bg_panel": "#241a0b",
        "bg_tree": "#1c1409",
        "bg_card": "#2d200e",
        "bg_hover": "#422f14",
        "bg_selected": "#f59e0b",
        "border": "#422f14",
        "border_subtle": "#2e210e",
        "border_focus": "#fbbf24",
        "accent": "#fbbf24",
        "accent_hover": "#fcd34d",
        "accent_gradient_end": "#fde047",
        "text": "#fefce8",
        "text_secondary": "#fef08a",
        "text_muted": "#fde047",
        "scroll_handle": "#422f14",
        "scroll_handle_hover": "#5c411c",
        "is_light": False,
    },
    "light": {
        "id": "light",
        "name": "皓月晨曦 (纯净浅色)",
        "icon_color": "#2563eb",
        "bg_main": "#f8fafc",
        "bg_panel": "#ffffff",
        "bg_tree": "#f1f5f9",
        "bg_card": "#ffffff",
        "bg_hover": "#e2e8f0",
        "bg_selected": "#dbeafe",
        "border": "#cbd5e1",
        "border_subtle": "#e2e8f0",
        "border_focus": "#2563eb",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_gradient_end": "#60a5fa",
        "text": "#0f172a",
        "text_secondary": "#334155",
        "text_muted": "#64748b",
        "scroll_handle": "#94a3b8",
        "scroll_handle_hover": "#64748b",
        "is_light": True,
    }
}


def hex_to_rgba(hex_str, alpha=0.85):
    hex_clean = hex_str.lstrip('#')
    if len(hex_clean) == 6:
        r = int(hex_clean[0:2], 16)
        g = int(hex_clean[2:4], 16)
        b = int(hex_clean[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha:.2f})"
    return hex_str


def get_theme_stylesheet(theme_key=None, has_custom_bg=None):
    if theme_key is None:
        theme_key = config.get("theme", "dark")
    if theme_key not in THEMES:
        theme_key = "dark"
    t = THEMES[theme_key]

    if has_custom_bg is None:
        bg_p = config.get("custom_background_image", "")
        has_custom_bg = bool(bg_p and os.path.exists(bg_p))

    if has_custom_bg:
        bg_window = "transparent"
        bg_central = "transparent"
        bg_panel_css = hex_to_rgba(t["bg_panel"], 0.85)
        bg_tree_css = hex_to_rgba(t["bg_tree"], 0.78)
        bg_table_css = hex_to_rgba(t["bg_main"], 0.72)
        bg_header_css = hex_to_rgba(t["bg_tree"], 0.88)
        bg_card_css = hex_to_rgba(t["bg_card"], 0.85)
        bg_status_css = hex_to_rgba(t["bg_tree"], 0.85)
        bg_item_selected = hex_to_rgba(t["bg_selected"], 0.85)
    else:
        bg_window = t["bg_main"]
        bg_central = t["bg_main"]
        bg_panel_css = t["bg_panel"]
        bg_tree_css = t["bg_tree"]
        bg_table_css = t["bg_main"]
        bg_header_css = t["bg_tree"]
        bg_card_css = t["bg_card"]
        bg_status_css = t["bg_tree"]
        bg_item_selected = t["bg_selected"]

    font_family = '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    btn_text_hover = "#ffffff" if not t["is_light"] else "#0f172a"
    dialog_bg = t["bg_main"] if not has_custom_bg else hex_to_rgba(t["bg_main"], 0.95)

    return f"""
/* 全局基础设置 */
QMainWindow {{
    background-color: {bg_window};
    color: {t["text"]};
    font-family: {font_family};
    font-size: 13px;
}}

QDialog {{
    background-color: {dialog_bg};
    color: {t["text"]};
    font-family: {font_family};
    font-size: 13px;
}}

QLabel {{
    color: {t["text"]};
    background-color: transparent;
}}

QCheckBox, QRadioButton {{
    color: {t["text"]};
    background-color: transparent;
    spacing: 6px;
}}

QToolTip {{
    background-color: {t["bg_panel"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    padding: 4px 8px;
    border-radius: 4px;
}}

QWidget#centralWidget, QWidget#rightContainer, QSplitter {{
    background-color: {bg_central};
}}

/* 顶部主工具栏 */
QToolBar {{
    background-color: {bg_panel_css};
    border-bottom: 1px solid {t["border"]};
    padding: 6px 12px;
    spacing: 6px;
}}

QToolButton {{
    background-color: transparent;
    color: {t["text_secondary"]};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 500;
}}

QToolButton:hover {{
    background-color: {t["bg_hover"]};
    border-color: {t["border"]};
    color: {btn_text_hover};
}}

QToolButton:pressed {{
    background-color: {t["accent"]};
    color: #ffffff;
}}

/* 按钮通用控件 */
QPushButton {{
    background-color: {bg_card_css};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {t["bg_hover"]};
    border-color: {t["accent"]};
    color: {btn_text_hover};
}}

QPushButton:pressed {{
    background-color: {t["accent"]};
    color: #ffffff;
}}

QPushButton:disabled {{
    background-color: {t["bg_panel"]};
    color: {t["text_muted"]};
    border-color: {t["border_subtle"]};
}}

QPushButton.primary {{
    background-color: {t["accent"]};
    color: #ffffff;
    border: 1px solid {t["accent"]};
    font-weight: 600;
}}

QPushButton.primary:hover {{
    background-color: {t["accent_hover"]};
    border-color: {t["accent_hover"]};
}}

QPushButton.primary:pressed {{
    background-color: {t["accent"]};
}}

/* 文本与下拉输入 */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: {bg_card_css};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {t["accent"]};
    selection-color: #ffffff;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {t["border_focus"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

/* 左侧分类导航树 */
QTreeWidget {{
    background-color: {bg_tree_css};
    border-right: 1px solid {t["border"]};
    border-top: none;
    border-bottom: none;
    border-left: none;
    padding: 8px 6px;
    outline: none;
}}

QTreeWidget::item {{
    padding: 7px 10px;
    border-radius: 6px;
    margin: 2px 2px;
    color: {t["text_secondary"]};
    font-weight: 500;
}}

QTreeWidget::item:hover {{
    background-color: {t["bg_hover"]};
    color: {t["text"]};
}}

QTreeWidget::item:selected {{
    background-color: {bg_item_selected};
    color: {t["accent"]};
    font-weight: 600;
}}

/* 中央多任务表格 */
QTableWidget {{
    background-color: {bg_table_css};
    border: none;
    gridline-color: {t["border_subtle"]};
    selection-background-color: {bg_item_selected};
    selection-color: {t["text"]};
    outline: none;
}}

QTableWidget::item {{
    padding: 8px 6px;
    border-bottom: 1px solid {t["border_subtle"]};
    color: {t["text"]};
}}

QTableWidget::item:selected {{
    background-color: {bg_item_selected};
}}

QHeaderView::section {{
    background-color: {bg_header_css};
    color: {t["text_secondary"]};
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid {t["border"]};
    border-right: 1px solid {t["border_subtle"]};
    font-weight: 600;
    font-size: 12px;
}}

/* 进度条 */
QProgressBar {{
    border: 1px solid {t["border"]};
    border-radius: 4px;
    text-align: center;
    background-color: {bg_panel_css};
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
    min-height: 14px;
    max-height: 14px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t["accent"]}, stop:1 {t["accent_gradient_end"]});
    border-radius: 3px;
}}

/* 细致滚动条 */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {t["scroll_handle"]};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t["scroll_handle_hover"]};
}}

QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 8px;
}}

QScrollBar::handle:horizontal {{
    background: {t["scroll_handle"]};
    min-width: 24px;
    border-radius: 4px;
}}

/* 选项卡 TabWidget */
QTabWidget::pane {{
    border: 1px solid {t["border"]};
    border-radius: 6px;
    background-color: {bg_tree_css};
}}

QTabBar::tab {{
    background-color: {t["bg_panel"]};
    color: {t["text_muted"]};
    border: 1px solid {t["border"]};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 4px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {bg_card_css};
    color: {t["accent"]};
    font-weight: 600;
    border-color: {t["accent"]};
}}

/* 状态栏 */
QStatusBar {{
    background-color: {bg_status_css};
    color: {t["text_muted"]};
    border-top: 1px solid {t["border"]};
    font-size: 12px;
    padding: 3px 8px;
}}

/* 分组框 */
QGroupBox {{
    border: 1px solid {t["border"]};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
    color: {t["text"]};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {t["accent"]};
}}

/* 滑动条 Slider */
QSlider::groove:horizontal {{
    height: 6px;
    background: {t["border"]};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: {t["accent"]};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {t["accent"]};
    border: 2px solid #ffffff;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}}

/* 右键上下文菜单 */
QMenu {{
    background-color: {t["bg_panel"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 4px 0;
}}

QMenu::item {{
    padding: 6px 20px;
    color: {t["text"]};
}}

QMenu::item:selected {{
    background-color: {t["bg_hover"]};
    color: {btn_text_hover};
}}

QMenu::separator {{
    height: 1px;
    background-color: {t["border"]};
    margin: 4px 6px;
}}
"""


DARK_THEME = get_theme_stylesheet("dark", False)

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
        "bg_main": "#121316",
        "bg_panel": "#18191d",
        "bg_tree": "#16171b",
        "bg_card": "#1a1b20",
        "bg_hover": "#27292f",
        "bg_selected": "#22252c",
        "border": "#23252a",
        "border_subtle": "#1d1e23",
        "border_focus": "#3875f6",
        "accent": "#3875f6",
        "accent_hover": "#4f87ff",
        "accent_gradient_end": "#60a5fa",
        "text": "#e4e4e7",
        "text_secondary": "#a1a1aa",
        "text_muted": "#71717a",
        "scroll_handle": "#272a31",
        "scroll_handle_hover": "#3b3f49",
        "is_light": False,
    },
    "midnight": {
        "id": "midnight",
        "name": "暗夜星河 (极客紫夜)",
        "icon_color": "#a855f7",
        "bg_main": "#0d0b18",
        "bg_panel": "#151226",
        "bg_tree": "#120e20",
        "bg_card": "#1a152e",
        "bg_hover": "#261e42",
        "bg_selected": "#2e2452",
        "border": "#2a2245",
        "border_subtle": "#201a36",
        "border_focus": "#a855f7",
        "accent": "#a855f7",
        "accent_hover": "#c084fc",
        "accent_gradient_end": "#38bdf8",
        "text": "#f3e8ff",
        "text_secondary": "#c084fc",
        "text_muted": "#938ba9",
        "scroll_handle": "#2e2452",
        "scroll_handle_hover": "#433575",
        "is_light": False,
    },
    "emerald": {
        "id": "emerald",
        "name": "青黛碧玉 (翠绿护眼)",
        "icon_color": "#10b981",
        "bg_main": "#091410",
        "bg_panel": "#0f201a",
        "bg_tree": "#0c1b16",
        "bg_card": "#142821",
        "bg_hover": "#1d382e",
        "bg_selected": "#194235",
        "border": "#1c3d31",
        "border_subtle": "#142b23",
        "border_focus": "#10b981",
        "accent": "#10b981",
        "accent_hover": "#34d399",
        "accent_gradient_end": "#6ee7b7",
        "text": "#ecfdf5",
        "text_secondary": "#6ee7b7",
        "text_muted": "#678a7e",
        "scroll_handle": "#1c3d31",
        "scroll_handle_hover": "#2a5445",
        "is_light": False,
    },
    "cyberpunk": {
        "id": "cyberpunk",
        "name": "赛博暗金 (琥珀暖金)",
        "icon_color": "#f59e0b",
        "bg_main": "#12100d",
        "bg_panel": "#1c1813",
        "bg_tree": "#171410",
        "bg_card": "#241e17",
        "bg_hover": "#362c20",
        "bg_selected": "#3f3323",
        "border": "#332a1e",
        "border_subtle": "#241c14",
        "border_focus": "#f59e0b",
        "accent": "#f59e0b",
        "accent_hover": "#fbbf24",
        "accent_gradient_end": "#fde047",
        "text": "#fef3c7",
        "text_secondary": "#fcd34d",
        "text_muted": "#988367",
        "scroll_handle": "#332a1e",
        "scroll_handle_hover": "#4d3e2b",
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
        "bg_selected": "#e0e7ff",
        "border": "#e2e8f0",
        "border_subtle": "#cbd5e1",
        "border_focus": "#2563eb",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_gradient_end": "#60a5fa",
        "text": "#0f172a",
        "text_secondary": "#475569",
        "text_muted": "#94a3b8",
        "scroll_handle": "#cbd5e1",
        "scroll_handle_hover": "#94a3b8",
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

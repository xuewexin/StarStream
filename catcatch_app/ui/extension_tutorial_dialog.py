"""
StarStream Downloader - Extension Tutorial Dialog
星流媒体嗅探器在 Chrome / Edge 等浏览器中的安装配置与使用教学
完全支持动态路径自适应、手动选择插件位置与安全跳转地址引导
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QFrame,
    QApplication, QScrollArea, QWidget, QLineEdit,
    QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from catcatch_app.core.browser_helper import (
    find_extension_dir,
    get_extension_dir,
    set_custom_extension_dir,
    is_valid_extension_dir,
    open_browser_guide,
    open_extension_folder,
    copy_to_clipboard
)
from catcatch_app.ui.icons import get_icon, get_app_icon


class ExtensionTutorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("浏览器插件安装与使用教学 - 星流下载器")
        self.setWindowIcon(get_app_icon())
        self.setFixedWidth(660)
        self.setMinimumHeight(660)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._refresh_extension_path_display()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)

        # 1. 顶部说明横幅
        banner = QFrame()
        banner.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        b_layout = QVBoxLayout(banner)
        b_layout.setContentsMargins(6, 6, 6, 6)
        b_layout.setSpacing(6)

        title_lbl = QLabel("星流媒体嗅探器 (StarStream Sniffer) 浏览器安装指引")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #38bdf8;")
        b_layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "提示：现代 Chromium 浏览器（Chrome / Edge）出于安全策略，拦截外部直接运行 .crx 安装包。\n"
            "官方可靠且永久的安装方式为通过「开发者模式」加载文件夹。支持在任意电脑、任意目录动态加载，只需 3 步即可搞定！"
        )
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.5;")
        b_layout.addWidget(desc_lbl)
        layout.addWidget(banner)

        # 2. 步骤一：打开浏览器扩展管理中心 (处理 Chromium 内部页阻止)
        step1_box = QGroupBox("步骤 1：打开浏览器的扩展管理页")
        s1_layout = QVBoxLayout(step1_box)
        s1_layout.setSpacing(8)

        s1_desc = QLabel(
            "⚠️ 注意：Chromium 安全沙箱禁止任何外部程序直接强制跳转内部设置页。\n"
            "👉 点击下方按钮后，软件已自动为您复制扩展页地址，并在浏览器中打开引导页；请直接在浏览器顶部地址栏按【Ctrl + V】粘贴并回车即可瞬间直达！"
        )
        s1_desc.setStyleSheet("color: #facc15; font-size: 12px; line-height: 1.4; background-color: #1a1805; padding: 8px; border-radius: 4px; border: 1px solid #854d0e;")
        s1_layout.addWidget(s1_desc)

        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(8)

        btn_edge = QPushButton("🚀 打开 Edge 扩展页面")
        btn_edge.setIcon(get_icon("globe", "#ffffff", 16))
        btn_edge.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: 600; padding: 6px 12px;")
        btn_edge.clicked.connect(self._open_edge)
        btn_row1.addWidget(btn_edge)

        btn_chrome = QPushButton("🚀 打开 Chrome 扩展页面")
        btn_chrome.setIcon(get_icon("globe", "#ffffff", 16))
        btn_chrome.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: 600; padding: 6px 12px;")
        btn_chrome.clicked.connect(self._open_chrome)
        btn_row1.addWidget(btn_chrome)

        s1_layout.addLayout(btn_row1)

        copy_row = QHBoxLayout()
        copy_row.setSpacing(8)
        btn_cp_edge = QPushButton("📋 复制 edge://extensions 地址")
        btn_cp_edge.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 11px; padding: 4px 8px;")
        btn_cp_edge.clicked.connect(lambda: self._copy_text("edge://extensions", "已复制 Edge 扩展页地址: edge://extensions\n请在浏览器地址栏按 Ctrl+V 粘贴并回车！"))
        copy_row.addWidget(btn_cp_edge)

        btn_cp_chrome = QPushButton("📋 复制 chrome://extensions 地址")
        btn_cp_chrome.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 11px; padding: 4px 8px;")
        btn_cp_chrome.clicked.connect(lambda: self._copy_text("chrome://extensions", "已复制 Chrome 扩展页地址: chrome://extensions\n请在浏览器地址栏按 Ctrl+V 粘贴并回车！"))
        copy_row.addWidget(btn_cp_chrome)
        copy_row.addStretch()
        s1_layout.addLayout(copy_row)

        layout.addWidget(step1_box)

        # 3. 步骤二：开启「开发者模式」开关
        step2_box = QGroupBox("步骤 2：开启「开发者模式」开关")
        s2_layout = QVBoxLayout(step2_box)
        s2_layout.setSpacing(6)

        s2_tip = QLabel(
            "• 在打开的扩展管理页面【右上角】（或 Edge 左侧菜单下方），找到【开发者模式】(Developer mode) 开关并勾选开启。\n"
            "• 开启后，页面左上方才会出现“加载已解压的扩展程序”按钮。"
        )
        s2_tip.setStyleSheet("color: #38bdf8; font-size: 12px; line-height: 1.5; background-color: #0f172a; padding: 8px; border-radius: 4px;")
        s2_layout.addWidget(s2_tip)
        layout.addWidget(step2_box)

        # 4. 步骤三：选择插件文件夹 (动态自适应 + 自由浏览自选)
        step3_box = QGroupBox("步骤 3：选择本项目扩展文件夹 (动态自适应)")
        s3_layout = QVBoxLayout(step3_box)
        s3_layout.setSpacing(8)

        s3_desc = QLabel(
            "点击浏览器左上角的【加载已解压的扩展程序】按钮，在弹出的窗口中选择下方目录即可。\n"
            "提示：软件会全盘自适应寻找插件位置；若您将插件移到了其他位置，可点击「浏览选择其他路径」自定义指定。"
        )
        s3_desc.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.4;")
        s3_layout.addWidget(s3_desc)

        # 路径展示与状态卡片
        path_card = QFrame()
        path_card.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 8px;")
        p_card_layout = QVBoxLayout(path_card)
        p_card_layout.setContentsMargins(4, 4, 4, 4)
        p_card_layout.setSpacing(6)

        status_row = QHBoxLayout()
        self.lbl_path_status = QLabel("探测中...")
        self.lbl_path_status.setStyleSheet("font-size: 12px; font-weight: 600;")
        status_row.addWidget(self.lbl_path_status)
        status_row.addStretch()
        p_card_layout.addLayout(status_row)

        input_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet("background-color: #0b0f19; color: #a78bfa; font-family: Consolas; font-size: 12px; padding: 6px; border: 1px solid #334155; border-radius: 4px;")
        btn_browse = QPushButton("浏览选择其他路径...")
        btn_browse.setIcon(get_icon("folder", "#ffffff", 16))
        btn_browse.setStyleSheet("background-color: #475569; color: #ffffff; padding: 6px 12px; font-weight: 500;")
        btn_browse.clicked.connect(self._browse_custom_path)
        input_row.addWidget(self.path_edit, 1)
        input_row.addWidget(btn_browse)
        p_card_layout.addLayout(input_row)

        s3_layout.addWidget(path_card)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        btn_copy = QPushButton("📋 一键复制扩展目录绝对路径")
        btn_copy.setIcon(get_icon("copy", "#a1a1aa", 16))
        btn_copy.clicked.connect(self._copy_path)
        action_row.addWidget(btn_copy)

        btn_rescan = QPushButton("🔄 重新扫描全盘")
        btn_rescan.setIcon(get_icon("refresh", "#a1a1aa", 16))
        btn_rescan.clicked.connect(self._rescan_path)
        action_row.addWidget(btn_rescan)

        btn_folder = QPushButton("📁 在资源管理器中打开")
        btn_folder.setIcon(get_icon("folder", "#a1a1aa", 16))
        btn_folder.clicked.connect(self._open_folder)
        action_row.addWidget(btn_folder)

        s3_layout.addLayout(action_row)
        layout.addWidget(step3_box)

        # 5. 步骤四：网页视频嗅探与下载使用方式
        step4_box = QGroupBox("步骤 4：如何嗅探与高速下载")
        s4_layout = QVBoxLayout(step4_box)
        s4_layout.setSpacing(6)

        s4_desc = QLabel(
            "1. 播放视频：在任何视频网页（B站、各类影视网等）开始播放视频。\n"
            "2. 悬浮胶囊：视频播放器右上角会自动浮现【下载视频】天蓝色胶囊按钮。\n"
            "3. 一键下载：点击胶囊中的【推送到星流下载器】，客户端将自动识别为 M3U8 流或 MP4 直链极速下载，并自动转为标准 MP4 格式！"
        )
        s4_desc.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.5;")
        s4_layout.addWidget(s4_desc)
        layout.addWidget(step4_box)

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

        # 底部操作栏
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_close = QPushButton("我已学会，完成")
        btn_close.setProperty("class", "primary")
        btn_close.setStyleSheet("background-color: #3b82f6; color: #ffffff; font-weight: 600; padding: 6px 20px;")
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)
        main_layout.addLayout(bottom_row)

    def _refresh_extension_path_display(self):
        ext_p = get_extension_dir()
        self.path_edit.setText(ext_p)
        if is_valid_extension_dir(ext_p):
            self.lbl_path_status.setText("✓ 已在当前电脑成功定位到扩展目录 (包含 manifest.json)")
            self.lbl_path_status.setStyleSheet("color: #4ade80; font-size: 12px; font-weight: 600;")
        else:
            self.lbl_path_status.setText("⚠️ 未在默认位置检测到插件目录，请点击右侧「浏览选择」指定插件所在文件夹")
            self.lbl_path_status.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 600;")

    def _open_edge(self):
        copy_to_clipboard("edge://extensions")
        ok, msg = open_browser_guide("edge")
        ext_p = self.path_edit.text()
        QMessageBox.information(
            self, "已启动 Edge 安装指引",
            "【关键提示】\n"
            "现代 Chromium 安全沙箱禁止任何外部程序直接强制跳转 edge:// 内部页。\n\n"
            "✨ 软件已自动将【edge://extensions】复制到了您的剪贴板！\n\n"
            "👉 请在刚打开的浏览器中，直接在顶部地址栏按【Ctrl + V】粘贴并回车即可瞬间直达！\n"
            "👉 随后开启右上角「开发者模式」，点击「加载已解压的扩展程序」，选择下方目录即可：\n"
            f"{ext_p}"
        )

    def _open_chrome(self):
        copy_to_clipboard("chrome://extensions")
        ok, msg = open_browser_guide("chrome")
        ext_p = self.path_edit.text()
        QMessageBox.information(
            self, "已启动 Chrome 安装指引",
            "【关键提示】\n"
            "现代 Chromium 安全沙箱禁止任何外部程序直接强制跳转 chrome:// 内部页。\n\n"
            "✨ 软件已自动将【chrome://extensions】复制到了您的剪贴板！\n\n"
            "👉 请在刚打开的浏览器中，直接在顶部地址栏按【Ctrl + V】粘贴并回车即可瞬间直达！\n"
            "👉 随后开启右上角「开发者模式」，点击「加载已解压的扩展程序」，选择下方目录即可：\n"
            f"{ext_p}"
        )

    def _copy_text(self, text, info_msg):
        copy_to_clipboard(text)
        QMessageBox.information(self, "已复制", info_msg)

    def _copy_path(self):
        ext_p = self.path_edit.text()
        copy_to_clipboard(ext_p)
        QMessageBox.information(
            self, "已复制",
            f"扩展目录绝对路径已复制到剪贴板:\n{ext_p}\n\n"
            "在浏览器点击「加载已解压的扩展程序」时，在文件选择框地址栏直接按 Ctrl+V 粘贴回车即可秒选！"
        )

    def _browse_custom_path(self):
        init_dir = self.path_edit.text() or os.getcwd()
        d = QFileDialog.getExistingDirectory(self, "请选择星流媒体嗅探器扩展所在目录 (包含 manifest.json)", init_dir)
        if d:
            ok, res = set_custom_extension_dir(d)
            if ok:
                self.path_edit.setText(res)
                self._refresh_extension_path_display()
                copy_to_clipboard(res)
                QMessageBox.information(self, "设置成功", f"插件目录已成功指定并更新为:\n{res}\n\n已自动为您复制到剪贴板！")
            else:
                reply = QMessageBox.question(
                    self, "确认选择",
                    f"选择的文件夹中未检测到 manifest.json 扩展清单文件：\n{d}\n\n是否仍然强制将其设为插件目录？",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    set_custom_extension_dir(d)
                    self.path_edit.setText(d)
                    self._refresh_extension_path_display()

    def _rescan_path(self):
        new_p = find_extension_dir()
        self.path_edit.setText(new_p)
        self._refresh_extension_path_display()
        QMessageBox.information(self, "扫描完成", f"已重新动态探测插件目录：\n{new_p}")

    def _open_folder(self):
        p = self.path_edit.text()
        open_extension_folder(p)

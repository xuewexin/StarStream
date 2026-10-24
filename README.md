<div align="center">

<p align="center">
  <img src="docs/images/starstream_logo.png" width="128" height="128" alt="StarStream Logo">
</p>

# 🌟 星流媒体下载器 (StarStream Pro)

**全能网页音视频智能嗅探扩展 + IDM 工业级多线程下载客户端 + 内置 N_m3u8DL-RE 与 FFmpeg 核心**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/m3u8-sniffer?style=flat-square&color=blue&label=GitHub%20Release)](https://github.com/xuewexin/m3u8-sniffer/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d7.svg?style=flat-square&logo=windows)](#)
[![Python](https://img.shields.io/badge/Python-3.8%20~%203.13-3776ab.svg?style=flat-square&logo=python)](#)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5%20%7C%20Dark%20Slate-6366f1.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square)](#)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/m3u8-sniffer/releases/download/v2.0.0/StarStream.exe">
    <img src="https://img.shields.io/badge/⬇️%20官方桌面客户端-StarStream.exe%20(内置%20N_m3u8DL%20核心)-2563eb?style=for-the-badge&logo=windows&logoColor=white" alt="点击直接下载 StarStream.exe">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/m3u8-sniffer/releases/download/v2.0.0/StarStream_Browser_Extension_v2.0.1.zip">
    <img src="https://img.shields.io/badge/🧩%20单独下载浏览器嗅探插件-Extension.zip%20(仅%20140KB)-059669?style=for-the-badge&logo=googlechrome&logoColor=white" alt="单独下载浏览器嗅探插件">
  </a>
</p>

> [!IMPORTANT]
> ### 💡 黄金搭档使用说明：桌面软件必须搭配浏览器插件协同使用！
> - **🧩 浏览器嗅探插件（前端雷达）**：负责在您日常浏览网页、播放视频时，全自动深度抓取 M3U8、DASH (MPD)、MP4 等真实网络数据流，并在播放器右上角智能浮现【下载视频】操作胶囊；
> - **💻 桌面下载客户端（后端引擎）**：负责接收扩展推送的音视频任务，自动调度内置的 **N_m3u8DL-RE** 高性能引擎与 **FFmpeg** 核心，执行 24.7MB/s 工业级高并发分块下载与无损混流封装；
> - **二者协同配合（类似 IDM 软件与 IDM 浏览器扩展）**：缺一不可！初次使用请务必参考下方的 [浏览器插件导入教学](#-浏览器插件导入教学) 将扩展导入您的 Chrome/Edge 浏览器。

<p align="center">
  <a href="#-应用实机展示">实机展示</a> •
  <a href="#-软件版本与下载">版本下载</a> •
  <a href="#-核心特性">核心特性</a> •
  <a href="#-浏览器插件导入教学">插件教学</a> •
  <a href="#-代理网络配置说明">代理设置</a> •
  <a href="#-常见问题-faq">常见问题</a>
</p>

</div>

---

## 📸 应用实机展示

### 1. 桌面端主控中心 (沉浸式 Slate 灰蓝工业级 UI)
> 彻底告别粗糙符号与简陋界面，全状态监控一目了然：本地监听端口 `18910` 就绪、`FFmpeg` 就绪、`N_m3u8DL (RE)` 引擎就绪、代理模式（直连 / 系统 / 手动）一键切换。

<p align="center">
  <img src="docs/images/app_main_window.png" width="92%" alt="桌面端主控中心实机截图">
</p>

---

### 2. 极速并发多任务下载 (实测 24.70 MB/s 极速分段拉取)
> 多任务队列并发调度，支持毫秒级断点续传。实时呈现分块下载百分比、动态传输速率（实测峰值达 **24.70 MB/s**）与秒级剩余时间估算。

<p align="center">
  <img src="docs/images/app_download_active.png" width="92%" alt="多任务高并发下载实况">
</p>

---

### 3. 海外流媒体无感嗅探 (以 YouTube 为例)
> 访问各类流媒体平台播放视频时，播放器右上角无感浮现【下载视频】胶囊。自动解析视频画质（如 1280x720）、独立 AUDIO 音频流与播放时长，支持一键推送到桌面端或复制真实链接。

<p align="center">
  <img src="docs/images/web_capsule_youtube.png" width="92%" alt="YouTube 网页视频一键悬浮胶囊嗅探">
</p>

---

### 4. 国内主流视频网站智能嗅探与直推下载
> 播放网页视频时，智能捕获 1080P 高清规格与 MP4 格式，悬浮窗直观呈现视频参数，点击【推送到星流下载器】即刻自动唤醒客户端高速下载。

<p align="center">
  <img src="docs/images/web_capsule_bilibili.png" width="92%" alt="国内主流视频平台嗅探与直推">
</p>

---

## 📦 软件版本与下载 (Releases)

您可以通过以下两种方式轻松获取并使用星流媒体下载器：

| 下载方式 | 包含组件 | 适用场景 | 官方下载链接 |
|---|---|---|---|
| **⭐ 推荐：StarStream.exe 单文件客户端** | 内置完整 **N_m3u8DL-RE** + **FFmpeg** | 免安装任何运行环境，双击即可直接运行 | [👉 点击下载 StarStream.exe (55MB)](https://github.com/xuewexin/m3u8-sniffer/releases/download/v2.0.0/StarStream.exe)<br>*(备用镜像：[Raw 下载](https://github.com/xuewexin/m3u8-sniffer/raw/main/StarStream.exe))* |
| **🧩 必装搭档：浏览器嗅探插件独立包 (v2.0.1)** | 纯插件源码包 (仅 140KB)，含 MV3 嗅探/悬浮胶囊/弹窗 | 仅需安装或更新浏览器插件的场景，极速秒下 | [👉 点击下载 Extension.zip (140KB)](https://github.com/xuewexin/m3u8-sniffer/releases/download/v2.0.0/StarStream_Browser_Extension_v2.0.1.zip) |
| **StarStream_v2.0_Portable.zip 便携全套包** | 包含 exe 客户端 + 浏览器扩展离线源码 + 启动脚本 | 解压即用，包含客户端与插件全套套件 | [👉 点击下载 Portable.zip (55MB)](https://github.com/xuewexin/m3u8-sniffer/releases/download/v2.0.0/StarStream_v2.0_Portable.zip) |
| **GitHub Releases 官方发行版主页** | 查看所有历史版本、更新日志与资产列表 | 追溯所有更新与校验包 | [👉 访问 Releases 页面](https://github.com/xuewexin/m3u8-sniffer/releases) |

> 💡 **提示**：独立版 exe **已打包内置最新的 N_m3u8DL-RE 引擎与 FFmpeg**，完全开箱即用，无需单独下载或配置外部命令行工具。

---

## ⚡ 核心特性

| 功能模块 | 核心能力描述 |
|---|---|
| **全能资源嗅探** | 自动抓取 M3U8 (HLS)、MPD (DASH)、MP4、FLV、WebM、TS、MP3、AAC 等全部流媒体与直链；深度 Hook 网页 `HTMLMediaElement.play`、`Blob`、`MediaSource`、`URL.createObjectURL` 与 `fetch/XHR` |
| **智能悬浮胶囊** | 网页视频播放器内原生注入天蓝色悬浮操作胶囊，自动识别分集、清晰度规格（4K/1080P/720P）、时长与音轨分离流，一键投送客户端 |
| **弹窗内置播放器** | 扩展弹窗内置轻量 `hls.min.js` 播放引擎，支持在扩展弹窗中实时预览 M3U8 流媒体，核对画面音画无误后再发起下载 |
| **双下载引擎体系** | **流媒体引擎**：调度最新 [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) 高性能引擎，自动解析音视频混流并分段拉取；<br>**直链引擎**：原生 Python 多线程 Range 分块高并发下载 |
| **媒体格式自动处理** | 下载完成后自动调用内置 FFmpeg 进行无损转封装，生成通用 MP4 格式并注入 `faststart` 标记，确保任意播放器秒开起播 |
| **多节点代理网络池** | 全面支持 **直连**、**跟随 Windows 系统代理**、**手动多代理池**（兼容 Clash 7890、v2rayN 10808/10809/3080 及各类 HTTP/SOCKS5 本地端口代理），提供 TCP 端口探活与外网延迟测速 |
| **自适应路径识别** | 软件全动态识别扩展源码所在的绝对路径，自动适配不同用户的电脑磁盘环境，杜绝死路径报错 |
| **磁盘缓存深度清理** | 内置磁盘清理向导，一键扫描并粉碎下载中断残留的 `.tmp`、`.part` 分片碎片，安全释放硬盘空间 |

---

## 🧩 浏览器插件导入教学

> ⚠️ **重要提示**：现代 Chromium 浏览器（Microsoft Edge / Google Chrome / Brave）出于安全防护机制，已拦截外部直接双击安装 `.crx` 安装包（会提示“无效的程序包”）。**官方唯一长期稳定、永久生效的导入方式是通过「开发者模式」加载文件夹**，只需 3 步即可轻松完成！

### 第一步：打开浏览器的扩展管理页
- **Edge 浏览器**：在地址栏输入 `edge://extensions` 并回车
- **Chrome 浏览器**：在地址栏输入 `chrome://extensions` 并回车

> 💡 **小贴士**：在星流客户端中点击「打开扩展页面」时，软件会**自动将扩展地址复制到剪贴板**，您只需在浏览器顶部地址栏按 <kbd>Ctrl</kbd> + <kbd>V</kbd> 粘贴并回车即可直达！

---

### 第二步：开启「开发者模式」
- 在扩展管理页面的**右上角**（或 Edge 页面左侧菜单栏底部），找到 **【开发者模式】(Developer mode)** 开关，点击开启。
- 开启后，页面左上方将出现 **【加载已解压的扩展程序】** 按钮。

---

### 第三步：选择扩展源码目录
1. 点击左上角的 **【加载已解压的扩展程序】** 按钮。
2. 在弹出的文件选择器中，定位并选中 **`m3u8-sniffer-extension`** 文件夹：
   - 若您单独下载了 [插件独立包 Extension.zip](https://github.com/xuewexin/m3u8-sniffer/releases/download/v2.0.0/StarStream_Browser_Extension_v2.0.1.zip)，将其解压后直接选中解压得到的文件夹即可；
   - 若您使用的是便携全套包或克隆了仓库，直接选中根目录下的 `m3u8-sniffer-extension` 文件夹（您亦可在星流客户端设置中一键复制当前电脑上的准确路径）。
3. 点击「选择文件夹」，插件即刻导入成功！
4. 点击浏览器右上角的拼图图标 🧩，将 **「星流媒体嗅探器」** 固定到工具栏即可开始使用。

---

## 🌐 代理网络配置说明

星流媒体下载器针对国内国际网络环境进行了专门优化，支持以下三种代理模式：

1. **直接连接 (Direct)**：不使用任何网络代理，直接请求目标服务器。流媒体引擎自动禁用系统默认代理，保障国内高速源不走绕路。
2. **跟随系统代理 (System)**：全自动捕获 Windows 当前开启的全局或系统代理端口，无需手动配置。
3. **手动多节点代理池 (Manual)**：
   - 适配本地客户端（如 Clash 监听 `127.0.0.1:7890`、v2rayN 监听 `127.0.0.1:10809` 或 SOCKS5 `127.0.0.1:10808` / `127.0.0.1:3080`）。
   - **智能容错与补全**：若直接输入 `127.0.0.1:7890`，系统将自动补全协议并兼容 HTTP 与 SOCKS5。
   - **TCP 探活与诊断**：点击「测试」按钮时，系统首先探测本地端口是否处于监听状态；若客户端未开启，将清晰给出排查提示，避免盲目排错。

---

## 🚀 开发者运行方式 (源码启动)

如果您希望在 Python 环境中调试或二次开发：

```bash
# 1. 克隆代码仓库
git clone https://github.com/xuewexin/m3u8-sniffer.git
cd m3u8-sniffer

# 2. 安装项目依赖
pip install -r requirements.txt

# 3. 运行主程序
python run_app.py

# 或在 Windows 下双击运行：
启动星流下载器.bat
```

---

## 📁 目录结构

```
StarStream-Pro/
├── StarStream.exe              # [官方推荐] 单文件独立可执行程序 (内置全部引擎)
├── run_app.py                  # Python 桌面客户端入口
├── start.bat                   # 跨平台标准启动批处理
├── 启动星流下载器.bat           # Windows 中文快捷启动脚本
├── requirements.txt            # Python 核心依赖清单
├── README.md                   # 官方详细图文说明文档
│
├── catcatch_app/               # 桌面客户端核心源代码
│   ├── main.py                 # 客户端主界面逻辑与生命周期
│   ├── core/                   # 核心服务 (多线程下载/代理池/FFmpeg引擎/本地HTTP服务)
│   ├── resources/              # 官方 Logo 图标与本地交互 HTML 引导
│   └── ui/                     # 现代化 PyQt5 界面交互组件与矢量 SVG 资源
│
├── m3u8-sniffer-extension/     # 浏览器 MV3 网页嗅探扩展源码
│   ├── manifest.json           # 扩展配置清单
│   ├── background.js           # 跨域拦截与数据总线
│   ├── content_script.js       # 网页 DOM 悬浮胶囊交互层
│   └── popup/                  # 扩展交互弹窗与内置 HLS 播放器
│
└── docs/images/                # 项目界面高清展示截图与官方 Logo
```

---

## ❓ 常见问题 (FAQ)

<details>
<summary><b>1. 下载的 exe 安装包里面包含 N_m3u8DL-RE 引擎吗？</b></summary>
<p>
<b>包含！完全内置，免外部配置。</b><br>
本项目的独立发行版 <code>StarStream.exe</code> 已<b>完整内置最新的 N_m3u8DL-RE 高性能引擎与 FFmpeg 核心</b>。下载后双击即可直接使用，无需任何额外的命令行配置！<br>
若使用 Python 源码运行，客户端也会全自动全盘搜寻；若未检测到，状态栏会提供醒目的一键获取通道与全盘重探按钮。
</p>
</details>

<details>
<summary><b>2. 为什么扩展不打包成 .crx 文件直接拖动安装？</b></summary>
<p>
现代 Chromium 浏览器（Chrome / Edge / Brave）出于安全策略，全面禁止通过拖拽方式直接安装未上架 Google Web Store 的 <code>.crx</code> 包，并会强制报“程序包无效”或自动禁用。通过「开发者模式」加载源码文件夹是 Chromium 官方唯一保证稳定且长期生效的标准方案。
</p>
</details>

<details>
<summary><b>3. 下载后的视频会自动转为 MP4 格式吗？</b></summary>
<p>
是的！星流媒体下载器默认开启【自动转为标准 MP4 格式】，内置集成 FFmpeg 进行无损封装合并，并自动写入 <code>faststart</code> 元数据标记，确保在所有主流播放器与手机移动端均可秒开起播。
</p>
</details>

<details>
<summary><b>4. 本地代理端口测试失败如何解决？</b></summary>
<p>
请先确认您的代理软件（如 Clash、v2rayN）已启动且开启了“允许局域网连接”或本地监听。星流下载器具备自动端口诊断功能，可分别测试 TCP 端口监听与 HTTP/SOCKS5 外网通道。输入代理端口时支持简写（如 <code>127.0.0.1:7890</code>），系统将自动适配。
</p>
</details>

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 许可协议开源。<br>
致谢：[N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) 与 [FFmpeg](https://ffmpeg.org/) 为音视频流媒体处理提供的卓越技术支持。

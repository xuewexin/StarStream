<div align="center">

<p align="center">
  <b>Language / 多语言:</b><br>
  <a href="README.md">简体中文</a> •
  <a href="README_zh-TW.md">繁體中文</a> •
  <a href="README_en.md">English</a> •
  <a href="README_ja.md">日本語</a> •
  <a href="README_ko.md">한국어</a> •
  <a href="README_fr.md">Français</a> •
  <a href="README_de.md">Deutsch</a> •
  <a href="README_es.md">Español</a> •
  <a href="README_ru.md">Русский</a> •
  <a href="README_pt.md">Português</a>
</p>


<p align="center">
  <img src="docs/images/starstream_logo.png" width="128" height="128" alt="StarStream Logo">
</p>

# 🌟 星流媒体下载器 (StarStream Pro)

**全能网页音视频智能嗅探扩展 + IDM 工业级多线程下载客户端 + 内置 N_m3u8DL-RE 与 FFmpeg 核心**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/StarStream?style=flat-square&color=blue&label=GitHub%20Release)](https://github.com/xuewexin/StarStream/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d7.svg?style=flat-square&logo=windows)](#)
[![Python](https://img.shields.io/badge/Python-3.8%20~%203.13-3776ab.svg?style=flat-square&logo=python)](#)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5%20%7C%20Dark%20Slate-6366f1.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square)](#)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.0/StarStream_v3.2.0_Portable.zip">
    <img src="https://img.shields.io/badge/⭐%20便携全套包-StarStream_v3.2.0_Portable.zip%20(内置%20FFmpeg%20与%20N_m3u8DL)-2563eb?style=for-the-badge&logo=windows&logoColor=white" alt="下载 Portable 便携包">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.0/StarStream.exe">
    <img src="https://img.shields.io/badge/🚀%20独立单文件-StarStream.exe%20(自动扫描前置引擎)-059669?style=for-the-badge&logo=windows&logoColor=white" alt="直接下载 StarStream.exe">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.0/StarStream_Browser_Extension_v3.2.0.zip">
    <img src="https://img.shields.io/badge/🧩%20浏览器嗅探扩展-Extension_v3.2.0.zip%20(仅%20165KB)-7c3aed?style=for-the-badge&logo=googlechrome&logoColor=white" alt="单独下载浏览器嗅探插件">
  </a>
  &nbsp;&nbsp;
  <a href="#-同类开源项目横向对比与选型指南-comparison--alternatives">
    <img src="https://img.shields.io/badge/🔥%20替代推荐-猫抓%20%7C%20SimpleG%20%7C%20yt--dlp-10b981?style=for-the-badge" alt="同类开源项目横向对比与选型指南">
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
  <a href="#-常见问题-faq">常见问题</a> •
  <a href="#-免责声明-disclaimer">免责声明</a>
</p>

</div>

---

## 📸 应用实机展示

### 1. 桌面端主控中心 (沉浸式 Dark Slate 灰蓝工业级 UI)
> 全矢量高精度图标，全状态监控一目了然：本地监听端口 `18910` 就绪、`FFmpeg` 就绪、`N_m3u8DL (RE)` 引擎就绪、网络代理实时状态指示与一键极速切换。

<p align="center">
  <img src="docs/images/app_main_window.png" width="92%" alt="桌面端主控中心实机截图">
</p>

---

### 2. 新建下载任务与深度逆向解析 (智能代理与独立并发配置)
> 支持全网主流视频分享口令与链接一键粘贴解析。针对单个任务独立配置并发线程数（4~32 线程）、专用保存目录与网络代理模式（直连 / 本地代理 / 跟随全局）。

<p align="center">
  <img src="docs/images/app_new_task.png" width="82%" alt="新建任务与代理配置对话框">
</p>

---

### 3. FFmpeg 多媒体专业处理工具箱 (格式转换与音视频后处理)
> 开箱即用内置专业级媒体工具箱：支持单文件/批量格式转换（MP4/MKV/TS/MOV）、音视频混流、无损音频提取、视频无损剪切与媒体元数据探测。

<p align="center">
  <img src="docs/images/app_ffmpeg_toolbox.png" width="82%" alt="FFmpeg 专业处理工具箱">
</p>

---

### 4. 海外流媒体无感嗅探 (以 YouTube 为例)
> 访问各类海外流媒体播放视频时，播放器右上角无感浮现【下载视频】胶囊。自动捕获真实分辨率、音频流与播放时长，自动对齐浏览器代理并支持一键推送到桌面端。

<p align="center">
  <img src="docs/images/web_capsule_youtube.png" width="82%" alt="YouTube 网页视频一键悬浮胶囊嗅探">
</p>

---

### 5. 主流网页视频智能嗅探与直推下载 (自动对齐浏览器代理)
> 在任意网页播放视频时，播放器右上角无感浮现下载胶囊。直观呈现真实分辨率、时长与格式，一键对齐浏览器代理并推送至桌面客户端高速下载。

<p align="center">
  <img src="docs/images/web_capsule_bilibili.png" width="58%" alt="网页视频智能悬浮嗅探卡片">
</p>

---

### 6. 桌面任务监控与便捷工具中心
> 点击悬浮球即刻展开监控面板：实时查看正在进行的下载任务进度、全局下载速率，并一键呼出格式转换、FFmpeg 工具箱与短视频提取工作台。

<p align="center">
  <img src="docs/images/app_floating_panel.png" width="68%" alt="桌面任务监控与工具中心">
</p>

---

### 7. 灵动微型太空星球悬浮球 (随时掌握任务动态)
> 极具科技感的迷你太空星球悬浮球，支持桌面任意拖拽、智能贴边吸附与多级缩放，实时掌握就绪任务数与全局传输动态。

<p align="center">
  <img src="docs/images/app_floating_widget.png" width="28%" alt="桌面迷你悬浮监控挂件">
</p>


## 📦 软件版本与下载 (Releases)

您可以通过以下方式轻松获取并使用星流媒体下载器最新发布版本：

| 下载方式 | 包含组件 | 适用场景 | 官方下载链接 |
|---|---|---|---|
| **⭐ 推荐：StarStream_v3.2.0_Portable.zip 全套便携包** | 内置完整 **StarStream.exe** + **N_m3u8DL-RE** + **FFmpeg** + 浏览器插件源码 | **强烈推荐未安装 FFmpeg / N_m3u8DL 的用户**，解压即用，全套核心内置 | [👉 点击下载 Portable 便携包](https://github.com/xuewexin/StarStream/releases/download/v3.2.0/StarStream_v3.2.0_Portable.zip) |
| **🚀 独立单文件版：StarStream.exe (77.5MB)** | 最新编译独立单文件可执行程序 (内置全部依赖) | **适合本地已有 FFmpeg 或 N_m3u8DL 的用户**，自动全盘扫描识别依赖；**请放入独立空白文件夹运行** | [👉 点击直接下载 StarStream.exe](https://github.com/xuewexin/StarStream/releases/download/v3.2.0/StarStream.exe) |
| **🧩 必装搭档：浏览器嗅探插件独立包 (v3.2.0)** | 纯插件源码包 (仅 165KB)，含 MV3 嗅探/自动匹配浏览器代理/画质时长智能排序 | 嗅探网页视频、当前页面纯净展示、按时长画质降序置顶 | [👉 点击下载 Extension.zip (165KB)](https://github.com/xuewexin/StarStream/releases/download/v3.2.0/StarStream_Browser_Extension_v3.2.0.zip) |
| **GitHub Releases 官方发行版主页** | 查看所有发布版本、更新日志与资产列表 | 追溯所有更新与校验包 | [👉 访问 Releases 页面](https://github.com/xuewexin/StarStream/releases) |

> 💡 **下载与使用重要建议 (必读指南)**：
> 1. **未安装 FFmpeg 与 N_m3u8DL 的用户**：
>    👉 **强烈建议直接下载【便携完整包 (`StarStream_v3.2.0_Portable.zip`)】**！便携包内已预置并配置好了全部必需的 `ffmpeg.exe` 与 `N_m3u8DL-RE.exe` 核心引擎，解压即可直接使用，无需任何环境配置。
> 2. **本地已有 FFmpeg 或 N_m3u8DL 的用户**：
>    👉 **可以直接下载单文件【独立主程序 (`StarStream.exe`)】**！星流在首次启动时会自动全盘扫描系统环境变量（`PATH`）与常见目录，智能识别并自动挂载这两个前置依赖工具，无需重复配置。
> 3. **⚠️ 运行注意事项 (强烈建议)**：
>    若您下载的是单文件独立版 `StarStream.exe`，**请务必将该 exe 文件放置在一个全新的空文件夹（如 `D:\StarStream\`）中运行**！软件在运行过程中会在 exe 所在目录下自动生成本地数据库、配置文件、日志记录及临时工作目录。将 exe 放入独立的干净文件夹中可防止桌面或下载目录混乱，便于日常管理与清理。

---

## ⚔️ 同类开源项目横向对比与选型指南 (Comparison & Alternatives)

很多用户在寻找音视频下载工具时常有疑问：**“星流 (StarStream) 与「猫抓 (CatCatch)」、「SimpleG」、「N_m3u8DL-RE 命令行」、「yt-dlp」或「Video DownloadHelper」相比有什么区别？我该如何选择？”**

下表为您直观梳理核心能力对比：

| 功能维度 / 核心特性 | 🌟 星流 (StarStream Pro) | 🐱 猫抓 (Cat-Catch) | 🛠️ SimpleG (N_m3u8DL原版GUI) | ⚡ yt-dlp / CLI 工具 | 🦊 Video DownloadHelper |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **产品形态** | **桌面客户端 + 浏览器扩展双模极速联动** | 纯浏览器扩展插件 | 传统单体 Windows 客户端 | 纯命令行控制台程序 | 浏览器扩展 + 付费配套应用 |
| **底层下载引擎** | **原生内置 N_m3u8DL-RE + FFmpeg 工业级引擎** | 浏览器内置 Blob / Fetch 内存拉取 | 老旧 N_m3u8DL-CLI v3.0.2 内核 | yt-dlp Python 脚本引擎 | 扩展自带下载 / 需装后台服务 |
| **高并发多线程下载** | **✅ 支持 (4 ~ 32 线程极速并发拉取，实测 24MB/s+)** | ❌ 仅单线程/低并发 (大文件与长视频极慢) | ⚠️ 基础多线程支持 | 需手动配置复杂命令行参数 | 需付费购买高级许可证解锁 |
| **音视频分离流混流** | **✅ 自动混流并秒级封装为通用 MP4 (faststart)** | ❌ 无法自动处理音轨/画面分离流 | ⚠️ 基础转码合并 | 支持命令行调用 FFmpeg 合并 | ❌ 免费版限制合并时长/加水印 |
| **浏览器代理自动对齐** | **✅ 深度对齐浏览器出口 IP (从根源彻底杜绝 403)** | 仅走浏览器当前代理 | ❌ 无法感知浏览器当前代理状态 | 需手动查询并配置 `--proxy` 参数 | ❌ 不支持智能代理对齐 |
| **网页播放器内嵌操作** | **✅ 视频右上角原生注入天蓝色下载操作胶囊** | ❌ 必须每次点击右上角扩展栏弹窗 | ❌ 无浏览器交互，需手动复制粘贴 URL | ❌ 纯黑窗口命令行输入 | 需点击浏览器右上角插件图标 |
| **桌面迷你悬浮监控挂件** | **✅ 炫酷星球呼吸悬浮挂件 + 任务监控微面板** | ❌ 无桌面端挂件 | ❌ 无桌面挂件 | ❌ 无图形界面挂件 | ❌ 无桌面端挂件 |
| **全网主流平台一键解析** | **✅ 内置短视频解析工作台 (B站4K/抖音/快手无水印)** | 需依赖第三方规则脚本 | ❌ 无逆向解析能力 | 依赖提取器更新维护 | ❌ 不支持国内短视频去水印 |
| **全球多语言支持** | **✅ 完整适配 10 国主流语言与专属 README 文档** | 仅中文 / 英文 | 仅中文 | 英文控制台输出 | 多语言支持 |
| **开源免费与商用限制** | **✅ 100% 永久开源免费 (基于 MIT 协议)** | 开源免费 | 开源免费 | 开源免费 (Unlicense) | 商业软件 (限制功能/诱导付费) |

### 🎯 针对不同使用习惯用户的选型建议：
- **如果您是「猫抓 (CatCatch)」忠实用户**：猫抓是一款出色的嗅探扩展，但在下载数十个 GB 的长视频或加密 HLS 流时，浏览器内存占用巨大且极易断流失败。星流在继承强大嗅探能力的同时，将下载交给工业级桌面引擎并发拉取，是**猫抓的终极性能加速替代方案**！
- **如果您是「SimpleG」老用户**：SimpleG 是一款陪伴大家多年的经典 N_m3u8DL GUI，但因久未维护已无法适配最新的动态防盗链与多节点代理。星流是**SimpleG 的 2026 现代化重构旗舰版**，界面彻底升级为沉浸式 Dark Slate 灰蓝矢量主题，支持小窗响应式折叠与最新 N_m3u8DL-RE 引擎！
- **如果您是「yt-dlp / 命令行」极客用户**：无需每次在终端中繁琐拼接 `--referer`、`--user-agent`、`--cookie` 与代理端口，星流浏览器扩展全自动捕获全部鉴权参数，一键投送客户端或一键复制完整命令行，极客与便捷兼得！
- **如果您是「Video DownloadHelper」用户**：彻底告别其必须安装额外付费 Companion App、免费版强制打水印、限制下载并发时长的困扰，星流全功能完全开放，开箱即用。

---

## ⚡ 核心特性

| 功能模块 | 核心能力描述 |
|---|---|
| **全能资源嗅探** | 自动抓取 M3U8 (HLS)、MPD (DASH)、MP4、FLV、WebM、TS、MP3、AAC 等全部流媒体与直链；深度 Hook 网页 `HTMLMediaElement.play`、`Blob`、`MediaSource`、`URL.createObjectURL` 与 `fetch/XHR` |
| **智能悬浮胶囊** | 网页视频播放器内原生注入天蓝色悬浮操作胶囊，自动识别分集、清晰度规格（4K/1080P/720P）、时长与音轨分离流，一键投送客户端 |
| **弹窗内置播放器** | 扩展弹窗内置轻量 `hls.min.js` 播放引擎，支持在扩展弹窗中实时预览 M3U8 流媒体，核对画面音画无误后再发起下载 |
| **双下载引擎体系** | **流媒体引擎**：调度最新 [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) 高性能引擎，自动解析音视频混流并分段拉取；<br>**直链引擎**：原生 Python 多线程 Range 分块高并发下载 |
| **单视频专属配置** | 插件内每个视频卡片均支持展开专属配置面板，可针对特定视频单独指定**保存目录**、**并发线程数**（4/8/16/32）与**下载代理** |
| **浏览器代理自动对齐** | 插件自动检测当前浏览器实际代理地址，实现**下载网络出口与视频播放网页出口完全对齐**，彻底杜绝防盗链 IP 不一致导致的 HTTP 403 鉴权失败 |
| **脱离客户端独立运行** | 插件可与 `N_m3u8DL-RE` 直接搭配使用！一键生成并复制完整命令行，免启动桌面 exe 客户端亦可直接在终端中极速下载 |
| **批量格式转换中心** | 全新内置批量多媒体转换中心，支持多文件与整目录批量扫描，提供智能极速无损拷贝 (-c copy，秒级无损封装转码)、H.264/H.265/高品质音频提取等预设方案，支持多任务排队顺序转换、单文件与总体双重进度条 |
| **完成与失败弹窗提醒** | 任务下载完成或失败时，屏幕右下角自动弹出沉浸式浮窗提醒，支持直接点击【立即播放】、【打开目录】或失败时一键呼出【详细诊断与日志】 |
| **媒体格式自动处理** | 下载完成后自动调用内置 FFmpeg 进行无损转封装，生成通用 MP4 格式并注入 `faststart` 标记，确保任意播放器秒开起播 |
| **多节点代理网络池** | 全面支持 **直连**、**跟随 Windows 系统代理**、**手动多代理池**（兼容 Clash 7890、v2rayN 10808/10809/3080 及各类 HTTP/SOCKS5 本地端口代理），提供 TCP 端口探活与外网延迟测速 |
| **智能错误诊断与日志** | 遇到下载失败时自动记录错误日志至 `Logs/download_errors.log`，深度智能诊断失败根因（HTTP 403 防盗链/鉴权过期、401 未授权、404 不存在、AES-128 解密失败、代理端口未开启、DNS 解析失败、FFmpeg 合并异常等），提供清晰的排查建议与一键日志导出 |
| **自适应路径识别** | 软件全动态识别扩展源码所在的绝对路径，自动适配不同用户的电脑磁盘环境，杜绝死路径报错 |
| **磁盘缓存深度清理** | 内置磁盘清理向导，一键扫描并粉碎下载中断残留的 `.tmp`、`.part` 分片碎片，安全释放硬盘空间 |

---

## 💡 深度进阶：插件与 N_m3u8DL (mu3e) 独立搭配使用

星流媒体嗅探器不仅能与 StarStream 桌面客户端无缝协同，**还能直接与 N_m3u8DL-RE / N_m3u8DL-CLI (mu3e) 命令行工具完美脱离客户端独立搭配使用**！

### 场景与优势：
1. **无需启动客户端**：若您偏好命令行极客风格，或者在轻量化运行环境中，无需启动桌面 exe 客户端。
2. **一键生成并复制命令**：
   - 网页播放视频后，打开插件弹窗；
   - 点击任意视频卡片上的 **【复制命令】** 按钮（或展开【⚙️ 配置】点击【📋 复制 N_m3u8DL-RE 完整运行命令】）；
   - 扩展已自动为您拼装好全部关键参数：包含防盗链 `Referer` 头、`User-Agent`、自选保存名称、并发线程数、`-M format=mp4` 自动转封装以及自选的浏览器代理参数！
3. **极速运行**：直接在任意 CMD 或 PowerShell 窗口按 <kbd>Ctrl</kbd> + <kbd>V</kbd> 粘贴并回车，N_m3u8DL-RE 即刻全速开始下载与合并！

---

## 🎯 单视频独立配置与三级优先级机制 (Priority Rules)

为了满足专业用户对不同视频下载策略的精细化控制，星流构建了完备的**配置优先级覆盖机制**：

```mermaid
flowchart TD
    A["开始视频下载任务"] --> B{"插件中该视频是否<br>自定义了配置?"}
    B -- "是 (填写的目录/线程/代理)" --> C["🥇 采用插件单视频专属配置<br>(最高优先级)"]
    B -- "否 (留空或选择默认)" --> D{"桌面客户端是否运行<br>且配置了全局设置?"}
    D -- "是" --> E["🥈 采用客户端全局设置<br>(StarStream 设置面板)"]
    D -- "否 (独立命令行下载)" --> F["🥉 采用下载引擎默认配置<br>(默认保存目录 / 16线程 / 直连)"]
    C --> G["执行下载引擎"]
    E --> G
    F --> G
```

### 1. 🥇 最高优先级：插件单视频专属配置
- 点击插件卡片中的 **【⚙️ 配置】** 展开面板：
  - **📁 保存目录**：支持为当前视频指定专有存放路径（如 `D:\Movies\Anime`）；
  - **⚡ 并发线程**：自选 4 / 8 / 16 / 32 线程（对严格防爬的站点可降至 4 线程，普通站点拉满 32 线程）；
  - **🌐 下载代理**：可选“🎯 自动匹配浏览器代理”、“⚡ 直连”、“Clash 7890”、“v2rayN 10808”或自定义特定代理。

### 2. 🥈 次高优先级：桌面客户端全局设置
- 若插件中配置项留空或选择“跟随客户端设置”，系统自动读取桌面端【设置】面板中的全局配置（保存目录、默认线程数、代理模式）。

### 3. 🥉 默认兜底级：引擎标准默认配置
- 若未启动客户端且通过插件导出的命令行直接执行，自动回退到引擎标准配置（保存至当前 `Downloads` 目录、16 线程、直连）。

---

## 🌐 浏览器代理自动检测与对齐功能

### 为什么需要让下载环境与浏览器处于同一代理？
* 许多海外流媒体平台（如 YouTube、X/Twitter 等）以及部分国内限制版权流媒体，在网页端播放时使用的是浏览器专属的代理通道。
* 视频服务器下发给网页的 M3U8 切片清单往往包含与**当前访问 IP 强绑定的防盗链 Token 鉴权凭证**。
* **如果桌面下载器使用直连、或与浏览器走不同的代理出口 IP，就会触发目标站点的防盗链风控，导致 HTTP 403 权限被拒绝或分片拉取失败！**

### 自动对齐工作原理：
1. **智能嗅探当前代理**：插件内置 `chrome.proxy` 状态分析模块，自动检测当前浏览器生效的代理模式（无论是 Clash、v2rayN、SwitchyOmega 分流还是系统代理）。
2. **下载环境无缝同源**：下载时选择 **【🎯 自动匹配浏览器代理】**（默认推荐），插件将提取出的准确代理通道传递给下载引擎，确保**下载请求所使用的网络节点与网页播放时完全一致**，从根源上彻底解决 403 防盗链与鉴权失效难题！

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
   - 若您单独下载了 [插件独立包 Extension.zip](https://github.com/xuewexin/StarStream/releases/download/v2.2.0/StarStream_Browser_Extension_v2.2.0.zip)，将其解压后直接选中解压得到的文件夹即可；
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
git clone https://github.com/xuewexin/StarStream.git
cd StarStream

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

<details>
<summary><b>5. 我可以脱离桌面客户端，只用浏览器插件和 N_m3u8DL-RE 命令行直接下载吗？</b></summary>
<p>
<b>完全可以！</b><br>
嗅探到流媒体后，在插件弹窗中点击【复制命令】，插件会自动提取防盗链 <code>Referer</code>、<code>User-Agent</code>、清晰度、自选线程与自选代理，组合成完整的 <code>N_m3u8DL-RE "URL" ...</code> 命令行。无需启动 exe 桌面客户端，直接在任意终端粘贴回车即可极速下载并混流！
</p>
</details>

<details>
<summary><b>6. 为什么部分视频下载会报 HTTP 403 错误？如何使用“自动匹配浏览器代理”解决？</b></summary>
<p>
很多视频站点（特别是海外平台或带严格鉴权的防盗链站点）会将分片访问权限与<b>请求网页时的客户端出口 IP 强绑定</b>。如果浏览器使用了代理，而桌面下载器走直连或使用了不同出口 IP，就会被服务器安全策略判定为跨 IP 非法盗链，直接返回 403 Forbidden！<br>
<b>解决方案</b>：在插件单个视频下载配置中，将【下载代理】选择为<b>「🎯 自动匹配浏览器代理」</b>（默认），下载器会自动与浏览器对齐使用同一代理端口与出口 IP，从而彻底解除防盗链与鉴权限制。
</p>
</details>

---

## ⚖️ 免责声明 (Disclaimer)

在使用**星流媒体下载器 (StarStream Pro)** 及配套浏览器嗅探扩展前，请您务必仔细阅读并理解本声明：

1. **技术研究与个人学习**：本项目属于开源个人技术探索，旨在研究浏览器网络底层拦截机制、流媒体协议（HLS / DASH）解析技术与多线程分块下载算法，仅供计算机技术爱好者交流学习及个人合法离线备份之用。
2. **知识产权与版权保护**：请使用者严格遵守所在国家或地区的法律法规，自觉尊重原创作者及版权持有人的知识产权与合法权益。未经版权方明确书面授权许可，**严禁将通过本工具下载的任何视听内容用于商业盈利、公开转播、二次分发、非法盗版传播或其它任何侵犯版权的违法违规行为**。
3. **免责与法律责任界定**：本工具仅提供通用的客户端流媒体协议解析与本地存储技术，开发者不提供、不托管、亦不分发任何音视频资源。用户因使用本工具而导致的任何形式的直接或间接法律责任、版权纠纷、民事侵权或第三方经济损失，**均由使用者本人独立全权承担，开发者及贡献者不承担任何直接或连带法律责任**。
4. **合理使用原则**：若您通过本工具获取的媒体资源涉及第三方版权争议，请在测试或学习完成后 24 小时内自觉删除。如果您对某些资源的版权归属存疑，请立即停止下载与使用。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 许可协议开源。<br>
致谢：[N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) 与 [FFmpeg](https://ffmpeg.org/) 为音视频流媒体处理提供的卓越技术支持。
---

## 📬 联系作者与技术支持

如果您在使用过程中遇到任何问题、功能 Bug、使用疑惑，或有宝贵的改进建议与功能需求，欢迎随时通过邮件联系作者：

- **QQ 邮箱**：[2792893068@qq.com](mailto:2792893068@qq.com)
- **Gmail**：[lepa23216@gmail.com](mailto:lepa23216@gmail.com)

收到邮件后会尽快为您解答与处理！感谢您的支持与反馈！

---

### 🏷️ 核心技术与检索索引 (Search Topics & Keywords)
`m3u8-downloader` • `video-downloader` • `catcatch-alternative` • `n-m3u8dl-re-gui` • `simpleg-upgrade` • `ffmpeg-gui` • `hls-stream-sniffer` • `dash-mpd-downloader` • `browser-extension` • `bilibili-video-download` • `douyin-watermark-free` • `chrome-video-extractor` • `yt-dlp-gui` • `stream-recorder` • `idm-alternative` • `media-downloader` • `video-sniffer` • `hls-downloader`

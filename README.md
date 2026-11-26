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
  <img src="docs/images/starstream_logo.png" width="144" alt="StarStream Pro Logo">
</p>

<p align="center">
  <img src="docs/images/hero_banner.png" width="96%" alt="StarStream Pro Hero Banner">
</p>

# 星流媒体下载器 (StarStream Pro)

**全平台网页音视频与文件智能嗅探扩展 · 工业级多线程并发桌面端 · 原生硬解混流 Android 客户端**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/StarStream?style=flat-square&color=2563eb&label=Release)](https://github.com/xuewexin/StarStream/releases)
[![Stars](https://img.shields.io/github/stars/xuewexin/StarStream?style=flat-square&color=f5c518&label=Stars)](https://github.com/xuewexin/StarStream/stargazers)
[![Downloads](https://img.shields.io/github/downloads/xuewexin/StarStream/total?style=flat-square&color=10b981&label=Downloads)](https://github.com/xuewexin/StarStream/releases)
[![Desktop](https://img.shields.io/badge/Desktop-64bit%20Client-0284c7.svg?style=flat-square)](#)
[![Android](https://img.shields.io/badge/Android-7.0%2B%20APK-10b981.svg?style=flat-square)](#)
[![Extension](https://img.shields.io/badge/Browser%20Extension-Manifest%20V3-7c3aed.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-0ea5e9.svg?style=flat-square)](LICENSE)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream_v3.2.8_Portable.zip">
    <img src="https://img.shields.io/badge/桌面全套便携包-StarStream_v3.2.8_Portable.zip-2563eb?style=for-the-badge" alt="下载便携全套包">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream.exe">
    <img src="https://img.shields.io/badge/独立主程序-StarStream.exe-059669?style=for-the-badge" alt="下载独立单文件版">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream_Browser_Extension_v3.2.8.zip">
    <img src="https://img.shields.io/badge/浏览器嗅探扩展-Extension_v3.2.8.zip-7c3aed?style=for-the-badge" alt="下载浏览器扩展">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream-Android-v3.2.8.apk">
    <img src="https://img.shields.io/badge/Android%20手机端-StarStream--Android--v3.2.8.apk-0284c7?style=for-the-badge" alt="下载安卓客户端">
  </a>
</p>

> [!IMPORTANT]
> ### 三端一体化协同体验：桌面客户端 + 浏览器扩展 + Android 移动端
> - **浏览器嗅探扩展 (Manifest V3)**：在日常浏览网页播放视频或下载文件时，自动截取 HLS (M3U8)、DASH (MPD)、MP4 等真实流媒体数据流，智能提取清晰度、时长与分集目录，并在播放器右上角提供悬浮下载胶囊一键推送客户端。
> - **桌面下载客户端 (PyQt5 + N_m3u8DL-RE + FFmpeg)**：内置高性能流媒体并发拉取核心与多媒体工具箱，支持高并发多线程分块下载、音视频双轨无损混流 MP4、AES-128 解密、批量格式转码及可选离线画质增强。
> - **Android 移动端 (原生 Kotlin + MediaMuxer)**：内置极简多内核嗅探浏览器、多文件类型爬取（视频/音频/文档/压缩包）、边下边看、外部播放器防盗链在线预览、可折叠分类书签与历史记录恢复。

<p align="center">
  <a href="#-实机运行展示">实机展示</a> •
  <a href="#-版本发布与获取">版本下载</a> •
  <a href="#-核心架构亮点">核心特性</a> •
  <a href="#-android-移动端特性">Android 端</a> •
  <a href="#-浏览器扩展加载指南">扩展导入</a> •
  <a href="#-常见问题解答-faq">常见问题</a>
</p>

</div>

---

## 💡 为什么选择 StarStream Pro？

| 常见下载痛点 | StarStream Pro 的技术解决路径 |
|---|---|
| 网页播放器隐藏清晰度与真实切片地址 | 自动解析 Master M3U8 与 DASH 双流清单，展开多路画质规格（4K / 1080P / 720P）直观呈现 |
| 音视频分离流下载后只有画面没有声音 | 自动捕获并配对最高兼容度音频轨，下载后调用本地无损混流封装为通用 MP4 |
| 多集课程、连续剧集逐集点击太繁琐 | 内置选集扫描与批量连爬引擎，自动正序命名归档到独立剧集文件夹 |
| 防盗链鉴权严苛，第三方工具常报 403 | 自动提取浏览器 `Referer`、`Cookie`、`User-Agent` 并严格对齐当前代理出口 |
| 手机端想边下载边预览大体积长视频 | 内置本地 `127.0.0.1` 流媒体缓冲代理，已落盘分片秒读取，支持边下边看与外部播放器在线预览 |

---

## 📸 实机运行展示

### 🖥️ 桌面端主下载控制中心
> 采用纯矢量图标与无间隙深色暗夜面板设计，实时统筹所有任务序号、画质规格、时长、协议类型、文件大小、下载进度、瞬时网速、剩余耗时与本地引擎就绪状态。

<p align="center">
  <img src="docs/images/showcase_1_pc_main.png" width="94%" alt="StarStream 桌面端主下载控制中心">
</p>

<table>
  <tr>
    <td width="50%" align="center">
      <b>网页视频悬浮嗅探与一键推送</b><br>
      <sub>页面播放媒体时自动浮现操作胶囊并对齐代理推流</sub><br><br>
      <img src="docs/images/web_capsule_youtube.png" width="95%" alt="网页端悬浮嗅探下载">
    </td>
    <td width="50%" align="center">
      <b>FFmpeg 专业多媒体处理工具箱</b><br>
      <sub>集格式转换、音视频混流、提取音频与无损剪辑于一体</sub><br><br>
      <img src="docs/images/app_ffmpeg_toolbox.png" width="95%" alt="FFmpeg 多媒体工具箱">
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <b>新建任务与多线程代理配置</b><br>
      <sub>支持直链/合集解析与单任务独立并发、代理设置</sub><br><br>
      <img src="docs/images/app_new_task.png" width="95%" alt="新建任务配置">
    </td>
    <td width="50%" align="center">
      <b>系统全局设置与本地画质增强</b><br>
      <sub>支持下载路径、多线程数、代理网络池与可选清晰增强设置</sub><br><br>
      <img src="docs/images/showcase_5_pc_settings.png" width="95%" alt="全局设置与画质增强中心">
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <b>桌面即时监控微面板</b><br>
      <sub>随点随开，掌握当前下载速率与快捷工具入口</sub><br><br>
      <img src="docs/images/app_floating_panel.png" width="92%" alt="桌面悬浮监控面板">
    </td>
    <td width="50%" align="center">
      <b>极简星球悬浮监控挂件</b><br>
      <sub>支持拖拽贴边、网速呼吸显示与拖入直链触发下载</sub><br><br>
      <img src="docs/images/app_floating_widget.png" width="46%" alt="桌面悬浮球挂件">
    </td>
  </tr>
</table>

---

## 📱 Android 移动端特性

Android 原生客户端源码位于 [android_app/](android_app/)，编译产物可直接从 Releases 获取：

- **内置多内核极简浏览器**：干净无广告启动页，内置多种桌面/移动端内核身份预设，支持一键 **「身份刷新」**（轮换版本号并重置会话缓存）。
- **完善的数据持久化与交互**：
  - 支持 **访问历史记录本地存储**，支持按最近访问重开、单条清除与全部清空；
  - 支持 **多标签页与当前页面持久化保存**：返回下载队列或彻底退出应用重进后，自动恢复上次所有标签页与网页；
  - 仅剩单个页面时 **左滑返回优先回到浏览器主页**，再次返回才退出至下载列表；
  - 首页「我的收藏书签」与「最近访问记录」均支持 **一键折叠/展开**，支持创建不同名称的 **自定义收藏文件夹**。
- **全类型资源嗅探与详细信息查看**：支持视频/流媒体（M3U8/MPD/MP4/MKV/FLV）、音频（MP3/M4A/FLAC/AAC）及文档安装包（PDF/ZIP/7Z/APK）爬取与自定义过滤；点击捕获条目即可探测并展示 **时长、格式类型、分辨率与真实大小**。
- **边下边看与外部在线预览**：内置本地防盗链 HTTP 流媒体代理，下载中的视频可即刻点击 **「边下边看」**，嗅探到的视频支持调用手机已安装的外部播放器实现免下载在线流畅预览。
- **高自由度下载控制**：支持同时下载多任务上限调节（1~6）、多线程并发分块设置（2~24）、以及自由选择手机任意 **自定义储存文件夹 (SAF)**。

---

## 📦 版本发布与获取 (Releases)

| 发行版本 | 内置组件 | 适用场景 | 获取链接 |
|---|---|---|---|
| **桌面全套便携包** | `StarStream.exe` + `N_m3u8DL-RE` + `FFmpeg` + 文档 | **推荐未配置环境用户**，解压即用，全部底层核心预置完成 | [StarStream_v3.2.8_Portable.zip](https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream_v3.2.8_Portable.zip) |
| **独立单文件桌面版** | 单文件独立程序（自动全盘探测本地引擎） | 本地已存在 `FFmpeg` 的用户；请置于单独空文件夹内运行 | [StarStream.exe](https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream.exe) |
| **浏览器嗅探扩展包** | Manifest V3 纯扩展源码目录 | 搭配桌面客户端使用，开启网页悬浮嗅探与批量推送 | [StarStream_Browser_Extension_v3.2.8.zip](https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream_Browser_Extension_v3.2.8.zip) |
| **Android 手机端** | 原生 Kotlin 安装包（含内置浏览器与硬件混流） | 手机端独立网页嗅探、边下边看、同系列连爬与文件下载 | [StarStream-Android-v3.2.8.apk](https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream-Android-v3.2.8.apk) |

---

## ⚡ 核心架构亮点

| 能力维度 | StarStream Pro 核心实现 |
|---|---|
| **全协议网络抓取** | 深度介入媒体播放元素与网络异步请求，支持 HLS 加密分片、DASH 分离音视频及大体积文件断点分块 |
| **自动化封装标准 MP4** | 桌面端基于 FFmpeg、移动端基于原生 `MediaExtractor + MediaMuxer` 无损封装并自动对齐音画时间轴 |
| **防盗链环境对齐** | 全链路继承网页播放上下文（Referer / Cookie / UA 与代理通道），从根源避免跨节点导致的 403 拒绝 |
| **可选画质增强（默认关闭）** | 支持手动启用本地离线清晰锐化或开源超分辨率算法增强低清片源（全程本地免费运行，无云端限制） |
| **全开源透明** | 桌面端、浏览器扩展、Android 客户端全套源码公开，零收费功能、无商业广告与强制绑定 |

---

## 🧩 浏览器扩展加载指南

1. 下载并解压 [StarStream_Browser_Extension_v3.2.8.zip](https://github.com/xuewexin/StarStream/releases/download/v3.2.8/StarStream_Browser_Extension_v3.2.8.zip)（或直接使用仓库内 [m3u8-sniffer-extension/](m3u8-sniffer-extension/) 目录）。
2. 在常用现代浏览器的地址栏打开 **扩展程序管理页**，开启右上角 **「开发者模式」**。
3. 点击 **「加载已解压的扩展程序」**，选择 `m3u8-sniffer-extension` 目录后固定到工具栏即可联动桌面客户端使用。

---

## 🚀 开发者源码构建与启动

### 桌面客户端 (Python)
```bash
git clone https://github.com/xuewexin/StarStream.git
cd StarStream
pip install -r requirements.txt
python run_app.py
```

### Android 移动端 (Gradle)
```bash
cd android_app
gradle assembleDebug --no-daemon
```

---

## ❓ 常见问题解答 (FAQ)

<details>
<summary><b>1. 为什么桌面客户端必须配合浏览器扩展使用？</b></summary>
<p>浏览器扩展负责实时感知网页中的真实媒体流、分集菜单与登录防盗链凭证；桌面客户端则专注于高并发分块下载与 FFmpeg 无损混流。二者通过本地端口 <code>18910</code> 通信协作，也可点击扩展中的「复制命令」在终端单独调用下载引擎。</p>
</details>

<details>
<summary><b>2. 为什么部分视频需要开启与浏览器一致的代理？</b></summary>
<p>许多流媒体服务端会将切片访问权限与网页请求时的出口 IP 绑定。选择扩展默认的「自动匹配浏览器代理」可将下载器链路与浏览器完全对齐，解决 403 或分片超时问题。</p>
</details>

<details>
<summary><b>3. 手机端下载画质与声音如何保证？</b></summary>
<p>Android 端内置解析与原生硬件混流引擎，自动优先匹配与手机兼容性最好的 AAC 音轨，并支持解析 HLS 独立音频清单；遇到正在下载的大型视频时，可通过「边下边看」即刻缓冲确认画面与声音。</p>
</details>

---

## ⚖️ 免责声明 (Disclaimer)

本项目仅作为流媒体传输协议解析、多线程网络调度与跨端 UI 工程化的开源技术学习与研究示例，**不提供、不托管也不分发任何受版权保护的音视频内容**。请使用者严格遵守所在国家与地区的法律法规，尊重原作者与版权方合法权益，下载内容仅限个人合法备份与技术测试，切勿用于任何商业盈利或违规分发用途；因不当使用产生的全部法律责任由使用者本人自行承担。

---

## 📬 联系作者与开源致谢

- **开发作者**：`xuewexin`
- **项目仓库**：[github.com/xuewexin/StarStream](https://github.com/xuewexin/StarStream) · [提交建议 / Issues](https://github.com/xuewexin/StarStream/issues)
- **联系邮箱**：[2792893068@qq.com](mailto:2792893068@qq.com) / [lepa23216@gmail.com](mailto:lepa23216@gmail.com)
- **开源致谢**：感谢 [FFmpeg](https://ffmpeg.org/) 与 [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) 等卓越底层开源工具提供的技术基石。本项目采用 [MIT License](LICENSE) 开源。

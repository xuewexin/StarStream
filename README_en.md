<div align="center">

<p align="center">
  <b>Language / Languages:</b><br>
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

# StarStream Pro — All-in-One Media Sniffer & Downloader

**Cross-Platform Web Media Sniffer Extension (MV3) · High-Speed Multi-Threaded Desktop Client · Native Android App**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/StarStream?style=flat-square&color=2563eb&label=Release)](https://github.com/xuewexin/StarStream/releases)
[![Stars](https://img.shields.io/github/stars/xuewexin/StarStream?style=flat-square&color=f5c518&label=Stars)](https://github.com/xuewexin/StarStream/stargazers)
[![Downloads](https://img.shields.io/github/downloads/xuewexin/StarStream/total?style=flat-square&color=10b981&label=Downloads)](https://github.com/xuewexin/StarStream/releases)
[![Desktop](https://img.shields.io/badge/Desktop-64bit%20Client-0284c7.svg?style=flat-square)](#)
[![Android](https://img.shields.io/badge/Android-7.0%2B%20APK-10b981.svg?style=flat-square)](#)
[![Extension](https://img.shields.io/badge/Browser%20Extension-Manifest%20V3-7c3aed.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-0ea5e9.svg?style=flat-square)](LICENSE)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream_v3.3.0_Portable.zip">
    <img src="https://img.shields.io/badge/Portable%20Suite-StarStream_v3.3.0_Portable.zip-2563eb?style=for-the-badge" alt="Download Portable Package">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream.exe">
    <img src="https://img.shields.io/badge/Standalone%20Client-StarStream.exe-059669?style=for-the-badge" alt="Download Standalone Executable">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream_Browser_Extension_v3.3.0.zip">
    <img src="https://img.shields.io/badge/Sniffer%20Extension-Extension_v3.3.0.zip-7c3aed?style=for-the-badge" alt="Download Browser Extension">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream-Android-v3.3.0.apk">
    <img src="https://img.shields.io/badge/Android%20APK-StarStream--Android--v3.3.0.apk-0284c7?style=for-the-badge" alt="Download Android APK">
  </a>
</p>

> [!IMPORTANT]
> ### Unified Desktop, Browser Extension & Mobile Ecosystem
> - **Browser Sniffer Extension (MV3)**: Automatically intercepts HLS (`M3U8`), DASH (`MPD`/`M4S`), MP4, audio, and batch episode playlists while browsing, displaying resolution, bitrate, and duration on a clean floating capsule.
> - **Desktop Client (PyQt5 + N_m3u8DL-RE + FFmpeg)**: Multi-threaded chunked downloading, lossless audio-video muxing, AES-128 decryption, batch format converter, and optional offline local video clarity enhancement.
> - **Android Client (Native Kotlin + FFmpegKit)**: Built-in minimalist multi-kernel sniffer browser, multi-type file crawling, watch-while-downloading, external player streaming preview, collapsible bookmark folders, and persistent tabs/history.

</div>

---

## 💡 Why StarStream Pro?

| Common Pain Point | How StarStream Pro Solves It |
|---|---|
| Split audio/video streams play with no sound or fail to mux | Auto-pairs audio & video streams across Bilibili, Douyin, and all split-track sites, losslessly muxing with **FFmpeg / FFmpegKit** into standard MP4 |
| Tedious manual downloads & messy episode names | Batch series crawler automatically names files as **Series Title + Episode Suffix** |
| Strict anti-hotlink 403/412 errors & CDN throttling | Syncs browser `Cookie`, `Referer`, `User-Agent`, and refreshes tokens automatically to break CDN speed caps |
| Fixed extension toggles & waiting to preview large videos | IDM-style editable capture extension list, instant watch-while-downloading, and external player streaming proxy |

---

<p align="center">
  <img src="docs/images/hero_banner.png" width="96%" alt="StarStream Pro Hero Banner">
</p>

---

## 📸 Live Application Showcase

<p align="center">
  <img src="docs/images/showcase_1_pc_main.png" width="94%" alt="StarStream Desktop Control Center">
</p>

<table>
  <tr>
    <td width="50%" align="center">
      <b>Web Player Floating Capsule & Auto Sniffing</b><br>
      <img src="docs/images/web_capsule_youtube.png" width="95%" alt="Web Floating Sniffer Capsule">
    </td>
    <td width="50%" align="center">
      <b>Built-in FFmpeg Multimedia Toolbox</b><br>
      <img src="docs/images/app_ffmpeg_toolbox.png" width="95%" alt="FFmpeg Multimedia Toolbox">
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <b>New Task & Multi-Thread Proxy Configuration</b><br>
      <img src="docs/images/app_new_task.png" width="95%" alt="New Task Configuration">
    </td>
    <td width="50%" align="center">
      <b>System Settings & Optional Quality Enhancement</b><br>
      <img src="docs/images/showcase_5_pc_settings.png" width="95%" alt="Settings & Enhancement">
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <b>Quick Desktop Monitor Dashboard</b><br>
      <img src="docs/images/app_floating_panel.png" width="92%" alt="Floating Monitor Panel">
    </td>
    <td width="50%" align="center">
      <b>Floating Desktop Speed Widget</b><br>
      <img src="docs/images/app_floating_widget.png" width="46%" alt="Floating Desktop Widget">
    </td>
  </tr>
</table>

---

## 📱 Android Client Highlights

- **Built-in Clean Multi-Kernel Browser**: Minimalist start page, switchable UA presets, one-tap **Identity Refresh** (rotates browser version & clears session cookies/cache), and pull-to-refresh.
- **Persistent Tabs, Bookmarks & History**: Automatically preserves browsing history, all open tabs, and the active webpage across app restarts; supports **collapsible bookmarks/history** and **custom named bookmark folders**.
- **Watch While Downloading & External Preview**: Built-in local anti-hotlink streaming proxy supports instant buffering playback during downloads and external media player online preview.
- **Customizable Concurrency & Storage**: Configure max simultaneous tasks (1–6), concurrent threads (2–24), sniffable file filters (Video/Audio/Docs/APK), and custom storage folders via SAF.

---

## 📦 Releases & Source Build

- Grab prebuilt releases directly from [GitHub Releases v3.3.0](https://github.com/xuewexin/StarStream/releases/tag/v3.3.0).
- **Desktop Source**: `pip install -r requirements.txt && python run_app.py`
- **Android Source**: `cd android_app && gradle assembleDebug --no-daemon`

---

## ⚖️ Disclaimer & Contact

This open-source project is intended solely for streaming protocol research, network scheduling engineering, and personal legal backups. All source code is MIT licensed.  
Author: `xuewexin` · Email: [2792893068@qq.com](mailto:2792893068@qq.com) / [lepa23216@gmail.com](mailto:lepa23216@gmail.com)

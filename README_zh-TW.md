<div align="center">

<p align="center">
  <b>Language / 多語言:</b><br>
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

# 星流媒體下載器 (StarStream Pro)

**全平台網頁影音與檔案智慧探測擴充 · 工業級多執行緒並發桌面端 · 原生硬解混流 Android 客戶端**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/StarStream?style=flat-square&color=2563eb&label=Release)](https://github.com/xuewexin/StarStream/releases)
[![Stars](https://img.shields.io/github/stars/xuewexin/StarStream?style=flat-square&color=f5c518&label=Stars)](https://github.com/xuewexin/StarStream/stargazers)
[![Desktop](https://img.shields.io/badge/Desktop-64bit%20Client-0284c7.svg?style=flat-square)](#)
[![Android](https://img.shields.io/badge/Android-7.0%2B%20APK-10b981.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-0ea5e9.svg?style=flat-square)](LICENSE)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream_v3.3.0_Portable.zip">
    <img src="https://img.shields.io/badge/桌面便攜全套包-StarStream_v3.3.0_Portable.zip-2563eb?style=for-the-badge" alt="下載便攜全套包">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream.exe">
    <img src="https://img.shields.io/badge/獨立主程式-StarStream.exe-059669?style=for-the-badge" alt="下載獨立版">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream_Browser_Extension_v3.3.0.zip">
    <img src="https://img.shields.io/badge/瀏覽器探測擴充-Extension_v3.3.0.zip-7c3aed?style=for-the-badge" alt="下載瀏覽器擴充">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream-Android-v3.3.0.apk">
    <img src="https://img.shields.io/badge/Android%20手機端-StarStream--Android--v3.3.0.apk-0284c7?style=for-the-badge" alt="下載安卓版">
  </a>
</p>

</div>

---

## 💡 為什麼選擇 StarStream Pro？

| 常見下載痛點 | StarStream Pro 的技術解決方案 |
|---|---|
| 影音分離流下載後沒有畫面或沒有聲音 | 全站自動配對獨立音軌與視訊軌（B站 / 抖音等），桌面與手機皆透過 **FFmpeg** 無損混流封裝為標準 MP4 |
| 多集課程、連續劇集逐集點擊繁瑣 | 內建選集掃描與批次連爬引擎，依「**影片名稱 + 集數**」自動規範命名歸檔 |
| 防盜鏈鑑權與限速導致下載失敗 | 自動同步瀏覽器 `Cookie` / `Referer` / `User-Agent`，監測限速並主動刷新令牌重建高速連線 |
| 手機端想邊下邊看與自訂抓取格式 | 支援 IDM 風格自訂爬取副檔名列表、邊下邊看代理與外部播放器防盜鏈線上預覽 |

---

<p align="center">
  <img src="docs/images/hero_banner.png" width="96%" alt="StarStream Pro Hero Banner">
</p>

---

## 📸 實機運行展示

<p align="center">
  <img src="docs/images/showcase_1_pc_main.png" width="94%" alt="StarStream 桌面端主控制中心">
</p>

<table>
  <tr>
    <td width="50%" align="center">
      <b>網頁影音懸浮探測與一鍵推送</b><br>
      <img src="docs/images/web_capsule_youtube.png" width="95%" alt="網頁端懸浮探測下載">
    </td>
    <td width="50%" align="center">
      <b>FFmpeg 專業多媒體處理工具箱</b><br>
      <img src="docs/images/app_ffmpeg_toolbox.png" width="95%" alt="FFmpeg 工具箱">
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <b>新建任務與多執行緒代理配置</b><br>
      <img src="docs/images/app_new_task.png" width="95%" alt="新建任務配置">
    </td>
    <td width="50%" align="center">
      <b>系統全域設定與本地畫質增強</b><br>
      <img src="docs/images/showcase_5_pc_settings.png" width="95%" alt="全域設定中心">
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <b>桌面即時監控微面板</b><br>
      <img src="docs/images/app_floating_panel.png" width="92%" alt="桌面懸浮監控面板">
    </td>
    <td width="50%" align="center">
      <b>極簡星球懸浮監控掛件</b><br>
      <img src="docs/images/app_floating_widget.png" width="46%" alt="桌面懸浮球掛件">
    </td>
  </tr>
</table>

---

## 📱 Android 手機端重點特性

- 內建多核心極簡瀏覽器與一鍵 **「身份刷新」**，支持網頁與清單下拉刷新。
- **跨重啟狀態持久化**：完整儲存瀏覽歷史記錄、打開的分頁與當前訪問頁面；單頁面左滑返回先回主頁再退出。
- **可折疊收藏資料夾**：支援建立自訂名稱收藏資料夾，書籤與最近訪問區塊可隨時折疊展開。
- **邊下邊看 & 外部線上預覽**：下載中即可透過本地防盜鏈代理緩衝播放，探測到的影片可直接呼叫外部播放器線上預覽。
- **彈性設定**：支援同時下載任務上限（1~6）、多執行緒（2~24）與系統自訂儲存目錄選擇。

## 📬 聯繫作者與授權條款
- 作者：`xuewexin` · 信箱：[2792893068@qq.com](mailto:2792893068@qq.com) / [lepa23216@gmail.com](mailto:lepa23216@gmail.com)
- 本專案採用 [MIT License](LICENSE) 開源，僅供技術學習與個人合法離線備份之用。

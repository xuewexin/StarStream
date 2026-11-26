<div align="center">

<p align="center">
  <b>Language / 다국어:</b><br>
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

# StarStream Pro - 통합 미디어 다운로더

**웹 미디어 스니퍼 확장 (MV3) · 고속 멀티스레드 데스크톱 클라이언트 · 네이티브 Android 앱**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/StarStream?style=flat-square&color=2563eb&label=Release)](https://github.com/xuewexin/StarStream/releases)
[![Stars](https://img.shields.io/github/stars/xuewexin/StarStream?style=flat-square&color=f5c518&label=Stars)](https://github.com/xuewexin/StarStream/stargazers)
[![Desktop](https://img.shields.io/badge/Desktop-64bit%20Client-0284c7.svg?style=flat-square)](#)
[![Android](https://img.shields.io/badge/Android-7.0%2B%20APK-10b981.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-0ea5e9.svg?style=flat-square)](LICENSE)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream_v3.3.0_Portable.zip">
    <img src="https://img.shields.io/badge/포터블%20패키지-StarStream_v3.3.0_Portable.zip-2563eb?style=for-the-badge" alt="Portable">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream.exe">
    <img src="https://img.shields.io/badge/단독%20실행%20파일-StarStream.exe-059669?style=for-the-badge" alt="EXE">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream_Browser_Extension_v3.3.0.zip">
    <img src="https://img.shields.io/badge/브라우저%20확장-Extension_v3.3.0.zip-7c3aed?style=for-the-badge" alt="Extension">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.3.0/StarStream-Android-v3.3.0.apk">
    <img src="https://img.shields.io/badge/Android%20앱-StarStream--Android--v3.3.0.apk-0284c7?style=for-the-badge" alt="APK">
  </a>
</p>

</div>

---

## 💡 왜 StarStream Pro인가요?

| 자주 겪는 문제 | StarStream Pro의 해결 방식 |
|---|---|
| 영상·음성 분리 스트림 다운로드 시 무음/병합 실패 | Bilibili, Douyin 등 모든 분리 스트림 사이트 자동 페어링 + **FFmpeg / FFmpegKit** 무손실 MP4 병합 |
| 연속극/강의 시리즈 일괄 저장 및 파일명 정리 | **영상 제목 + 회차** 형식으로 자동 명명하여 일괄 다운로드 |
| 까다로운 핫링크 차단 및 CDN 속도 제한 | 브라우저 `Cookie` / `Referer` 동기화 및 속도 저하 시 자동 토큰 갱신 가속 |
| 원하는 확장자만 골라 캡처 & 받으면서 바로 보기 | IDM 스타일 확장자 추가/삭제, 다운로드 중 실시간 재생 및 외부 플레이어 미리보기 지원 |

---

<p align="center">
  <img src="docs/images/hero_banner.png" width="96%" alt="StarStream Pro Hero Banner">
</p>

---

## 📸 실제 구동 화면

<p align="center">
  <img src="docs/images/showcase_1_pc_main.png" width="94%" alt="StarStream 메인 콘솔">
</p>

<table>
  <tr>
    <td width="50%" align="center"><img src="docs/images/web_capsule_youtube.png" width="95%" alt="웹 캡슐"><br><sub>웹 비디오 플로팅 캡처</sub></td>
    <td width="50%" align="center"><img src="docs/images/app_ffmpeg_toolbox.png" width="95%" alt="FFmpeg 툴박스"><br><sub>내장 FFmpeg 멀티미디어 툴박스</sub></td>
  </tr>
  <tr>
    <td width="50%" align="center"><img src="docs/images/app_new_task.png" width="95%" alt="새 작업"><br><sub>새 작업 및 프록시 설정</sub></td>
    <td width="50%" align="center"><img src="docs/images/showcase_5_pc_settings.png" width="95%" alt="환경 설정"><br><sub>스레드 및 화질 향상 설정</sub></td>
  </tr>
  <tr>
    <td width="50%" align="center"><img src="docs/images/app_floating_panel.png" width="92%" alt="모니터 패널"><br><sub>데스크톱 실시간 모니터</sub></td>
    <td width="50%" align="center"><img src="docs/images/app_floating_widget.png" width="46%" alt="플로팅 위젯"><br><sub>플로팅 속도 모니터링 위젯</sub></td>
  </tr>
</table>

---

## 📱 Android 모바일 주요 기능

- **내장 멀티 커널 브라우저 & 신원 새로고침**, 당겨서 새로고침, 접이식 북마크 폴더 및 방문 기록/열린 탭 영구 보존.
- **다운로드 중 실시간 재생 & 외부 플레이어 온라인 미리보기**.
- **동시 다운로드 작업 수, 멀티스레드 수 및 사용자 지정 저장 폴더(SAF) 설정**.

Author: `xuewexin` · [2792893068@qq.com](mailto:2792893068@qq.com) / [lepa23216@gmail.com](mailto:lepa23216@gmail.com) · MIT License

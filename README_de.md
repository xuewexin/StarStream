<div align="center">

<p align="center">
  <b>Language / Mehrsprachig:</b><br>
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

# 🌟 StarStream Pro - Medien-Downloader

**All-in-One Web-Video- & Audio-Sniffer-Erweiterung + Industrieller Multithread-Download-Client + Integrierte N_m3u8DL-RE & FFmpeg-Kerne**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/StarStream?style=flat-square&color=blue&label=GitHub%20Release)](https://github.com/xuewexin/StarStream/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d7.svg?style=flat-square&logo=windows)](#)
[![Python](https://img.shields.io/badge/Python-3.8%20~%203.13-3776ab.svg?style=flat-square&logo=python)](#)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5%20%7C%20Dark%20Slate-6366f1.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square)](#)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream_v3.2.1_Portable.zip">
    <img src="https://img.shields.io/badge/⭐%20Portable%20Paket-StarStream_v3.2.1_Portable.zip%20(FFmpeg%20%26%20N_m3u8DL%20integriert)-2563eb?style=for-the-badge&logo=windows&logoColor=white" alt="Portable Paket herunterladen">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream.exe">
    <img src="https://img.shields.io/badge/🚀%20Standalone%20EXE-StarStream.exe%20(Auto--Scan%20Tools)-059669?style=for-the-badge&logo=windows&logoColor=white" alt="StarStream.exe herunterladen">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream_Browser_Extension_v3.2.1.zip">
    <img src="https://img.shields.io/badge/🧩%20Browser--Erweiterung-Extension_v3.2.1.zip%20(165%20KB)-7c3aed?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Erweiterung herunterladen">
  </a>
  &nbsp;&nbsp;
  <a href="#-vergleich--alternativen-warum-starstream">
    <img src="https://img.shields.io/badge/🔥%20Alternative-CatCatch%20%7C%20SimpleG%20%7C%20yt--dlp-10b981?style=for-the-badge" alt="Vergleich & Alternativen">
  </a>
</p>

> [!IMPORTANT]
> ### 💡 Goldenes Duo Handbuch: Desktop-Software und Browser-Erweiterung arbeiten zusammen!
> - **🧩 Browser-Sniffer-Erweiterung (Frontend-Radar)**: Fängt beim Surfen und Abspielen von Videos automatisch echte M3U8-, DASH- (MPD) und MP4-Datenströme ab und blendet oben rechts im Player eine Download-Kapsel ein;
> - **💻 Desktop-Client (Backend-Engine)**: Empfängt die übergebenen Videoaufgaben und steuert die integrierten Hochleistungsmotoren **N_m3u8DL-RE** und **FFmpeg** für Downloads mit bis zu 24,7 MB/s und verlustfreie Zusammenführung;
> - **Perfektes Zusammenspiel (wie IDM und die IDM-Erweiterung)**: Beide Komponenten sind unverzichtbar! Bitte folgen Sie der [Anleitung zur Installation der Browser-Erweiterung](#-anleitung-zur-installation-der-browser-erweiterung).

<p align="center">
  <a href="#-screens--funktionen">Screenshots</a> •
  <a href="#-versionen-und-downloads">Downloads</a> •
  <a href="#-hauptfunktionen">Hauptfunktionen</a> •
  <a href="#-anleitung-zur-installation-der-browser-erweiterung">Installation</a> •
  <a href="#-proxy-einstellungen">Proxy</a> •
  <a href="#-häufig-gestellte-fragen-faq">FAQ</a> •
  <a href="#-haftungsausschluss">Haftungsausschluss</a>
</p>

</div>

---

## 📸 Screenshots & Funktionen

### 1. Desktop-Dashboard (Modernes Dark-Slate-Industriedesign)
> Präzise Vektorsymbole und lückenlose Statusüberwachung: Lokaler Port `18910` bereit, `FFmpeg` bereit, `N_m3u8DL (RE)` einsatzbereit, Echtzeitanzeige für Netzwerk-Proxys.

<p align="center">
  <img src="docs/images/app_main_window.png" width="92%" alt="Desktop-Dashboard">
</p>

---

### 2. Neuer Download-Auftrag (Individuelle Proxy- und Thread-Konfiguration)
> Intelligente URL-Erkennung per Klick. Konfigurieren Sie Threads (4 bis 32), Zielordner und Proxy-Verbindungsmodi für jeden Download separat.

<p align="center">
  <img src="docs/images/app_new_task.png" width="82%" alt="Neuer Download-Auftrag Dialog">
</p>

---

### 3. Professionelle FFmpeg-Multimedia-Toolbox (Konvertierung & Nachbearbeitung)
> Integrierte Medien-Toolbox: Einzel- und Stapelkonvertierung (MP4/MKV/TS/MOV), Muxen von Audio und Video, verlustfreie Audio-Extraktion und schneller Videoschnitt.

<p align="center">
  <img src="docs/images/app_ffmpeg_toolbox.png" width="82%" alt="FFmpeg-Toolbox">
</p>

---

### 4. Nahtloses Video-Sniffing (Beispiel YouTube)
> Ein eleganter schwebender Badge erscheint beim Abspielen von Webvideos. Auflösung und Dauer prüfen und den Download über denselben Proxy-Kanal an den Desktop übertragen.

<p align="center">
  <img src="docs/images/web_capsule_youtube.png" width="82%" alt="YouTube-Sniffer-Kapsel">
</p>

---

### 5. Web-Streaming-Sniffer & Direktübertragung (Automatische Proxy-Synchronisation)
> Zeigt echte Videoauflösungen, Dauer und Format an. Synchronisiert sich automatisch mit dem Browser-Proxy für extrem schnelle Downloads auf dem Desktop.

<p align="center">
  <img src="docs/images/web_capsule_bilibili.png" width="58%" alt="Web-Sniffer Schwebende Karte">
</p>

---

### 6. Desktop-Aufgabenüberwachung & Schnellwerkzeuge
> Klicken Sie auf die Schwebekugel, um das Dashboard zu öffnen: Live-Downloadstatus, Gesamtrate überwachen und Stapelkonvertierung, FFmpeg sowie Video-Extraktor starten.

<p align="center">
  <img src="docs/images/app_floating_panel.png" width="68%" alt="Aufgabenüberwachung & Werkzeuge">
</p>

---

### 7. Desktop-Schwebendes Minifenster (Echtzeit-Überwachung von Status & Rate)
> Zukunftsweisendes Planeten-Widget mit freier Platzierung auf dem Desktop, Kantenandocken und Live-Anzeige der Download-Geschwindigkeit und bereiten Aufgaben.

<p align="center">
  <img src="docs/images/app_floating_widget.png" width="28%" alt="Schwebendes Desktop-Widget">
</p>


## 📦 Versionen und Downloads

Sie können die neueste Version von StarStream über die folgenden Kanäle herunterladen:

| Download-Art | Enthaltene Komponenten | Empfohlen für | Download-Link |
|---|---|---|---|
| **⭐ Empfohlen: StarStream_v3.2.1_Portable.zip** | Integrierte **StarStream.exe** + **N_m3u8DL-RE** + **FFmpeg** + Erweiterung | **Dringend empfohlen ohne FFmpeg / N_m3u8DL**, sofort einsatzbereit | [👉 Portable-Paket herunterladen](https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream_v3.2.1_Portable.zip) |
| **🚀 Standalone-EXE: StarStream.exe (77.5MB)** | Eigenständige ausführbare Binärdatei | **Für Benutzer mit vorhandenem FFmpeg oder N_m3u8DL**, automatische Pfaderkennung; **in separatem Ordner starten** | [👉 StarStream.exe herunterladen](https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream.exe) |
| **🧩 Browser-Erweiterung (v3.2.1)** | Quellpaket der Erweiterung (165 KB), MV3-Sniffer, Proxy-Ausrichtung | Webvideo-Sniffing, saubere Registerkarten, Sortierung | [👉 Extension.zip (165 KB) herunterladen](https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream_Browser_Extension_v3.2.1.zip) |
| **Offizielle GitHub Releases Seite** | Alle Versionen, Änderungsprotokolle und Checksummen | Versionsverlauf | [👉 Releases ansehen](https://github.com/xuewexin/StarStream/releases) |

> 💡 **Download- und Installationshinweise (Wichtiger Hinweis)**:
> 1. **Für Benutzer ohne installiertes FFmpeg oder N_m3u8DL**:
>    👉 **Empfehlung: Laden Sie das Portable-Paket (`StarStream_v3.2.1_Portable.zip`) herunter**! Es enthält alle erforderlichen Tools (`ffmpeg.exe` und `N_m3u8DL-RE.exe`) vorkonfiguriert.
> 2. **Für Benutzer, die FFmpeg oder N_m3u8DL bereits besitzen**:
>    👉 **Sie können direkt die eigenständige `StarStream.exe` herunterladen**! StarStream durchsucht beim Start automatisch Ihre Umgebungspfade (`PATH`) nach vorhandenen Tools.
> 3. **⚠️ Wichtiger Nutzungshinweis**:
>    Bitte platzieren Sie die eigenständige `StarStream.exe` **vor dem Start in einem sauberen, separaten Ordner (z. B. `D:\StarStream\`)**! Das Programm erstellt Konfigurationsdateien, Datenbanken und Protokolle im selben Ordner.

---

## ⚔️ Vergleich & Alternativen (Warum StarStream?)

Vergleich zwischen StarStream, Cat-Catch, SimpleG, N_m3u8DL-RE, yt-dlp und Video DownloadHelper:

| Funktion | 🌟 StarStream Pro | 🐱 Cat-Catch | 🛠️ SimpleG | ⚡ yt-dlp / CLI | 🦊 Video DownloadHelper |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Architektur** | **Client & Browser-Erweiterung kombiniert** | Nur Browser-Erweiterung | Klassische Desktop-App | Befehlszeilen-Tool (CLI) | Erweiterung + Bezahl-App |
| **Download-Engine** | **Integriertes N_m3u8DL-RE & FFmpeg** | Browser Blob / Fetch | Veraltetes N_m3u8DL-CLI | yt-dlp Python-Engine | Erweiterung / Drittanbieter-Host |
| **Multi-Threading** | **✅ Unterstützt (4 ~ 32 Threads, 24MB/s+)** | ❌ Single-Thread / Langsam | ⚠️ Einfaches Multi-Threading | Manuelle Befehlsparameter | Nur mit Premium-Lizenz |
| **Proxy-Synchronisation** | **✅ Automatisch mit Browser-IP (Anti-403)** | Nur Browser-Proxy | ❌ Erkennt Browser-Proxy nicht | Manueller `--proxy` Parameter | ❌ Nicht unterstützt |
| **Player-Overlay** | **✅ Download-Kapsel direkt im Videoplayer** | ❌ Klick auf Symbol nötig | ❌ Manuelles Kopieren der URL | ❌ Nur Terminaleingabe | Klick auf Symbol nötig |
| **Lizenz** | **✅ 100% Kostenlos & Open Source (MIT)** | Open Source | Open Source | Open Source | Kostenpflichtige Einschränkungen |

---

## ⚡ Hauptfunktionen

| Modul | Beschreibung |
|---|---|
| **Universal-Sniffer** | Fängt M3U8 (HLS), MPD (DASH), MP4, FLV, WebM, TS, MP3, AAC und Direktlinks ab. Tiefen-Hooks in `HTMLMediaElement.play`, `Blob`, `MediaSource`, `fetch/XHR`. |
| **Intelligente Kapsel** | Im Videoplayer eingeblendeter Aktions-Button, der Auflösungen (4K/1080P/720P), Laufzeiten und getrennte Audiostreams erkennt. |
| **Integrierter Player** | Leichtgewichtiger `hls.min.js`-Player im Erweiterungs-Popup zur Vorschau von Streams vor dem Download. |
| **Duales Download-System** | **Streaming**: [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) für Segment-Download und Multiplexing.<br>**Direktlink**: Python-Multithread-Range-Downloader. |
| **Konfiguration pro Video** | Eigener Speicherordner, individuelle Thread-Anzahl (4/8/16/32) und spezifischer Proxy für jedes Video. |
| **Automatische Proxy-Angleichung** | Gleicht die Ausgangs-IP des Downloaders mit dem Browser ab, um HTTP 403 Forbidden Fehler zuverlässig zu verhindern. |
| **Stapel-Formatkonverter** | Konvertierungszentrum für mehrere Dateien: Verlustfreies Kopieren (`-c copy`), H.264/H.265-Re-Encoding und Audioextraktion. |
| **Desktop-Benachrichtigungen** | Popups bei Abschluss oder Fehlern mit Schnellzugriff auf [Wiedergabe], [Ordner öffnen] und [Fehlerdiagnose]. |
| **Automatische MP4-Konvertierung** | Ruft FFmpeg nach dem Download auf, um Streams in MP4 mit `faststart`-Metadaten umzuwandeln. |
| **Fehlerdiagnose & Logs** | Analysiert Fehler (`Logs/download_errors.log`) mit konkreten Ratschlägen zu Token-Abläufen, AES-128 und DNS-Problemen. |
| **Festplatten-Bereinigung** | Scannt und entfernt unvollständige `.tmp`- und `.part`-Fragmente sicher von der Festplatte. |

---

## 🧩 Anleitung zur Installation der Browser-Erweiterung

> ⚠️ Chromium-Browser blockieren die direkte Installation externer `.crx`-Dateien per Drag-and-Drop. **Das Laden über den Entwicklermodus ist der offizielle und dauerhafte Weg.**

### Schritt 1: Erweiterungsseite des Browsers öffnen
- **Microsoft Edge**: `edge://extensions` in die Adressleiste eingeben und Enter drücken.
- **Google Chrome**: `chrome://extensions` in die Adressleiste eingeben und Enter drücken.

### Schritt 2: „Entwicklermodus“ aktivieren
- Schalten Sie oben rechts den Schalter **Entwicklermodus** (Developer mode) ein.
- Klicken Sie anschließend auf die Schaltfläche **[Entpackte Erweiterung laden]**.

### Schritt 3: Quellordner auswählen
1. Klicken Sie auf **[Entpackte Erweiterung laden]**.
2. Wählen Sie den Ordner **`m3u8-sniffer-extension`** aus.
3. Klicken Sie auf „Ordner auswählen“. Die Erweiterung ist einsatzbereit!
4. Heften Sie **StarStream Media Sniffer** an Ihre Browser-Symbolleiste.

---

## ⚖️ Haftungsausschluss

1. **Forschung und private Nutzung**: Dieses Projekt dient der technischen Analyse von Netzwerkprotokollen und rechtmäßigen privaten Offline-Sicherungen.
2. **Urheberrecht**: Bitte beachten Sie geltende Urheberrechte. Eine unbefugte kommerzielle Nutzung oder Weiterverbreitung ist untersagt.
3. **Haftungsbeschränkung**: Diese Software stellt lediglich Analyse- und Speichertechnologien bereit und hostet keine Medieninhalte.

---

## 📄 Lizenz

Lizenziert unter der [MIT License](LICENSE). Besonderer Dank an [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) und [FFmpeg](https://ffmpeg.org/).
---

## 📬 Kontakt zum Autor & Technischer Support

Wenn Sie während der Nutzung auf Probleme, Fehler oder Unklarheiten stoßen, oder Vorschläge zur Verbesserung und Funktionswünsche haben, können Sie sich jederzeit gerne per E-Mail an den Autor wenden:

- **QQ-Mail**: [2792893068@qq.com](mailto:2792893068@qq.com)
- **Gmail**: [lepa23216@gmail.com](mailto:lepa23216@gmail.com)

Nach Erhalt der E-Mail werden wir uns schnellstmöglich um Ihr Anliegen kümmern! Vielen Dank für Ihre Unterstützung und Ihr Feedback!

---

### 🏷️ Search Topics & SEO Keywords
`m3u8-downloader` • `video-downloader` • `catcatch-alternative` • `n-m3u8dl-re-gui` • `simpleg-upgrade` • `ffmpeg-gui` • `hls-stream-sniffer` • `dash-mpd-downloader` • `browser-extension` • `bilibili-video-download` • `douyin-watermark-free` • `chrome-video-extractor` • `yt-dlp-gui` • `stream-recorder` • `idm-alternative` • `media-downloader` • `video-sniffer` • `hls-downloader`

<div align="center">

<p align="center">
  <b>Language / Multilingüe:</b><br>
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

# 🌟 StarStream Pro - Descargador de Medios

**Extensión de rastreo de video y audio web todo en uno + Cliente de descarga multiproceso industrial + Núcleos integrados N_m3u8DL-RE y FFmpeg**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/StarStream?style=flat-square&color=blue&label=GitHub%20Release)](https://github.com/xuewexin/StarStream/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d7.svg?style=flat-square&logo=windows)](#)
[![Python](https://img.shields.io/badge/Python-3.8%20~%203.13-3776ab.svg?style=flat-square&logo=python)](#)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5%20%7C%20Dark%20Slate-6366f1.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square)](#)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream_v3.2.1_Portable.zip">
    <img src="https://img.shields.io/badge/⭐%20Paquete%20Portátil-StarStream_v3.2.1_Portable.zip%20(FFmpeg%20y%20N_m3u8DL%20integrados)-2563eb?style=for-the-badge&logo=windows&logoColor=white" alt="Descargar paquete portátil">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream.exe">
    <img src="https://img.shields.io/badge/🚀%20Ejecutable%20EXE-StarStream.exe%20(Escaneo%20automático)-059669?style=for-the-badge&logo=windows&logoColor=white" alt="Descargar StarStream.exe">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream_Browser_Extension_v3.2.1.zip">
    <img src="https://img.shields.io/badge/🧩%20Extensión%20Navegador-Extension_v3.2.1.zip%20(165%20KB)-7c3aed?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Descargar extensión">
  </a>
  &nbsp;&nbsp;
  <a href="#-comparativa-y-alternativas-por-qué-starstream">
    <img src="https://img.shields.io/badge/🔥%20Alternativa-CatCatch%20%7C%20SimpleG%20%7C%20yt--dlp-10b981?style=for-the-badge" alt="Comparativa y Alternativas">
  </a>
</p>

> [!IMPORTANT]
> ### 💡 Guía del Dúo Dorado: ¡El software de escritorio y la extensión trabajan juntos!
> - **🧩 Extensión de Rastreo (Radar Frontal)**: Intercepta y extrae automáticamente flujos reales M3U8, DASH (MPD) y MP4 mientras navega, mostrando una práctica cápsula de descarga sobre el reproductor;
> - **💻 Cliente de Escritorio (Motor Dorsal)**: Recibe las tareas enviadas por la extensión y coordina los motores integrados **N_m3u8DL-RE** y **FFmpeg** para descargas concurrentes de alta velocidad (hasta 24.7 MB/s) y fusión sin pérdidas;
> - **Sinergia Total (similar a IDM y su extensión)**: Ambos componentes son esenciales. Siga la [Guía de Instalación de la Extensión](#-guía-de-instalación-de-la-extensión-del-navegador).

<p align="center">
  <a href="#-demostración-y-capturas">Demostración</a> •
  <a href="#-versiones-y-descargas">Descargas</a> •
  <a href="#-características-principales">Características</a> •
  <a href="#-guía-de-instalación-de-la-extensión-del-navegador">Instalación</a> •
  <a href="#-preguntas-frecuentes-faq">FAQ</a> •
  <a href="#-descargo-de-responsabilidad">Descargo</a>
</p>

</div>

---

## 📸 Demostración y Capturas

### 1. Panel de control de escritorio (Diseño moderno Dark Slate)
> Iconos vectoriales nítidos y monitorización completa: Puerto local `18910` listo, `FFmpeg` listo, motor `N_m3u8DL (RE)` preparado e indicador de proxy de red en tiempo real.

<p align="center">
  <img src="docs/images/app_main_window.png" width="92%" alt="Captura del panel de control">
</p>

---

### 2. Nueva tarea de descarga (Configuración individual de proxy e hilos)
> Extracción y análisis de enlaces con un solo clic. Configuración de hilos concurrentes (4 a 32), carpetas de guardado y modos de proxy por tarea.

<p align="center">
  <img src="docs/images/app_new_task.png" width="82%" alt="Diálogo de nueva tarea">
</p>

---

### 3. Caja de herramientas multimedia FFmpeg (Conversión y edición)
> Estación de trabajo multimedia lista para usar: conversión individual y por lotes (MP4/MKV/TS/MOV), multiplexación de audio/vídeo, extracción de audio sin pérdidas y recorte rápido.

<p align="center">
  <img src="docs/images/app_ffmpeg_toolbox.png" width="82%" alt="Caja de herramientas FFmpeg">
</p>

---

### 4. Rastreo fluido de vídeos internacionales (Ejemplo YouTube)
> Una cápsula flotante no intrusiva aparece al reproducir vídeos web. Detecta resolución real y duración, enviando la tarea al escritorio mediante el mismo proxy.

<p align="center">
  <img src="docs/images/web_capsule_youtube.png" width="82%" alt="Cápsula de detección de YouTube">
</p>

---

### 5. Rastreo de vídeo web y envío directo (Alineación automática de proxy)
> Muestra resoluciones reales, duración y formato. Se alinea automáticamente con el proxy del navegador para descargar a máxima velocidad en el cliente de escritorio.

<p align="center">
  <img src="docs/images/web_capsule_bilibili.png" width="58%" alt="Tarjeta flotante del rastreador web">
</p>

---

### 6. Centro de monitoreo de tareas y herramientas rápidas
> Haga clic en la esfera flotante para expandir el panel: supervise descargas activas, velocidad global y abra el conversor, FFmpeg o el extractor de vídeo.

<p align="center">
  <img src="docs/images/app_floating_panel.png" width="68%" alt="Centro de monitoreo y herramientas">
</p>

---

### 7. Widget flotante de escritorio (Seguimiento en directo de tareas y velocidad)
> Widget esférico interactivo con arrastre libre por el escritorio, acoplamiento a los bordes y visualización en tiempo real de tareas listas y velocidad global.

<p align="center">
  <img src="docs/images/app_floating_widget.png" width="28%" alt="Widget flotante de escritorio">
</p>


## 📦 Versiones y Descargas (Releases)

Puede obtener la última versión oficial de StarStream a través de las siguientes opciones:

| Método de descarga | Componentes incluidos | Recomendado para | Enlace de descarga |
|---|---|---|---|
| **⭐ Recomendado: StarStream_v3.2.1_Portable.zip** | **StarStream.exe** + **N_m3u8DL-RE** + **FFmpeg** + Extensión integrados | **Muy recomendado sin FFmpeg / N_m3u8DL**, listo para usar sin configuración | [👉 Descargar Paquete Portátil](https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream_v3.2.1_Portable.zip) |
| **🚀 Versión Ejecutable: StarStream.exe (77.5MB)** | Binario ejecutable independiente | **Para usuarios que ya tienen FFmpeg o N_m3u8DL**, detecta herramientas; **colocar en carpeta limpia dedicada** | [👉 Descargar StarStream.exe](https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream.exe) |
| **🧩 Extensión para Navegador (v3.2.1)** | Código fuente de extensión (165 KB), rastreo MV3, sincronización de proxy | Captura de video web, interfaz clara, orden por duración | [👉 Descargar Extension.zip (165 KB)](https://github.com/xuewexin/StarStream/releases/download/v3.2.1/StarStream_Browser_Extension_v3.2.1.zip) |
| **Página Oficial de GitHub Releases** | Todas las versiones, registros de cambios y verificación de archivos | Historial completo de versiones | [👉 Visitar Releases](https://github.com/xuewexin/StarStream/releases) |

> 💡 **Guía de descarga e instalación (Aviso importante)**:
> 1. **Para usuarios sin FFmpeg o N_m3u8DL instalado**:
>    👉 **¡Se recomienda descargar el paquete portátil (`StarStream_v3.2.1_Portable.zip`)**! Incluye `ffmpeg.exe` y `N_m3u8DL-RE.exe` preconfigurados.
> 2. **Para usuarios que ya tienen FFmpeg o N_m3u8DL**:
>    👉 **¡Pueden descargar directamente el ejecutable independiente (`StarStream.exe`)**! StarStream escaneará automáticamente su sistema (`PATH`) para detectar las herramientas existentes.
> 3. **⚠️ Consejo importante**:
>    Si descargan la versión ejecutable `StarStream.exe`, **¡colóquenla en una carpeta nueva y limpia (ej: `D:\StarStream\`) antes de abrirla**! La aplicación creará archivos de configuración, base de datos y registros en su misma carpeta.

---

## ⚔️ Comparativa y Alternativas (¿Por qué StarStream?)

Comparativa entre StarStream, Cat-Catch, SimpleG, N_m3u8DL-RE, yt-dlp y Video DownloadHelper:

| Característica | 🌟 StarStream Pro | 🐱 Cat-Catch | 🛠️ SimpleG | ⚡ yt-dlp / CLI | 🦊 Video DownloadHelper |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Arquitectura** | **Cliente de escritorio + Extensión web** | Solo extensión | Programa de escritorio clásico | Consola de comandos (CLI) | Extensión + App complementaria |
| **Motor de descarga** | **N_m3u8DL-RE + FFmpeg integrados** | Descarga en navegador Blob/Fetch | N_m3u8DL-CLI antiguo | Motor yt-dlp Python | Descarga navegador / Servicio |
| **Multihilo de alta velocidad** | **✅ Compatible (4 ~ 32 hilos, 24MB/s+)** | ❌ Un solo hilo / Lento | ⚠️ Multihilo básico | Parámetros manuales | Requiere licencia de pago |
| **Sincronización de Proxy** | **✅ Alineación con IP del navegador (Evita 403)** | Solo proxy del navegador | ❌ No detecta proxy del navegador | Requiere parámetro `--proxy` | ❌ No disponible |
| **Cápsula en el reproductor** | **✅ Botón incrustado en el reproductor de video** | ❌ Requiere clic en la barra | ❌ Copia y pega manual de enlace | ❌ Solo consola de texto | Requiere clic en la barra |
| **Licencia** | **✅ 100% Gratuito y Código Abierto (MIT)** | Código abierto | Código abierto | Código abierto | Freemium con pagos |

---

## ⚡ Características Principales

| Módulo | Descripción |
|---|---|
| **Rastreador Universal** | Captura M3U8 (HLS), MPD (DASH), MP4, FLV, WebM, TS, MP3, AAC y enlaces directos. Intercepta `HTMLMediaElement.play`, `Blob`, `MediaSource`, `fetch/XHR`. |
| **Cápsula Flotante** | Botón incrustado en el reproductor que identifica resoluciones (4K/1080P/720P), duración y pistas de audio separadas. |
| **Reproductor Integrado** | Reproductor ligero `hls.min.js` en la ventana emergente de la extensión para previsualizar antes de descargar. |
| **Doble Motor** | **Streaming**: [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) para descarga segmentada y multiplexación.<br>**Enlace Directo**: Descargador Range multiproceso nativo en Python. |
| **Configuración por Video** | Carpeta de guardado personalizada, hilos (4/8/16/32) y proxy específico para cada video. |
| **Alineación de Proxy** | Sincroniza la IP de salida del descargador con la del navegador para evitar errores HTTP 403 Forbidden. |
| **Conversor de Formatos** | Centro de conversión por lotes: copia sin pérdidas (`-c copy`), recodificación H.264/H.265 y extracción de audio. |
| **Notificaciones de Escritorio** | Avisos emergentes en la esquina inferior derecha al completar o fallar descargas. |
| **Conversión Automática a MP4** | Remuxing automático con FFmpeg a formato MP4 estándar con metadatos `faststart`. |
| **Diagnóstico Inteligente** | Registra y analiza errores en `Logs/download_errors.log` para ofrecer recomendaciones inmediatas. |
| **Limpieza de Caché** | Busca y elimina fragmentos residuales `.tmp` y `.part` de descargas interrumpidas. |

---

## 🧩 Guía de Instalación de la Extensión del Navegador

### Paso 1: Abrir la página de extensiones
- **Microsoft Edge**: Ingrese `edge://extensions` en la barra de direcciones y presione Enter.
- **Google Chrome**: Ingrese `chrome://extensions` en la barra de direcciones y presione Enter.

### Paso 2: Activar el «Modo de desarrollador»
- En la esquina superior derecha, active el interruptor **Modo de desarrollador** (Developer mode).
- Aparecerá el botón **[Cargar extensión descomprimida]**.

### Paso 3: Seleccionar la carpeta de la extensión
1. Haga clic en **[Cargar extensión descomprimida]**.
2. Seleccione la carpeta **`m3u8-sniffer-extension`**.
3. Haga clic en "Seleccionar carpeta". ¡La extensión ya está instalada!
4. Fije **StarStream Media Sniffer** en su barra de herramientas.

---

## ⚖️ Descargo de Responsabilidad

1. **Investigación técnica y uso personal**: Este proyecto está destinado al estudio de protocolos de streaming y copias de seguridad personales legítimas.
2. **Propiedad intelectual**: Respete las leyes aplicables y los derechos de autor. Se prohíbe el uso comercial o redistribución no autorizada.
3. **Límite de responsabilidad**: Esta herramienta no aloja ni distribuye contenidos multimedia.

---

## 📄 Licencia

Licenciado bajo la [Licencia MIT](LICENSE). Agradecimientos a [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) y [FFmpeg](https://ffmpeg.org/).
---

## 📬 Contacto con el Autor y Soporte Técnico

Si encuentra algún problema, error, duda durante el uso, o tiene sugerencias de mejora y solicitudes de nuevas funciones, no dude en contactar al autor por correo electrónico:

- **Correo QQ**: [2792893068@qq.com](mailto:2792893068@qq.com)
- **Gmail**: [lepa23216@gmail.com](mailto:lepa23216@gmail.com)

¡Responderemos y atenderemos sus consultas y sugerencias lo antes posible! ¡Gracias por su apoyo y comentarios!

---

### 🏷️ Search Topics & SEO Keywords
`m3u8-downloader` • `video-downloader` • `catcatch-alternative` • `n-m3u8dl-re-gui` • `simpleg-upgrade` • `ffmpeg-gui` • `hls-stream-sniffer` • `dash-mpd-downloader` • `browser-extension` • `bilibili-video-download` • `douyin-watermark-free` • `chrome-video-extractor` • `yt-dlp-gui` • `stream-recorder` • `idm-alternative` • `media-downloader` • `video-sniffer` • `hls-downloader`

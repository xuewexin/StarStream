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
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.0/StarStream_v3.2.0_Portable.zip">
    <img src="https://img.shields.io/badge/⬇️%20Cliente%20de%20Escritorio-StarStream_v3.2.0_Portable.zip%20(Núcleo%20Integrado)-2563eb?style=for-the-badge&logo=windows&logoColor=white" alt="Descargar StarStream.exe">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.2.0/StarStream_Browser_Extension_v3.2.0.zip">
    <img src="https://img.shields.io/badge/🧩%20Extensión%20del%20Navegador-Extension.zip%20(Solo%20140KB)-059669?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Descargar Extensión del Navegador">
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

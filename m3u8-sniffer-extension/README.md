# CatCatch 灵猫嗅探 Pro — 浏览器扩展 (Chrome / Edge MV3)

模仿猫抓 (Cat Catch) 全部功能开发，具备深度音视频嗅探、IDM 风格悬浮下载栏、内置 HLS.js 视频预览与本地桌面客户端联动。

## 功能亮点

1. **全媒体格式深度嗅探**：
   - 流媒体：M3U8 (HLS)、MPD (DASH)
   - 视频：MP4、FLV、WebM、MKV、TS、AVI、MOV
   - 音频：MP3、M4A、AAC、WAV、OGG、FLAC
2. **双通道嗅探机制**：
   - URL 扩展名匹配
   - 响应头 `Content-Type` 嗅探（捕捉无文件后缀的动态视频流与文件大小）
3. **网页注入深度 Hook**：
   - 监听 `HTMLMediaElement.prototype.play` 与 `src`
   - 拦截 `MediaSource` 与 `URL.createObjectURL`（定位 Blob 流）
   - 拦截 `fetch` 与 `XMLHttpRequest`
4. **IDM 风格网页悬浮下载按钮**：
   - 播放视频时智能在播放器右上角浮现 `[⬇ 下载此视频 (CatCatch)]`，一键推送到桌面客户端下载
5. **弹窗媒体预览播放器**：
   - 内置离线版 `hls.min.js`，弹窗内直接播放预览 M3U8 流媒体
6. **与本地灵猫桌面客户端无缝联动**：
   - 通过本地轻量级 HTTP API (`http://127.0.0.1:18910`) 与客户端双向通信
   - 支持批量推送下载、实时在线心跳感知
   - 兼容 Chrome Native Messaging 机制

## 快速加载

1. 打开 Chrome 访问 `chrome://extensions/`（或 Edge 访问 `edge://extensions/`）
2. 打开右上角「**开发者模式**」
3. 点击「**加载已解压的扩展程序**」
4. 选择本目录 `m3u8-sniffer-extension` 即可

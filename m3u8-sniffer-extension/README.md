# CatCatch 灵猫嗅探 Pro — 浏览器扩展 (Chrome / Edge MV3)

模仿猫抓 (CatCatch) 深度嗅探逻辑开发，具备深度音视频嗅探、DASH 音视频双流自动配对、安全风控/人机验证异常穿透报告、IDM 风格悬浮下载栏、内置 HLS.js 视频预览与本地桌面客户端联动。

## 功能亮点

1. **全媒体格式深度嗅探与音画合一配对**：
   - 流媒体：M3U8 (HLS)、MPD / M4S (DASH 音视频双流)
   - 视频：MP4、FLV、WebM、MKV、TS、AVI、MOV
   - 音频：MP3、M4A、AAC、WAV、OGG、FLAC
   - **B站 / DASH 智能配对**：自动捕获独立高清视频轨与独立高品质音频轨，在前端毫秒级智能配对生成「【音画合一】」条目，支持双轨同步预览并在推送到客户端后通过 FFmpeg 100% 混流封装为有声 MP4。
2. **安全风控与人机验证穿透报告（打破浏览器人机验证）**：
   - 自动检测 HTTP 412 (Precondition Failed)、`sec.bilibili.com`、极验滑动验证、Cloudflare Turnstile 拦截
   - 插件弹窗顶部展示高危风控横幅，支持一键打开网页验证，在浏览器完成人机挑战后一键同步最新 Cookie/Token 回传客户端，立即复活断点续传。
3. **真实浏览器指纹动态同步**：
   - 破除固定写死配置，动态跟随当前嗅探浏览器的 User-Agent 与 Client Hints，实现与浏览器网络环境 100% 对齐。
4. **双通道嗅探机制**：
   - URL 扩展名匹配
   - 响应头 `Content-Type` 嗅探（捕捉无文件后缀的动态视频流与文件大小）
5. **网页注入深度 Hook**：
   - 监听 `HTMLMediaElement.prototype.play` 与 `src`
   - 拦截 `MediaSource` 与 `URL.createObjectURL`（定位 Blob 流）
   - 拦截 `fetch` 与 `XMLHttpRequest`
6. **IDM 风格网页悬浮下载按钮**：
   - 播放视频时智能在播放器右上角浮现 `[⬇ 下载此视频 (CatCatch)]`，一键推送到桌面客户端下载。
7. **弹窗媒体预览播放器**：
   - 内置离线版 `hls.min.js`，弹窗内直接播放预览 M3U8 流媒体，支持音画双流同屏同步播放。
8. **与本地灵猫桌面客户端无缝联动**：
   - 通过本地轻量级 HTTP API (`http://127.0.0.1:18910`) 与客户端双向通信
   - 支持批量推送下载、实时在线心跳感知
   - 兼容 Chrome Native Messaging 机制

## 快速加载

1. 打开 Chrome 访问 `chrome://extensions/`（或 Edge 访问 `edge://extensions/`）
2. 打开右上角「**开发者模式**」
3. 点击「**加载已解压的扩展程序**」
4. 选择本目录 `m3u8-sniffer-extension` 即可

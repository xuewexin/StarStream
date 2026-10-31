// inject.js - CatCatch In-Page Deep Sniffer & DOM Hooks (仅抓取完整视频流，坚决过滤碎片切片)
(function () {
  'use strict';
  if (window.__CATCATCH_INJECTED__) return;
  window.__CATCATCH_INJECTED__ = true;

  // 仅匹配完整音视频与流媒体清单（移除 .ts，彻底防止切片风暴）
  const MEDIA_REGEX = /\.(m3u8|mpd|mp4|webm|flv|f4v|mkv|avi|mov|wmv|mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)/i;

  // 针对抖音/快手/B站/小红书等短视频无后缀 CDN 流的智能识别正则
  const SHORT_VIDEO_CDN_REGEX = /(douyinvod\.com|snssdk\.com|iesdouyin\.com|bilivideo\.(com|cn)|hdslb\.com|kwaicdn\.com|kwai\.net|xhscdn\.com)/i;

  // 严格过滤已知分片与临时碎片切片特征
  const FRAGMENT_REGEX = /(\.ts|\.m4s|\.m4v|\.vtt|\.srt|\.key|\.mp2t)(\?|#|$)|([-_/](seg|segment|chunk|frag|slice|part)[-_/\d]+)|(\b(init\.mp4|range=|\/stream\/segment))/i;

  function notifyMedia(data) {
    if (!data.url || data.url.startsWith('blob:') || data.url.startsWith('data:') || data.url.startsWith('chrome:')) {
      return; // 坚决丢弃 blob: 内部内存对象，只抓取真实网络流
    }
    if (FRAGMENT_REGEX.test(data.url)) {
      return; // 坚决丢弃切片分片，只抓取完整视频
    }
    try {
      window.postMessage({
        source: 'CATCATCH_INJECTOR',
        payload: {
          url: data.url,
          title: document.title || '',
          pageUrl: window.location.href,
          mediaType: data.mediaType || 'video',
          mimeType: data.mimeType || '',
          sourceType: data.sourceType || 'hook',
          timestamp: Date.now()
        }
      }, '*');
    } catch (e) {}
  }

  // 1. Hook HTMLMediaElement (Video / Audio 播放与属性设置，只捕获真实网络 URL)
  const origPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    try {
      const src = this.currentSrc || this.src;
      if (src && !src.startsWith('blob:') && !src.startsWith('data:') && !src.startsWith('chrome:') && !FRAGMENT_REGEX.test(src)) {
        const isAudio = this instanceof HTMLAudioElement || this.tagName.toLowerCase() === 'audio';
        notifyMedia({
          url: src,
          mediaType: isAudio ? 'audio' : 'video',
          sourceType: 'media_play'
        });
      }
    } catch (e) {}
    return origPlay.apply(this, arguments);
  };

  // Hook src setter (很多现代前端如 React/Vue 通过 el.src = url 动态赋值)
  const origSrcDesc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src');
  if (origSrcDesc && origSrcDesc.set) {
    Object.defineProperty(HTMLMediaElement.prototype, 'src', {
      set: function (val) {
        if (val && typeof val === 'string' && !val.startsWith('blob:') && !val.startsWith('data:') && !FRAGMENT_REGEX.test(val)) {
          if (MEDIA_REGEX.test(val) || SHORT_VIDEO_CDN_REGEX.test(val)) {
            const isAudio = this instanceof HTMLAudioElement || this.tagName.toLowerCase() === 'audio';
            notifyMedia({
              url: val,
              mediaType: isAudio ? 'audio' : 'video',
              sourceType: 'src_setter'
            });
          }
        }
        return origSrcDesc.set.call(this, val);
      },
      get: origSrcDesc.get,
      configurable: true
    });
  }

  // 2. Hook Fetch (捕获动态加载的 m3u8 / mpd / mp4 清单)
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    try {
      let url = '';
      if (typeof input === 'string') {
        url = input;
      } else if (input && input.url) {
        url = input.url;
      }
      if (url && MEDIA_REGEX.test(url) && !FRAGMENT_REGEX.test(url) && !url.startsWith('blob:')) {
        notifyMedia({
          url: url,
          sourceType: 'fetch'
        });
      }
    } catch (e) {}
    return origFetch.apply(this, arguments);
  };

  // 3. Hook XMLHttpRequest (捕获播放器 XHR 加载的流)
  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    try {
      if (url && typeof url === 'string' && MEDIA_REGEX.test(url) && !FRAGMENT_REGEX.test(url) && !url.startsWith('blob:')) {
        notifyMedia({
          url: url,
          sourceType: 'xhr'
        });
      }
    } catch (e) {}
    return origOpen.apply(this, arguments);
  };
})();

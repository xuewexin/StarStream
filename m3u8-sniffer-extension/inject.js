// inject.js - CatCatch In-Page Deep Sniffer & DOM Hooks
(function () {
  'use strict';
  if (window.__CATCATCH_INJECTED__) return;
  window.__CATCATCH_INJECTED__ = true;

  const MEDIA_REGEX = /\.(m3u8|mpd|mp4|webm|flv|f4v|mkv|ts|mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)/i;

  function notifyMedia(data) {
    if (!data.url || data.url.startsWith('blob:') || data.url.startsWith('data:') || data.url.startsWith('chrome:')) {
      return; // 坚决丢弃 blob: 内部内存对象，只抓取真实网络流
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
      if (src && !src.startsWith('blob:') && !src.startsWith('data:') && !src.startsWith('chrome:')) {
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
      if (url && MEDIA_REGEX.test(url) && !url.startsWith('blob:')) {
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
      if (url && typeof url === 'string' && MEDIA_REGEX.test(url) && !url.startsWith('blob:')) {
        notifyMedia({
          url: url,
          sourceType: 'xhr'
        });
      }
    } catch (e) {}
    return origOpen.apply(this, arguments);
  };
})();

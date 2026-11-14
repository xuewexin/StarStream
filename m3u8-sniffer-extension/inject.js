// inject.js - CatCatch In-Page Sniffer & DOM Hooks (精准捕获页面播放流，杜绝切片与垃圾广告干扰)
(function () {
  'use strict';
  if (window.__CATCATCH_INJECTED__) return;
  window.__CATCATCH_INJECTED__ = true;

  // 视音频及流媒体清单正则（清单永远放行）
  const PLAYLIST_REGEX = /\.(m3u8|mpd)(\?|#|$)/i;
  const MEDIA_REGEX = /\.(m3u8|mpd|mp4|webm|flv|f4v|mkv|avi|mov|wmv|mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)/i;

  // 针对主流短视频平台 CDN 流识别
  const SHORT_VIDEO_CDN_REGEX = /(douyinvod\.com|snssdk\.com|iesdouyin\.com|bilivideo\.(com|cn)|hdslb\.com|kwaicdn\.com|kwai\.net|xhscdn\.com)/i;

  function isBiliDashUrl(url) {
    if (!url) return false;
    return /(bilivideo\.(com|cn)|hdslb\.com|\/upgcxcode\/|\bgen=playurlv3\b|\b\d{6,14}-\d+-\d+\.m4s\b)/i.test(url);
  }

  // 严格过滤已知分片与切片特征 (过滤 .ts/.m4s 切片、Range 分段、init.mp4 初始化段)
  const FRAGMENT_REGEX = /(\.ts|\.m4s|\.m4v|\.vtt|\.srt|\.key|\.mp2t)(\?|#|$)|([-_/](seg|segment|chunk|frag|slice|part)[-_/\d]+)|(\b(init\.mp4|range=|\/stream\/segment))/i;

  function isFragment(url) {
    if (!url) return true;
    const clean = String(url).split('#')[0];
    if (PLAYLIST_REGEX.test(clean)) return false; // 媒体清单永远放行！
    if (isBiliDashUrl(clean)) return false; // B站完整DASH流绝非切片，放行！
    return FRAGMENT_REGEX.test(clean);
  }

  function notifyMedia(data) {
    if (!data.url || data.url.startsWith('blob:') || data.url.startsWith('data:') || data.url.startsWith('chrome:')) {
      return; // 坚决丢弃 blob: 内部内存对象，只抓取真实网络流
    }
    if (isFragment(data.url)) {
      return; // 坚决丢弃切片分片，只抓取完整视频
    }
    try {
      window.postMessage({
        source: 'CATCATCH_INJECTOR',
        payload: {
          url: data.url,
          audioUrl: data.audioUrl || '',
          title: document.title || '',
          pageUrl: window.location.href,
          referer: window.location.href,
          userAgent: navigator.userAgent,
          cookie: document.cookie || '',
          mediaType: data.mediaType || (PLAYLIST_REGEX.test(data.url) ? 'm3u8' : 'video'),
          mimeType: data.mimeType || '',
          sourceType: data.sourceType || 'hook',
          timestamp: Date.now()
        }
      }, '*');
    } catch (e) {}
  }

  // 1. Hook HTMLMediaElement (Video / Audio 播放与属性设置)
  const origPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    try {
      const src = this.currentSrc || this.src;
      if (src && !src.startsWith('blob:') && !src.startsWith('data:') && !src.startsWith('chrome:') && !isFragment(src)) {
        const isAudio = this instanceof HTMLAudioElement || this.tagName.toLowerCase() === 'audio';
        notifyMedia({
          url: src,
          mediaType: isAudio ? 'audio' : (PLAYLIST_REGEX.test(src) ? 'm3u8' : 'video'),
          sourceType: 'media_play'
        });
      }
    } catch (e) {}
    return origPlay.apply(this, arguments);
  };

  // Hook src setter (很多现代前端动态赋值 el.src = url)
  const origSrcDesc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src');
  if (origSrcDesc && origSrcDesc.set) {
    Object.defineProperty(HTMLMediaElement.prototype, 'src', {
      set: function (val) {
        if (val && typeof val === 'string' && !val.startsWith('blob:') && !val.startsWith('data:') && !isFragment(val)) {
          if (MEDIA_REGEX.test(val) || SHORT_VIDEO_CDN_REGEX.test(val)) {
            const isAudio = this instanceof HTMLAudioElement || this.tagName.toLowerCase() === 'audio';
            notifyMedia({
              url: val,
              mediaType: isAudio ? 'audio' : (PLAYLIST_REGEX.test(val) ? 'm3u8' : 'video'),
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

  // 2. Hook Hls.js (主流 H5 播放器核心)
  let hlsHooked = false;
  function hookHls() {
    if (hlsHooked) return;
    try {
      const H = window.Hls;
      if (H && H.prototype && H.prototype.loadSource && !H.prototype.__cc_wrapped) {
        const origLoadSource = H.prototype.loadSource;
        H.prototype.loadSource = function (url) {
          try {
            if (url && typeof url === 'string') {
              notifyMedia({
                url: url,
                mediaType: 'm3u8',
                sourceType: 'hls_loadSource'
              });
            }
          } catch (e) {}
          return origLoadSource.apply(this, arguments);
        };
        H.prototype.__cc_wrapped = true;
        hlsHooked = true;
      }
    } catch (e) {}
  }
  hookHls();
  let tries = 0;
  const hlsTimer = setInterval(() => {
    tries++;
    hookHls();
    if (hlsHooked || tries > 30) clearInterval(hlsTimer);
  }, 300);

  // 3. Hook Fetch (捕获播放器请求的 m3u8 / mpd / mp4 清单)
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    try {
      let url = '';
      if (typeof input === 'string') {
        url = input;
      } else if (input && input.url) {
        url = input.url;
      }
      if (url && (MEDIA_REGEX.test(url) || SHORT_VIDEO_CDN_REGEX.test(url)) && !isFragment(url) && !url.startsWith('blob:')) {
        notifyMedia({
          url: url,
          mediaType: PLAYLIST_REGEX.test(url) ? 'm3u8' : 'video',
          sourceType: 'fetch'
        });
      }
    } catch (e) {}
    return origFetch.apply(this, arguments);
  };

  // 4. Hook XMLHttpRequest (捕获播放器 XHR 加载的流)
  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    try {
      if (url && typeof url === 'string' && (MEDIA_REGEX.test(url) || SHORT_VIDEO_CDN_REGEX.test(url)) && !isFragment(url) && !url.startsWith('blob:')) {
        notifyMedia({
          url: url,
          mediaType: PLAYLIST_REGEX.test(url) ? 'm3u8' : 'video',
          sourceType: 'xhr'
        });
      }
    } catch (e) {}
    return origOpen.apply(this, arguments);
  };

  // 5. 深度扫描页面上所有媒体元素、分发源以及已加载的网络资源缓存
  function checkExistingMedia() {
    // 5.0 针对 B站 页面原生 __playinfo__ 进行音画双轨嗅探
    try {
      const pi = window.__playinfo__;
      if (pi && pi.data && pi.data.dash) {
        const dash = pi.data.dash;
        const videos = dash.video || [];
        const audios = dash.audio || [];
        if (videos.length > 0) {
          const bestVideo = videos.reduce((prev, curr) => ((curr.id || 0) > (prev.id || 0) ? curr : prev), videos[0]);
          const bestAudio = audios.length > 0 ? audios.reduce((prev, curr) => ((curr.id || 0) > (prev.id || 0) ? curr : prev), audios[0]) : null;
          const vUrl = bestVideo.baseUrl || bestVideo.base_url || '';
          const aUrl = bestAudio ? (bestAudio.baseUrl || bestAudio.base_url || '') : '';
          if (vUrl) {
            notifyMedia({
              url: vUrl,
              audioUrl: aUrl,
              mediaType: 'bili_dash',
              sourceType: 'bili_playinfo'
            });
          }
        }
      }
    } catch (e) {}

    // 5.1 扫描 performance 资源加载记录 (捕获在 inject.js 运行前就已经发出的所有网络流)
    try {
      if (window.performance && typeof window.performance.getEntriesByType === 'function') {
        const resources = window.performance.getEntriesByType('resource');
        for (let i = 0; i < resources.length; i++) {
          const u = resources[i].name;
          if (u && (MEDIA_REGEX.test(u) || SHORT_VIDEO_CDN_REGEX.test(u)) && !isFragment(u) && !u.startsWith('blob:')) {
            notifyMedia({
              url: u,
              mediaType: PLAYLIST_REGEX.test(u) ? 'm3u8' : 'video',
              sourceType: 'performance_resource'
            });
          }
        }
      }
    } catch (e) {}

    // 5.2 扫描 DOM 中的 video, audio, source 标签
    try {
      document.querySelectorAll('video, audio').forEach((el) => {
        const src = el.currentSrc || el.src;
        if (src && !src.startsWith('blob:') && !src.startsWith('data:') && !isFragment(src)) {
          notifyMedia({
            url: src,
            mediaType: el.tagName.toLowerCase() === 'audio' ? 'audio' : (PLAYLIST_REGEX.test(src) ? 'm3u8' : 'video'),
            sourceType: 'dom_element'
          });
        }
        el.querySelectorAll('source').forEach((s) => {
          const sSrc = s.src || s.getAttribute('src');
          if (sSrc && !sSrc.startsWith('blob:') && !sSrc.startsWith('data:') && !isFragment(sSrc)) {
            notifyMedia({
              url: sSrc,
              mediaType: PLAYLIST_REGEX.test(sSrc) ? 'm3u8' : 'video',
              sourceType: 'dom_source'
            });
          }
        });
      });
    } catch (e) {}

    // 5.3 扫描 iframe 引用
    try {
      document.querySelectorAll('iframe').forEach((ifr) => {
        try {
          const iSrc = ifr.src || ifr.getAttribute('src');
          if (iSrc && (MEDIA_REGEX.test(iSrc) || PLAYLIST_REGEX.test(iSrc)) && !isFragment(iSrc)) {
            notifyMedia({
              url: iSrc,
              mediaType: PLAYLIST_REGEX.test(iSrc) ? 'm3u8' : 'video',
              sourceType: 'dom_iframe'
            });
          }
        } catch (e) {}
      });
    } catch (e) {}
  }

  // 监听来自扩展弹窗的手动深度重新嗅探指令
  window.addEventListener('message', (event) => {
    if (event.data && event.data.action === 'CATCATCH_DO_RESNIFF') {
      checkExistingMedia();
    }
  });

  // 监听页面播放事件
  document.addEventListener('play', (e) => {
    try {
      const el = e.target;
      if (el && (el.tagName === 'VIDEO' || el.tagName === 'AUDIO')) {
        const src = el.currentSrc || el.src;
        if (src && !src.startsWith('blob:') && !src.startsWith('data:') && !isFragment(src)) {
          notifyMedia({
            url: src,
            mediaType: el.tagName.toLowerCase() === 'audio' ? 'audio' : (PLAYLIST_REGEX.test(src) ? 'm3u8' : 'video'),
            sourceType: 'event_play'
          });
        }
      }
    } catch (e) {}
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkExistingMedia);
  } else {
    checkExistingMedia();
  }
})();

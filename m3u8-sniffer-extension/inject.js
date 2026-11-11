// inject.js - 页面主世界 (MAIN world) 深度嗅探引擎
// 相比旧版新增：
//  1. 精确分片识别，不再误杀 .../part_1080/master.m3u8 这类真实清单
//  2. 读取 XHR / fetch 响应正文（很多站点的播放地址由 API 以 JSON 返回）
//  3. 深度扫描页面源码、内联脚本、data-* 属性、performance 资源表、
//     同源 iframe 以及页面 JS 全局变量（猫抓"深度搜索"的同款能力）
//  4. 上报页面自身的 Referer / UA / Cookie，供下载与在线预览防盗链使用
(function () {
  'use strict';
  if (window.__CATCATCH_INJECTED__) return;
  window.__CATCATCH_INJECTED__ = true;

  const PLAYLIST_RE = /\.(m3u8|mpd)(\?|#|$)/i;
  const MEDIA_RE = /\.(m3u8|mpd|mp4|webm|flv|f4v|mkv|avi|mov|wmv|mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)/i;
  const SEGMENT_RE = /\.(ts|m4s|m4v|mp2t|cmfv|cmfa|vtt|srt|ass|key)(\?|#|$)/i;
  const SHORT_CDN_RE = /(douyinvod\.com|snssdk\.com|iesdouyin\.com|bilivideo\.(com|cn)|hdslb\.com|kwaicdn\.com|kwai\.net|xhscdn\.com)/i;
  const PLAYLISH_KEY_RE = /(playlist|master|m3u8|manifest|\.mpd|hls|\/dash\/)/i;

  function isFragmentUrl(url) {
    if (!url) return true;
    const clean = String(url).split('#')[0];
    if (PLAYLIST_RE.test(clean)) return false;
    if (SEGMENT_RE.test(clean)) return true;
    if (/(^|\/)(init\.mp4|init\.m4s)$/i.test(clean.split('?')[0])) return true;
    if (/(^|\/)(segment|chunk|frag|seg|part)[-_.]?\d+\.(ts|m4s|mp4|m4v)/i.test(clean)) return true;
    return false;
  }

  const seenUrls = new Set();
  const scannedResponses = new Set();
  let scanCount = 0;

  function getContext() {
    return {
      pageUrl: location.href,
      referer: location.href,
      userAgent: navigator.userAgent,
      cookie: document.cookie || '',
      title: document.title || ''
    };
  }

  function emit(urls, sourceType) {
    const unique = [...new Set(urls)].filter((u) => {
      if (!u || isFragmentUrl(u) || seenUrls.has(u)) return false;
      seenUrls.add(u);
      return true;
    }).slice(0, 80);
    if (!unique.length) return;
    try {
      window.postMessage({
        source: 'CATCATCH_INJECTOR',
        payload: Object.assign({
          urls: unique,
          url: unique[0],
          sourceType: sourceType || 'hook',
          timestamp: Date.now()
        }, getContext())
      }, '*');
    } catch (e) {}
  }

  function notifyOne(url, sourceType) {
    if (!url || isFragmentUrl(url) || url.startsWith('blob:') || url.startsWith('data:')) return;
    if (!PLAYLIST_RE.test(url) && !MEDIA_RE.test(url) && !SHORT_CDN_RE.test(url)) return;
    try {
      window.postMessage({
        source: 'CATCATCH_INJECTOR',
        payload: Object.assign({
          url: url,
          urls: [url],
          mediaType: /\.mp3|\.m4a|\.aac|\.wav|\.ogg|\.flac|\.opus/i.test(url) ? 'audio' : 'video',
          sourceType: sourceType || 'hook',
          timestamp: Date.now()
        }, getContext())
      }, '*');
    } catch (e) {}
  }

  // 从任意文本里挖出媒体直链（兼容 JS 字符串里的 \/ 转义、\u002F、HTML 实体）
  function extractMediaUrls(text) {
    if (!text || typeof text !== 'string') return [];
    let s = text.length > 3000000 ? text.slice(0, 3000000) : text;
    s = s.replace(/\\\//g, '/').replace(/\\u002[fF]/g, '/').replace(/&amp;/g, '&');
    const re = /https?:\/\/[^\s"'`<>\\\[\]{}|;]{8,700}/gi;
    const out = new Set();
    let m;
    while ((m = re.exec(s)) !== null) {
      let u = m[0].replace(/[)\],.;'"]+$/, '');
      if (isFragmentUrl(u)) continue;
      if (PLAYLIST_RE.test(u) || MEDIA_RE.test(u) || SHORT_CDN_RE.test(u) || PLAYLISH_KEY_RE.test(u)) {
        out.add(u);
        if (out.size >= 60) break;
      }
    }
    return [...out];
  }

  function reportText(text, sourceType) {
    if (!text || text.length < 12 || text.length > 2000000) return;
    if (!/m3u8|mpd|playlist|master\.|\.mp4|hls|dash|stream|source|video_url|play_url/i.test(text)) return;
    const urls = extractMediaUrls(text);
    if (urls.length) emit(urls, sourceType);
  }

  function safeStringify(value) {
    const seen = new WeakSet();
    return JSON.stringify(value, (key, val) => {
      if (typeof val === 'string' && val.length > 8000) return val.slice(0, 8000);
      if (val && typeof val === 'object') {
        if (seen.has(val)) return undefined;
        seen.add(val);
      }
      if (typeof val === 'function') return undefined;
      return val;
    });
  }

  // ---------------- 页面深度扫描 ----------------
  function deepScan(reason) {
    if (scanCount > 24) return;
    scanCount++;
    const found = new Set();
    const add = (t) => { extractMediaUrls(t).forEach((u) => found.add(u)); };

    try { add(document.documentElement.outerHTML); } catch (e) {}

    try {
      document.querySelectorAll('script').forEach((s) => {
        if (s.textContent) add(s.textContent);
        if (s.src && !isFragmentUrl(s.src) && PLAYLIST_RE.test(s.src)) found.add(s.src);
      });
    } catch (e) {}

    try {
      document.querySelectorAll('source[src],video[src],audio[src],iframe[src],[data-url],[data-src],[data-hls],[data-m3u8],[data-video],[data-source],[data-config],[data-player],[data-poster]').forEach((el) => {
        for (const a of el.attributes) {
          if (a.value && a.value.length < 20000 && /https?:|m3u8|mpd|mp4/i.test(a.value)) add(a.value);
        }
      });
    } catch (e) {}

    try {
      performance.getEntriesByType('resource').forEach((e) => {
        if (e.name && !isFragmentUrl(e.name) && (PLAYLIST_RE.test(e.name) || MEDIA_RE.test(e.name) || SHORT_CDN_RE.test(e.name))) {
          found.add(e.name);
        }
      });
    } catch (e) {}

    // MAIN world 特权：直接读取页面 JS 自己定义的全局配置对象
    const KEYS = [
      '__NUXT__', '__INITIAL_STATE__', '__NEXT_DATA__', '__APOLLO_STATE__', '__DATA__', '__PAGE_DATA__',
      'playerConfig', 'videoData', 'videoInfo', 'video_url', 'playUrl', 'playurl', 'playlist',
      'config', 'player', '_player', 'video', 'sources', 'source', 'm3u8', 'hlsUrl', 'streamUrl'
    ];
    for (const k of KEYS) {
      try {
        const v = window[k];
        if (v == null) continue;
        const s = typeof v === 'string' ? v : (typeof v === 'object' ? safeStringify(v) : '');
        if (s) add(s);
      } catch (e) {}
    }

    // 扫描 window 自有属性：不少站点把地址挂在自定义全局变量上
    try {
      let objCount = 0;
      for (const k of Object.getOwnPropertyNames(window)) {
        if (k.length > 60) continue;
        let v;
        try { v = window[k]; } catch (e) { continue; }
        if (typeof v === 'string') {
          if (v.length > 16 && v.length < 200000 && /(m3u8|mpd|https?:\/\/|\.mp4)/i.test(v)) add(v);
        } else if (v && typeof v === 'object' && objCount < 40 && /play|video|stream|source|config|hls|media|m3u8/i.test(k)) {
          objCount++;
          try { const s = safeStringify(v); if (s) add(s); } catch (e) {}
        }
      }
    } catch (e) {}

    // 同源 iframe（跨域 iframe 由该 frame 内自己的 content script 覆盖）
    try {
      document.querySelectorAll('iframe').forEach((f) => {
        try {
          if (f.contentDocument && f.contentDocument.documentElement) {
            add(f.contentDocument.documentElement.outerHTML);
          }
        } catch (e) {}
      });
    } catch (e) {}

    if (found.size) emit([...found], reason || 'deep_scan');
  }

  // ---------------- 请求 Hook ----------------
  const origPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    try {
      const src = this.currentSrc || this.src;
      if (src) notifyOne(src, 'media_play');
    } catch (e) {}
    return origPlay.apply(this, arguments);
  };

  const origSrcDesc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src');
  if (origSrcDesc && origSrcDesc.set) {
    Object.defineProperty(HTMLMediaElement.prototype, 'src', {
      set: function (val) {
        if (typeof val === 'string') notifyOne(val, 'src_setter');
        return origSrcDesc.set.call(this, val);
      },
      get: origSrcDesc.get,
      configurable: true
    });
  }

  // hls.js / 播放器实例：master playlist 往往只传给 loadSource，不一定走常规 XHR
  let hlsWrapped = false;
  let wrapTries = 0;
  function tryWrapPlayer() {
    if (hlsWrapped || wrapTries > 30) return;
    wrapTries++;
    try {
      const H = window.Hls;
      if (H && H.prototype && H.prototype.loadSource && !H.prototype.__cc_wrapped) {
        const orig = H.prototype.loadSource;
        H.prototype.loadSource = function (u) {
          try { notifyOne(String(u), 'hls_loadSource'); } catch (e) {}
          return orig.apply(this, arguments);
        };
        H.prototype.__cc_wrapped = true;
        hlsWrapped = true;
      }
    } catch (e) {}
  }

  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    let url = '';
    try {
      url = typeof input === 'string' ? input : (input && input.url) || '';
      if (url) notifyOne(url, 'fetch');
    } catch (e) {}

    const p = origFetch.apply(this, arguments);

    // 检查疑似"播放配置 API"的响应正文，里面常藏着各清晰度 m3u8
    if (url && p && typeof p.then === 'function' && !scannedResponses.has(url) &&
        !SEGMENT_RE.test(url) && !/\.(mp4|webm|flv|mkv|avi|mov)(\?|$)/i.test(url) &&
        /(api|play|video|source|config|stream|m3u8|hls|dash|detail|info|manifest)/i.test(url)) {
      scannedResponses.add(url);
      if (scannedResponses.size > 300) scannedResponses.clear();
      p.then((res) => {
        try {
          const ct = (res.headers && res.headers.get('content-type')) || '';
          if (!/(json|javascript|text|xml)/i.test(ct)) return;
          const clone = res.clone();
          clone.text().then((t) => reportText(t, 'fetch_body')).catch(() => {});
        } catch (e) {}
      }).catch(() => {});
    }
    return p;
  };

  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    try {
      if (typeof url === 'string') notifyOne(url, 'xhr');
      this.__cc_url = String(url || '');
    } catch (e) {}
    return origOpen.apply(this, arguments);
  };

  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    try {
      const u = this.__cc_url || '';
      if (u && !scannedResponses.has(u) && !SEGMENT_RE.test(u) &&
          /(api|play|video|source|config|stream|m3u8|hls|dash|detail|info|manifest)/i.test(u)) {
        scannedResponses.add(u);
        this.addEventListener('load', () => {
          try {
            const ct = (this.getResponseHeader && this.getResponseHeader('content-type')) || '';
            if (!/(json|javascript|text|xml)/i.test(ct)) return;
            if (this.responseType && this.responseType !== 'text' && this.responseType !== '') return;
            reportText(this.responseText, 'xhr_body');
          } catch (e) {}
        }, { once: true });
      }
    } catch (e) {}
    return origSend.apply(this, arguments);
  };

  // ---------------- 触发时机 ----------------
  [600, 2000, 5000, 10000].forEach((ms) => {
    setTimeout(() => { tryWrapPlayer(); deepScan('scan_' + ms); }, ms);
  });
  tryWrapPlayer();

  function bindScanEvents() {
    document.addEventListener('DOMContentLoaded', () => deepScan('dom_ready'));
    window.addEventListener('load', () => deepScan('window_load'));
    document.addEventListener('play', () => {
      deepScan('play');
      setTimeout(() => deepScan('play_delay'), 1600);
    }, true);

    let timer = null;
    try {
      const mo = new MutationObserver(() => {
        if (timer) return;
        timer = setTimeout(() => { timer = null; deepScan('mutation'); }, 2000);
      });
      mo.observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['src', 'data-src', 'data-url', 'data-config', 'data-video', 'data-source']
      });
    } catch (e) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindScanEvents);
  } else {
    bindScanEvents();
  }
})();

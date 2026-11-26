// inject.js - CatCatch In-Page Deep Media Sniffer & DOM Engine (猫抓同款深度媒体嗅探与多源挂载核心)
(function () {
  'use strict';
  if (window.__CATCATCH_INJECTED__) return;
  window.__CATCATCH_INJECTED__ = true;

  // 1. 媒体核心正则定义
  const PLAYLIST_REGEX = /\.(m3u8|mpd)(\?|#|$)/i;
  const AUDIO_REGEX = /\.(mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)|302\d{2}\.m4s|mime(?:_type)?=audio|\/ies-music\/|douyinstatic\.com.*\.(mp3|m4a)/i;
  const MEDIA_REGEX = /\.(m3u8|mpd|mp4|webm|flv|f4v|mkv|avi|mov|wmv|mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)/i;
  const SHORT_VIDEO_CDN_REGEX = /(douyinvod\.com|snssdk\.com|iesdouyin\.com|douyinstatic\.com|bilivideo\.(com|cn)|hdslb\.com|kwaicdn\.com|kwai\.net|xhscdn\.com|weibo\.com\/.*\.mp4)/i;
  const STREAM_KEYWORD_REGEX = /((\.m3u8|\.mpd|\.flv|\.mp4|\.m4s|manifest|\/dash\/|\/hls\/|\/playlist|\/master)([\?&#\/]|$))|(\b(playurl|play_url|videoplayurl|getvideo|getstream)\b)/i;

  function guessMediaType(url) {
    if (PLAYLIST_REGEX.test(url)) return 'm3u8';
    if (AUDIO_REGEX.test(url)) return 'audio';
    return 'video';
  }

  function isBiliDashUrl(url) {
    if (!url) return false;
    return /(bilivideo\.(com|cn)|hdslb\.com|\/upgcxcode\/|\bgen=playurlv3\b|bilibili\.com|\b\d{6,14}.*?\.m4s\b)/i.test(url);
  }

  function isFragment(url) {
    if (!url) return true;
    const clean = String(url).split('#')[0];
    if (PLAYLIST_REGEX.test(clean)) return false; // 清单永远放行
    if (isBiliDashUrl(clean)) return false; // B站DASH轨道为完整媒体，放行
    if (/(^|\/)(init\.mp4|init\.m4s)$/i.test(clean.split('?')[0])) return true;
    if (/(^|\/)(segment|chunk|frag|seg|part)[-_.]?\d+\.(ts|m4s|mp4|m4v)/i.test(clean)) return true;
    if (/\/stream\/segment\//i.test(clean)) return true;
    return false;
  }

  const notifiedUrls = new Set();

  function notifyMedia(data) {
    if (!data || !data.url) return;
    const url = data.url;
    if (url.startsWith('blob:') || url.startsWith('data:') || url.startsWith('chrome:') || url.startsWith('javascript:')) {
      return;
    }
    if (isFragment(url)) {
      return;
    }

    const cacheKey = `${url}|${data.audioUrl || ''}`;
    if (notifiedUrls.has(cacheKey)) {
      return;
    }
    notifiedUrls.add(cacheKey);
    if (notifiedUrls.size > 300) {
      const first = notifiedUrls.values().next().value;
      notifiedUrls.delete(first);
    }

    try {
      window.postMessage({
        source: 'CATCATCH_INJECTOR',
        payload: {
          url: url,
          audioUrl: data.audioUrl || '',
          title: data.title || document.title || '',
          pageUrl: window.location.href,
          referer: window.location.href,
          userAgent: navigator.userAgent,
          cookie: document.cookie || '',
          mediaType: data.mediaType || (PLAYLIST_REGEX.test(url) ? 'm3u8' : (data.audioUrl ? 'bili_dash' : 'video')),
          mimeType: data.mimeType || '',
          sourceType: data.sourceType || 'hook',
          timestamp: Date.now()
        }
      }, '*');
    } catch (e) {}
  }

  // 2. Hook HTMLMediaElement (Video / Audio 播放与属性赋值)
  const origPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    try {
      const src = this.currentSrc || this.src;
      if (src && !src.startsWith('blob:') && !src.startsWith('data:') && !isFragment(src)) {
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

  const origLoad = HTMLMediaElement.prototype.load;
  HTMLMediaElement.prototype.load = function () {
    try {
      const src = this.currentSrc || this.src;
      if (src && !src.startsWith('blob:') && !src.startsWith('data:') && !isFragment(src)) {
        const isAudio = this instanceof HTMLAudioElement || this.tagName.toLowerCase() === 'audio';
        notifyMedia({
          url: src,
          mediaType: isAudio ? 'audio' : (PLAYLIST_REGEX.test(src) ? 'm3u8' : 'video'),
          sourceType: 'media_load'
        });
      }
    } catch (e) {}
    return origLoad.apply(this, arguments);
  };

  const origSrcDesc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src');
  if (origSrcDesc && origSrcDesc.set) {
    Object.defineProperty(HTMLMediaElement.prototype, 'src', {
      set: function (val) {
        if (val && typeof val === 'string' && !val.startsWith('blob:') && !val.startsWith('data:') && !isFragment(val)) {
          if (MEDIA_REGEX.test(val) || SHORT_VIDEO_CDN_REGEX.test(val) || STREAM_KEYWORD_REGEX.test(val)) {
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

  // 3. Hook Source 标签赋值
  const origSourceSrc = Object.getOwnPropertyDescriptor(HTMLSourceElement.prototype, 'src');
  if (origSourceSrc && origSourceSrc.set) {
    Object.defineProperty(HTMLSourceElement.prototype, 'src', {
      set: function (val) {
        if (val && typeof val === 'string' && !val.startsWith('blob:') && !val.startsWith('data:') && !isFragment(val)) {
          notifyMedia({
            url: val,
            mediaType: PLAYLIST_REGEX.test(val) ? 'm3u8' : 'video',
            sourceType: 'source_src_setter'
          });
        }
        return origSourceSrc.set.call(this, val);
      },
      get: origSourceSrc.get,
      configurable: true
    });
  }

  // 4. Hook Fetch (全量网络嗅探，支持 URL匹配 + Content-Type检测 + Magic Header识别)
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    let reqUrl = '';
    if (typeof input === 'string') {
      reqUrl = input;
    } else if (input && input.url) {
      reqUrl = input.url;
    }

    if (reqUrl && (MEDIA_REGEX.test(reqUrl) || SHORT_VIDEO_CDN_REGEX.test(reqUrl) || STREAM_KEYWORD_REGEX.test(reqUrl)) && !isFragment(reqUrl) && !reqUrl.startsWith('blob:')) {
      notifyMedia({
        url: reqUrl,
        mediaType: guessMediaType(reqUrl),
        sourceType: 'fetch_url'
      });
    }

    const p = origFetch.apply(this, arguments);
    p.then((res) => {
      try {
        if (!res || !res.headers) return;
        const ctype = (res.headers.get('content-type') || '').toLowerCase();
        const finalUrl = res.url || reqUrl;
        if (!finalUrl || finalUrl.startsWith('blob:') || isFragment(finalUrl)) return;

        if (ctype.includes('mpegurl') || ctype.includes('dash+xml') || ctype.startsWith('video/') || ctype.startsWith('audio/')) {
          notifyMedia({
            url: finalUrl,
            mediaType: (ctype.includes('mpegurl') || PLAYLIST_REGEX.test(finalUrl)) ? 'm3u8' : (ctype.startsWith('audio/') ? 'audio' : 'video'),
            mimeType: ctype,
            sourceType: 'fetch_content_type'
          });
        } else if (ctype.includes('octet-stream') || ctype.includes('text/plain') || !ctype) {
          // 猫抓核心逻辑：克隆并嗅探响应前缀，若为 #EXTM3U 清单则放行
          res.clone().text().then((text) => {
            if (text && text.trim().startsWith('#EXTM3U')) {
              notifyMedia({
                url: finalUrl,
                mediaType: 'm3u8',
                sourceType: 'fetch_magic_m3u8'
              });
            } else if (text && text.includes('<MPD') && text.includes('xmlns="urn:mpeg:dash:schema:mpd:2011"')) {
              notifyMedia({
                url: finalUrl,
                mediaType: 'mpd',
                sourceType: 'fetch_magic_mpd'
              });
            }
          }).catch(() => {});
        }
      } catch (e) {}
    }).catch(() => {});
    return p;
  };

  // 5. Hook XMLHttpRequest (全量 XHR 监听与 Magic Header 分析)
  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__catcatch_url = url;
    try {
      if (url && typeof url === 'string' && (MEDIA_REGEX.test(url) || SHORT_VIDEO_CDN_REGEX.test(url) || STREAM_KEYWORD_REGEX.test(url)) && !isFragment(url) && !url.startsWith('blob:')) {
        notifyMedia({
          url: url,
          mediaType: guessMediaType(url),
          sourceType: 'xhr_url'
        });
      }
    } catch (e) {}
    return origOpen.apply(this, arguments);
  };

  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (data) {
    this.addEventListener('load', function () {
      try {
        const u = this.__catcatch_url || this.responseURL;
        if (!u || u.startsWith('blob:') || isFragment(u)) return;
        const ctype = (this.getResponseHeader('Content-Type') || '').toLowerCase();
        if (ctype.includes('mpegurl') || ctype.includes('dash+xml') || ctype.startsWith('video/') || ctype.startsWith('audio/')) {
          notifyMedia({
            url: u,
            mediaType: (ctype.includes('mpegurl') || PLAYLIST_REGEX.test(u)) ? 'm3u8' : (ctype.startsWith('audio/') ? 'audio' : 'video'),
            mimeType: ctype,
            sourceType: 'xhr_content_type'
          });
        } else {
          const prefix = typeof this.responseText === 'string' ? this.responseText.substring(0, 240).trim() : '';
          if (prefix.startsWith('#EXTM3U')) {
            notifyMedia({
              url: u,
              mediaType: 'm3u8',
              sourceType: 'xhr_magic_m3u8'
            });
          } else if (prefix.includes('<MPD') && prefix.includes('mpd')) {
            notifyMedia({
              url: u,
              mediaType: 'mpd',
              sourceType: 'xhr_magic_mpd'
            });
          }
        }
      } catch (e) {}
    });
    return origSend.apply(this, arguments);
  };

  // 6. Hook 业界主流 H5 播放器核心库 (Hls.js, Flv.js, Dash.js, DPlayer)
  function hookPlayerLibraries() {
    try {
      if (window.Hls && window.Hls.prototype && !window.Hls.prototype.__cc_wrapped) {
        const origHls = window.Hls.prototype.loadSource;
        window.Hls.prototype.loadSource = function (url) {
          if (url && typeof url === 'string') {
            notifyMedia({ url, mediaType: 'm3u8', sourceType: 'hls_js' });
          }
          return origHls.apply(this, arguments);
        };
        window.Hls.prototype.__cc_wrapped = true;
      }
    } catch (e) {}

    try {
      if (window.flvjs && !window.flvjs.__cc_wrapped) {
        const origFlv = window.flvjs.createPlayer;
        window.flvjs.createPlayer = function (mediaDataSource, config) {
          if (mediaDataSource && mediaDataSource.url) {
            notifyMedia({ url: mediaDataSource.url, mediaType: 'video', sourceType: 'flv_js' });
          }
          return origFlv.apply(this, arguments);
        };
        window.flvjs.__cc_wrapped = true;
      }
    } catch (e) {}

    try {
      if (window.dashjs && window.dashjs.MediaPlayer && !window.dashjs.__cc_wrapped) {
        const origDash = window.dashjs.MediaPlayer.prototype.attachSource;
        if (origDash) {
          window.dashjs.MediaPlayer.prototype.attachSource = function (url) {
            if (url && typeof url === 'string') {
              notifyMedia({ url, mediaType: 'mpd', sourceType: 'dash_js' });
            }
            return origDash.apply(this, arguments);
          };
        }
        window.dashjs.__cc_wrapped = true;
      }
    } catch (e) {}
  }
  hookPlayerLibraries();
  let hookTries = 0;
  const hookTimer = setInterval(() => {
    hookTries++;
    hookPlayerLibraries();
    if (hookTries > 25) clearInterval(hookTimer);
  }, 400);

  // 7. B站原生 DASH 音画双轨实时深度解析与自动配对
  function checkBilibiliPlayInfo() {
    try {
      const pi = window.__playinfo__;
      if (pi && pi.data && pi.data.dash) {
        const dash = pi.data.dash;
        const videos = dash.video || [];
        const audios = dash.audio || [];
        if (videos.length > 0) {
          const bestVideo = videos.reduce((prev, curr) => ((curr.id || 0) > (prev.id || 0) ? curr : prev), videos[0]);
          const bestAudio = audios.length > 0 ? audios.reduce((prev, curr) => ((curr.id || 0) > (prev.id || 0) ? curr : prev), audios[0]) : null;
          const vUrl = bestVideo.baseUrl || bestVideo.base_url || (bestVideo.backupUrl && bestVideo.backupUrl[0]) || '';
          const aUrl = bestAudio ? (bestAudio.baseUrl || bestAudio.base_url || (bestAudio.backupUrl && bestAudio.backupUrl[0]) || '') : '';
          if (vUrl) {
            notifyMedia({
              url: vUrl,
              audioUrl: aUrl,
              title: document.title || 'B站高清视频',
              mediaType: 'bili_dash',
              sourceType: 'bili_playinfo'
            });
          }
        }
      }
    } catch (e) {}
  }

  // 监听 B站 __playinfo__ 变量注入或更新
  try {
    let playInfoVal = window.__playinfo__;
    checkBilibiliPlayInfo();
    Object.defineProperty(window, '__playinfo__', {
      configurable: true,
      enumerable: true,
      get: function () {
        return playInfoVal;
      },
      set: function (newVal) {
        playInfoVal = newVal;
        setTimeout(checkBilibiliPlayInfo, 50);
      }
    });
  } catch (e) {}

  // 8. 深度扫描页面上所有媒体元素、分发源以及已加载的网络资源缓存
  function checkExistingMedia() {
    checkBilibiliPlayInfo();

    // 扫描 performance 资源加载记录
    try {
      if (window.performance && typeof window.performance.getEntriesByType === 'function') {
        const resources = window.performance.getEntriesByType('resource');
        for (let i = 0; i < resources.length; i++) {
          const u = resources[i].name;
          if (u && (MEDIA_REGEX.test(u) || SHORT_VIDEO_CDN_REGEX.test(u) || STREAM_KEYWORD_REGEX.test(u)) && !isFragment(u) && !u.startsWith('blob:')) {
            notifyMedia({
              url: u,
              mediaType: PLAYLIST_REGEX.test(u) ? 'm3u8' : 'video',
              sourceType: 'performance_resource'
            });
          }
        }
      }
    } catch (e) {}

    // 扫描 DOM 中的 video, audio, source 标签
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

    // 扫描 iframe 引用
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

  // 9. DOM 动态元素监听 (针对现代 SPA / 动态渲染网页)
  try {
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (node.nodeType !== 1) continue;
          if (node.tagName === 'VIDEO' || node.tagName === 'AUDIO') {
            const src = node.currentSrc || node.src;
            if (src && !src.startsWith('blob:') && !isFragment(src)) {
              notifyMedia({
                url: src,
                mediaType: node.tagName === 'AUDIO' ? 'audio' : (PLAYLIST_REGEX.test(src) ? 'm3u8' : 'video'),
                sourceType: 'mutation_media'
              });
            }
          } else if (node.querySelectorAll) {
            node.querySelectorAll('video, audio, source').forEach((el) => {
              const src = el.currentSrc || el.src;
              if (src && !src.startsWith('blob:') && !isFragment(src)) {
                if (MEDIA_REGEX.test(src) || PLAYLIST_REGEX.test(src) || SHORT_VIDEO_CDN_REGEX.test(src)) {
                  notifyMedia({
                    url: src,
                    mediaType: el.tagName === 'AUDIO' ? 'audio' : (PLAYLIST_REGEX.test(src) ? 'm3u8' : 'video'),
                    sourceType: 'mutation_child'
                  });
                }
              }
            });
          }
        }
      }
    });
    observer.observe(document.documentElement || document.body, { childList: true, subtree: true });
  } catch (e) {}

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

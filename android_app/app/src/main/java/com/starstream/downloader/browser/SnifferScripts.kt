package com.starstream.downloader.browser

import com.starstream.downloader.core.AppConfig

/**
 * 注入 WebView 的全类型媒体与文件嗅探脚本 & 同系列 DOM 扫描脚本
 * 支持根据用户在设置中添加/删除的扩展名列表动态生成嗅探过滤规则（IDM 风格）
 */
object SnifferScripts {

    fun buildInjectSnifferJs(extensions: List<String> = AppConfig.getSniffExtensions()): String {
        val cleanExts = extensions.map { it.trim().lowercase().trimStart('.') }
            .filter { it.matches(Regex("[a-z0-9]{1,12}")) }
            .distinct()
        val extRegexPart = if (cleanExts.isEmpty()) "mp4|m3u8" else cleanExts.joinToString("|")
        val tsAllowed = cleanExts.contains("ts")
        val ignoreNoiseExts = listOf("jpg", "jpeg", "png", "webp", "avif", "gif", "svg", "ico", "css", "js", "json", "woff", "woff2", "ttf", "vtt", "srt", "ass")
            .filter { it !in cleanExts }
            .let { list -> if (tsAllowed) list else list + "ts" }
            .joinToString("|")

        return """
            (function() {
              const __customExtRe = new RegExp('\\.($extRegexPart)(\\?|#|${'$'})', 'i');
              const __ignoreExtRe = new RegExp('\\.($ignoreNoiseExts)(${'$'}|\\?)', 'i');
              window.__starstream_ext_re = __customExtRe;
              window.__starstream_ignore_re = __ignoreExtRe;
              if (window.__starstream_hooked) return;
              window.__starstream_hooked = true;
              let lastDomDur = 0;
              let lastDomRes = '';

              function updateDomVideoMeta() {
                document.querySelectorAll('video').forEach(function(v) {
                  const d = (v.duration && isFinite(v.duration)) ? Math.round(v.duration) : 0;
                  if (d > lastDomDur) lastDomDur = d;
                  if (v.videoWidth > 0 && v.videoHeight > 0) {
                    lastDomRes = v.videoWidth + 'x' + v.videoHeight;
                  }
                });
              }

              function report(url, mediaType, durSec, resStr) {
                if (!url || typeof url !== 'string') return;
                if (url.startsWith('blob:') || url.startsWith('data:')) return;
                let absUrl = url;
                try { absUrl = new URL(url, window.location.href).href; } catch (e) {}
                const clean = absUrl.split('#')[0].toLowerCase();
                const path = clean.split('?')[0];
                if (window.__starstream_ignore_re && window.__starstream_ignore_re.test(path)) return;
                if (/(init\.mp4|init\.m4s|\/bfs\/|bvc_preview|sprite|thumb|cover|avatar)/i.test(clean)) return;
                const matchedCustom = window.__starstream_ext_re && window.__starstream_ext_re.test(clean);
                const matchedPlatform = /(\/upgcxcode\/|playurl|douyinvod\.com|iesdouyin\.com|kwaicdn\.com|xhscdn\.com|\/api\/hls\/|302\d{2}\.m4s)/i.test(clean);
                if (matchedCustom || matchedPlatform) {
                  updateDomVideoMeta();
                  const isVid = /\.(m3u8|mpd|mp4|m4s|flv|webm|mkv|mov|avi)(\?|#|${'$'})/i.test(clean) || matchedPlatform;
                  const finalDur = durSec || (isVid ? lastDomDur : 0);
                  const finalRes = resStr || (isVid ? lastDomRes : '');
                  try {
                    window.StarStreamBridge.onMediaFound(
                      absUrl,
                      mediaType || '',
                      document.title || '',
                      window.location.href,
                      finalDur,
                      finalRes
                    );
                  } catch (e) {}
                }
              }

              function scanDomMedia() {
                updateDomVideoMeta();
                document.querySelectorAll('video, audio, source').forEach(function(el) {
                  const s = el.currentSrc || el.src;
                  if (!s) return;
                  const isAud = el.tagName.toLowerCase() === 'audio';
                  const d = (el.duration && isFinite(el.duration)) ? Math.round(el.duration) : 0;
                  const r = (el.videoWidth && el.videoHeight) ? (el.videoWidth + 'x' + el.videoHeight) : '';
                  report(s, isAud ? 'audio' : '', d, r);
                });
                document.querySelectorAll('a[href]').forEach(function(a) {
                  const h = a.getAttribute('href');
                  if (h && window.__starstream_ext_re && window.__starstream_ext_re.test(h)) {
                    report(h, '', 0, '');
                  }
                });
                try {
                  if (window.player_aaaa && window.player_aaaa.url) {
                    report(window.player_aaaa.url, '', lastDomDur, lastDomRes);
                  }
                } catch (e) {}
              }

              const origFetch = window.fetch;
              if (origFetch) {
                window.fetch = function(input, init) {
                  try {
                    const u = typeof input === 'string' ? input : (input && input.url);
                    report(u, '', 0, '');
                  } catch (e) {}
                  return origFetch.apply(this, arguments);
                };
              }
              const origOpen = XMLHttpRequest.prototype.open;
              XMLHttpRequest.prototype.open = function(method, url) {
                try { report(url, '', 0, ''); } catch (e) {}
                return origOpen.apply(this, arguments);
              };
              scanDomMedia();
              setInterval(scanDomMedia, 1800);
            })();
        """.trimIndent()
    }

    val SCAN_SERIES_JS = """
        (function() {
          const href = window.location.href;
          const host = window.location.hostname.toLowerCase();
          let seriesTitle = (document.title || '').replace(/\s*[-_|—].*${'$'}/, '').trim() || '同系列合集';
          const episodes = [];
          const seen = new Set();
          let curIdx = 0;

          function addEp(title, epUrl, isCur) {
            if (!epUrl) return;
            let abs = '';
            try { abs = new URL(epUrl, href).href; } catch (e) { return; }
            if (seen.has(abs)) return;
            seen.add(abs);
            const t = (title || '').replace(/\s+/g, ' ').trim();
            if (!t) return;
            if (isCur || abs === href) curIdx = episodes.length;
            episodes.push({ index: episodes.length + 1, title: t, page_url: abs });
          }

          if (host.includes('bilibili.com')) {
            const h = document.querySelector('.video-pod__header .title, .base-video-sections-v1 .first-line-title, .multi-page .head-con h3');
            if (h && h.textContent) seriesTitle = h.textContent.trim();
            const podItems = document.querySelectorAll('.video-pod__list .pod-item, .video-pod__list .video-pod__item');
            if (podItems.length > 1) {
              const bvM = href.match(/(BV[a-zA-Z0-9]+)/);
              const curBv = bvM ? bvM[1] : '';
              podItems.forEach((it, idx) => {
                const tEl = it.querySelector('.title-txt, .title, a');
                const aEl = it.tagName === 'A' ? it : it.querySelector('a');
                const dk = it.getAttribute('data-key') || '';
                let u = aEl ? aEl.getAttribute('href') : '';
                if (!u && dk.startsWith('BV')) u = 'https://www.bilibili.com/video/' + dk;
                else if (!u && curBv) u = 'https://www.bilibili.com/video/' + curBv + '?p=' + (idx + 1);
                addEp(tEl ? tEl.textContent : ('P' + (idx + 1)), u, it.classList.contains('active'));
              });
            }
          }

          if (episodes.length < 2) {
            const baseU = new URL(href);
            const basePath = baseU.pathname.replace(/\/${'$'}/, '');
            const prefix = basePath.replace(/\d+(?=(?:\.[a-z]+)?${'$'})/i, '');
            const epRe = /(第\s*\d+\s*[集话期章讲节课部回]|EP?\s*\d+|P\d+|^\d{1,3}${'$'}|^(?:集|话|期|课)\s*\d+|番外|先导|预告|全集)/i;
            const noiseRe = /(次觀看|次观看|views|已完結|已完结|全\s*\d+\s*集)/i;
            const actRe = /^(?:從|从|立即|开始|開始|观看|觀看|正在).*?(?:開始|开始|播放|观看|觀看)${'$'}|^(?:上一集|下一集|播放|正在播放)${'$'}/;
            const map = new Map();
            document.querySelectorAll('a[href]').forEach((a) => {
              const rh = a.getAttribute('href') || '';
              if (!rh || rh.startsWith('#') || rh.startsWith('javascript:')) return;
              let u; try { u = new URL(rh, href); } catch (e) { return; }
              if (u.hostname !== baseU.hostname) return;
              const txt = (a.getAttribute('title') || a.textContent || '').replace(/\s+/g, ' ').trim();
              if (!txt || txt.length > 50 || noiseRe.test(txt)) return;
              const up = u.pathname.replace(/\/${'$'}/, '');
              const samePat = prefix.length > 3 && up.startsWith(prefix) && up !== prefix;
              if (samePat || epRe.test(txt)) {
                if (map.has(u.href)) {
                  const prev = map.get(u.href);
                  if (actRe.test(prev.t) && !actRe.test(txt)) prev.t = txt;
                } else {
                  map.set(u.href, { t: txt, u: u.href, cur: u.href === href });
                }
              }
            });
            if (map.size >= 2) {
              Array.from(map.values()).slice(0, 150).forEach(x => addEp(x.t, x.u, x.cur));
            }
          }
          return JSON.stringify({ has_series: episodes.length > 1, series_title: seriesTitle, current_index: curIdx, page_url: href, episodes: episodes });
        })();
    """.trimIndent()
}

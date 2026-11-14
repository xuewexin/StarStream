// content_script.js - CatCatch Content Script & IDM Floating Bar
(function () {
  'use strict';

  // 1. 注入 inject.js 到宿主页面上下文
  function injectHookScript() {
    try {
      const script = document.createElement('script');
      script.src = chrome.runtime.getURL('inject.js');
      script.onload = function () {
        this.remove();
      };
      (document.head || document.documentElement).appendChild(script);
    } catch (e) {}
  }
  injectHookScript();

  // 兜底通道：部分站点 CSP 会拦截 <script src="chrome-extension://...">，
  // 改由 background 用 scripting API 注入 MAIN world（含深层 iframe），
  // inject.js 自带幂等标志，双通道不会重复 hook。
  try {
    chrome.runtime.sendMessage({ action: 'ENSURE_MAIN_INJECT' }).catch(() => {});
  } catch (e) {}

  if (typeof ExtI18n !== 'undefined') {
    ExtI18n.initLang();
  }
  try {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === 'local' && changes.extension_language && typeof ExtI18n !== 'undefined') {
        ExtI18n.setLang(changes.extension_language.newValue);
      }
    });
  } catch (e) {}

  function toBase64(str) {
    if (!str) return '';
    try {
      return btoa(unescape(encodeURIComponent(str)));
    } catch (e) {
      return btoa(str);
    }
  }

  // 精确分片识别：清单 (m3u8/mpd) 永不被当作切片丢弃
  const PLAYLIST_REGEX = /\.(m3u8|mpd)(\?|#|$)/i;
  const SEGMENT_REGEX = /\.(ts|m4s|m4v|mp2t|cmfv|cmfa|vtt|srt|ass|key)(\?|#|$)/i;
  function isBiliDashUrl(url) {
    if (!url) return false;
    return /(bilivideo\.(com|cn)|hdslb\.com|\/upgcxcode\/|\bgen=playurlv3\b|\b\d{6,14}-\d+-\d+\.m4s\b)/i.test(url);
  }
  function isFragmentUrl(url) {
    if (!url) return true;
    const clean = String(url).split('#')[0];
    if (PLAYLIST_REGEX.test(clean)) return false;
    if (isBiliDashUrl(clean)) return false;
    if (SEGMENT_REGEX.test(clean)) return true;
    if (/(^|\/)(init\.mp4|init\.m4s)$/i.test(clean.split('?')[0])) return true;
    if (/(^|\/)(segment|chunk|frag|seg|part)[-_.]?\d+\.(ts|m4s|mp4|m4v)/i.test(clean)) return true;
    return false;
  }

  // 标题清理与播放器名字剔除助手
  function isPlayerOrGenericTitle(title) {
    if (!title) return true;
    const t = title.trim().toLowerCase();
    const generic = [
      'dplayer', 'ckplayer', 'artplayer', 'xgplayer', 'aliplayer', 'player',
      'video', 'iframe', 'play', 'mp4', 'm3u8', 'media', '播放器', '视频播放',
      '全屏视频播放器', '全屏播放器', 'html5视频播放器', '网页视频播放器',
      '无标题', 'untitled', 'index', 'default'
    ];
    if (generic.includes(t) || generic.some(g => t === `${g}.html` || t === `${g}.php`)) return true;
    if (t.includes('播放器') || t.includes('player') || t === '全屏视频' || t === '视频播放') return true;
    return false;
  }

  function cleanVideoTitle(raw, fallbackTabTitle) {
    let title = (raw || '').trim();
    if (isPlayerOrGenericTitle(title)) {
      if (fallbackTabTitle && !isPlayerOrGenericTitle(fallbackTabTitle)) {
        title = fallbackTabTitle.trim();
      } else {
        title = '';
      }
    }
    // 移除末尾播放器标识与盗版影视网站后缀
    title = title.replace(/\s*[-_—|]\s*(DPlayer|ckplayer|Artplayer|xgplayer|Aliplayer|网页播放器|H5播放器)\s*$/i, '');
    title = title.replace(/\s*[-_—|]\s*(在线播放|在线观看|高清在线|免费在线|完整版在线|高清播放).*$/i, '');
    const defaultTitle = typeof ExtI18n !== 'undefined' ? ExtI18n.t('cap_default_video_title') : '网页视频';
    return title.trim() || fallbackTabTitle || defaultTitle;
  }

  // 2. 接收来自 inject.js 的深层嗅探消息
  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data || event.data.source !== 'CATCATCH_INJECTOR') return;
    const payload = event.data.payload;
    if (!payload || !payload.url || payload.url.startsWith('blob:') || isFragmentUrl(payload.url)) return;

    chrome.runtime.sendMessage({
      action: 'SNIFFED_MEDIA',
      data: payload
    }).catch(() => {});
  });

  // 响应来自 popup 的深度重新嗅探指令
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message && message.action === 'RESNIFF_ACTIVE_TAB') {
      try {
        window.postMessage({ action: 'CATCATCH_DO_RESNIFF' }, '*');
      } catch (e) {}
      try {
        document.querySelectorAll('video, audio').forEach((el) => {
          const src = el.currentSrc || el.src;
          if (src && !src.startsWith('blob:') && !isFragmentUrl(src)) {
            chrome.runtime.sendMessage({
              action: 'SNIFFED_MEDIA',
              data: {
                url: src,
                title: cleanVideoTitle(document.title),
                pageUrl: window.location.href,
                referer: window.location.href,
                mediaType: el.tagName.toLowerCase() === 'audio' ? 'audio' : (PLAYLIST_REGEX.test(src) ? 'm3u8' : 'video'),
                sourceType: 'content_script_resniff'
              }
            }).catch(() => {});
          }
          el.querySelectorAll('source').forEach((s) => {
            const sSrc = s.src || s.getAttribute('src');
            if (sSrc && !sSrc.startsWith('blob:') && !isFragmentUrl(sSrc)) {
              chrome.runtime.sendMessage({
                action: 'SNIFFED_MEDIA',
                data: {
                  url: sSrc,
                  title: cleanVideoTitle(document.title),
                  pageUrl: window.location.href,
                  referer: window.location.href,
                  mediaType: PLAYLIST_REGEX.test(sSrc) ? 'm3u8' : 'video',
                  sourceType: 'content_script_resniff_source'
                }
              }).catch(() => {});
            }
          });
        });
      } catch (e) {}
      sendResponse({ status: 'ok' });
    }
    return true;
  });

  // 3. IDM 悬浮下载条 (支持闲置自动渐隐、标签页切换清理与一键关闭)
  let activeFloatingBtn = null;
  let activePanel = null;
  let autoHideTimer = null;
  let isMouseOverBtn = false;

  const SVG_DOWNLOAD_ICON = `<svg class="catcatch-icon-svg" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
    <polyline points="7 10 12 15 17 10"></polyline>
    <line x1="12" y1="15" x2="12" y2="3"></line>
  </svg>`;

  function resetAutoHideTimer(delay = 3500) {
    if (autoHideTimer) clearTimeout(autoHideTimer);
    if (activePanel) return; // 详情面板展开时不自动隐藏
    autoHideTimer = setTimeout(() => {
      if (activeFloatingBtn && !activePanel && !isMouseOverBtn) {
        activeFloatingBtn.classList.add('catcatch-btn-hidden');
      }
    }, delay);
  }

  function initFloatingDownloadBar() {
    document.addEventListener('mouseover', handleMouseOver, true);

    document.addEventListener('play', (e) => {
      if (e.target && (e.target.tagName === 'VIDEO' || e.target.tagName === 'AUDIO')) {
        showFloatingBarForMedia(e.target);
      }
    }, true);

    // 点击页面任意外部空白处关闭详情面板
    document.addEventListener('click', (e) => {
      if (activePanel && !activePanel.contains(e.target) && (!activeFloatingBtn || !activeFloatingBtn.contains(e.target))) {
        if (activePanel) {
          activePanel.remove();
          activePanel = null;
        }
        resetAutoHideTimer(2000);
      }
    }, true);
  }

  function handleMouseOver(e) {
    const target = e.target;
    if (!target) return;
    if (target.tagName === 'VIDEO' || (target.tagName === 'DIV' && target.querySelector('video'))) {
      const videoEl = target.tagName === 'VIDEO' ? target : target.querySelector('video');
      if (videoEl && !videoEl.__catcatch_dismissed) {
        showFloatingBarForMedia(videoEl);
      }
    }
  }

  /**
   * 把播放器真实元数据同步回后台。
   * streamUrl 会把更新精确锁定到"当前正在播的这条流"，
   * 避免把整片时长写到同页面的 6 秒广告切片上。
   */
  function syncMediaMetadata(mediaEl) {
    if (!mediaEl) return;
    const rawDur = Number(mediaEl.duration);
    const dur = Number.isFinite(rawDur) && rawDur > 0 ? Math.floor(rawDur) : 0;
    const res = (mediaEl.videoWidth && mediaEl.videoHeight) ? `${mediaEl.videoWidth}x${mediaEl.videoHeight}` : '';
    const streamUrl = mediaEl.__catcatch_stream_url || '';
    if (dur > 0 || res || streamUrl) {
      chrome.runtime.sendMessage({
        action: 'UPDATE_MEDIA_METADATA',
        data: {
          duration: dur,
          resolution: res,
          streamUrl,
          videoSrc: mediaEl.currentSrc || mediaEl.src || ''
        }
      }).catch(() => {});
    }
  }

  function showFloatingBarForMedia(mediaEl) {
    if (mediaEl.__catcatch_dismissed) return;

    // 监听播放器的实际播放元数据，将真实的视频时长和分辨率实时同步回后台
    function syncRealMetadata() {
      syncMediaMetadata(mediaEl);
    }
    if (!mediaEl.__catcatch_meta_bound) {
      mediaEl.__catcatch_meta_bound = true;
      mediaEl.addEventListener('durationchange', syncRealMetadata);
      mediaEl.addEventListener('loadedmetadata', syncRealMetadata);
      mediaEl.addEventListener('playing', syncRealMetadata);
    }
    syncRealMetadata();

    const rect = mediaEl.getBoundingClientRect();
    if (rect.width < 160 || rect.height < 100) return;

    if (activeFloatingBtn && activeFloatingBtn.__targetMedia === mediaEl) {
      // 唤醒并重新开始倒计时自动消失
      activeFloatingBtn.classList.remove('catcatch-btn-hidden');
      resetAutoHideTimer(3500);
      return;
    }
    removeFloatingBar();

    const btn = document.createElement('div');
    btn.className = 'catcatch-floating-btn';
    const t = (k, def) => (typeof ExtI18n !== 'undefined' ? ExtI18n.t(k) : def);
    btn.innerHTML = `
      <div class="catcatch-btn-main" style="display:inline-flex;align-items:center;gap:5px;">
        ${SVG_DOWNLOAD_ICON}
        <span>${t('cap_download_video', '下载视频')}</span>
      </div>
      <span class="catcatch-close-badge" title="${t('cap_close_badge', '关闭悬浮角标')}">×</span>
    `;
    btn.__targetMedia = mediaEl;

    const topPos = window.scrollY + rect.top + 10;
    const rightPos = window.innerWidth - (window.scrollX + rect.right) + 12;
    btn.style.top = `${topPos}px`;
    btn.style.right = `${rightPos}px`;

    // 鼠标在按钮上时阻止自动隐藏
    btn.addEventListener('mouseenter', () => {
      isMouseOverBtn = true;
      if (autoHideTimer) clearTimeout(autoHideTimer);
      btn.classList.remove('catcatch-btn-hidden');
    });

    btn.addEventListener('mouseleave', () => {
      isMouseOverBtn = false;
      resetAutoHideTimer(2000);
    });

    // 点击主区域展开下载面板
    const mainArea = btn.querySelector('.catcatch-btn-main');
    mainArea.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleMediaPanel(mediaEl, btn);
    });

    // 点击右上角 × 彻底关闭此视频的角标
    const closeBadge = btn.querySelector('.catcatch-close-badge');
    closeBadge.addEventListener('click', (e) => {
      e.stopPropagation();
      mediaEl.__catcatch_dismissed = true;
      removeFloatingBar();
    });

    // 监听播放器上的鼠标移动，有操作时唤醒，闲置 3.5 秒后自动隐去
    mediaEl.addEventListener('mousemove', () => {
      if (activeFloatingBtn && !mediaEl.__catcatch_dismissed) {
        activeFloatingBtn.classList.remove('catcatch-btn-hidden');
        resetAutoHideTimer(3500);
      }
    }, { passive: true });

    document.body.appendChild(btn);
    activeFloatingBtn = btn;
    resetAutoHideTimer(3500);
  }

  function getResolutionScore(res) {
    if (!res) return 0;
    const s = String(res).toUpperCase();
    if (s.includes('4K') || s.includes('2160')) return 2160;
    if (s.includes('2K') || s.includes('1440')) return 1440;
    if (s.includes('1080')) return 1080;
    if (s.includes('720')) return 720;
    if (s.includes('480')) return 480;
    if (s.includes('360')) return 360;
    if (s.includes('240')) return 240;
    const m = s.match(/(\d{3,4})[xX*](\d{3,4})/);
    if (m) {
      return Math.min(parseInt(m[1]), parseInt(m[2]));
    }
    return 0;
  }

  /** 从地址里提取真实画质（/720p/、_1080p.、4k），优先于播放器渲染尺寸 */
  function extractQualityFromUrl(url) {
    const u = String(url || '');
    const m = u.match(/(?:^|[\/_.-])(\d{3,4})p(?:[\/_.-]|$)/i);
    if (m) {
      const h = parseInt(m[1], 10);
      if (h >= 144 && h <= 4320) return `${h}P`;
    }
    if (/(?:^|[\/_.-])(4k|2160p?)(?:[\/_.-]|$)/i.test(u)) return '2160P';
    if (/(?:^|[\/_.-])2k(?:[\/_.-]|$)/i.test(u)) return '1440P';
    return '';
  }

  function bestResOf(item) {
    if (!item) return '';
    return extractQualityFromUrl(item.url) || item.resolution || '';
  }

  /** 画面分辨率展示：1920x1080 → 1080P */
  function formatResLabel(value) {
    if (!value) return t('cap_hd_stream', '高清流');
    const s = String(value).toUpperCase();
    const dim = s.match(/(\d{3,4})[X×*](\d{3,4})/);
    if (dim) return `${Math.min(parseInt(dim[1], 10), parseInt(dim[2], 10))}P`;
    const h = getResolutionScore(value);
    if (h) return `${h}P`;
    return String(value);
  }

  /** 时长展示：超过 1 小时显示 h:mm:ss，避免出现 "117分22秒" */
  function formatDurLabel(sec) {
    const total = Math.round(Number(sec) || 0);
    if (!Number.isFinite(total) || total <= 0) return '';
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const mm = h > 0 ? String(m).padStart(2, '0') : String(m);
    const ss = String(s).padStart(2, '0');
    return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
  }

  async function resolveRealMediaUrl(mediaEl) {
    const rawSrc = mediaEl.currentSrc || mediaEl.src || '';
    let directMedia = null;
    if (rawSrc && !rawSrc.startsWith('blob:') && (rawSrc.startsWith('http://') || rawSrc.startsWith('https://')) && !isFragmentUrl(rawSrc)) {
      directMedia = { url: rawSrc, mediaType: 'video', format: 'MP4' };
    }

    // 若为 blob: 协议（MediaSource 流）或需要获取标签页元数据，向 background 查询
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: 'GET_MEDIA_FOR_TAB',
        pageUrl: window.location.href
      }, (res) => {
        const tabTitle = (res && res.tabTitle) || '';
        if (res && res.media && res.media.length > 0) {
          // 智能过滤广告切片: 过滤标记为 isAd 的流（若播放器实际时长 > 45秒，避免误把正片过滤）
          const rawDurSec = Number(mediaEl.duration);
          const durSec = Number.isFinite(rawDurSec) && rawDurSec > 0 ? Math.floor(rawDurSec) : 0;
          const nonAds = res.media.filter((i) => !i.isAd || durSec > 45);
          const pool = nonAds.length > 0 ? nonAds : res.media;
          // 默认选择「时长最长 → 画质最高」的正片
          pool.sort((a, b) => {
            if (!a.isAd && b.isAd) return -1;
            if (a.isAd && !b.isAd) return 1;

            // 1. 时长降序（时长未知的排在已知之后）
            const durA = Number(a.duration) || 0;
            const durB = Number(b.duration) || 0;
            if (durA !== durB) return durB - durA;

            // 2. 画面分辨率降序（优先地址里的真实画质标签）
            const resA = getResolutionScore(bestResOf(a));
            const resB = getResolutionScore(bestResOf(b));
            if (resA !== resB) return resB - resA;

            // 3. 体积降序
            const sizeDiff = (b.contentLength || 0) - (a.contentLength || 0);
            if (sizeDiff) return sizeDiff;

            // 4. 流媒体格式优先
            if (a.mediaType === 'm3u8' && b.mediaType !== 'm3u8') return -1;
            if (a.mediaType !== 'm3u8' && b.mediaType === 'm3u8') return 1;

            return (b.timestamp || 0) - (a.timestamp || 0);
          });
          const chosen = pool[0];
          resolve({
            url: chosen.url,
            audioUrl: chosen.audioUrl || '',
            mediaType: chosen.mediaType || 'm3u8',
            format: (chosen.mediaType || 'm3u8').toUpperCase(),
            resolution: bestResOf(chosen),
            duration: chosen.duration || 0,
            tabTitle: tabTitle || chosen.pageTitle || '',
            referer: chosen.referer || '',
            userAgent: chosen.userAgent || '',
            cookie: chosen.cookie || ''
          });
        } else if (directMedia) {
          directMedia.tabTitle = tabTitle;
          resolve(directMedia);
        } else {
          resolve(null);
        }
      });
    });
  }

  async function toggleMediaPanel(mediaEl, anchorBtn) {
    if (activePanel) {
      activePanel.remove();
      activePanel = null;
      return;
    }

    let currentTitle = cleanVideoTitle(document.title);
    const rect = anchorBtn.getBoundingClientRect();
    const t = (k, def) => (typeof ExtI18n !== 'undefined' ? ExtI18n.t(k) : def);

    const panel = document.createElement('div');
    panel.className = 'catcatch-floating-panel';
    panel.style.top = `${window.scrollY + rect.bottom + 6}px`;
    panel.style.right = `${window.innerWidth - (window.scrollX + rect.right)}px`;

    // 若当前在通用播放器 iframe 中，立即向上层标签页请求主网页标题进行标题纠正
    if (!currentTitle || isPlayerOrGenericTitle(document.title)) {
      try {
        chrome.runtime.sendMessage({ action: 'GET_TAB_INFO' }, (res) => {
          if (res && res.title) {
            const refined = cleanVideoTitle(res.title);
            if (refined && !isPlayerOrGenericTitle(refined)) {
              currentTitle = refined;
              const titleEl = panel.querySelector('.catcatch-panel-title');
              if (titleEl) {
                titleEl.textContent = currentTitle;
                titleEl.title = currentTitle;
              }
            }
          }
        });
      } catch (e) {}
    }

    panel.innerHTML = `
      <div class="catcatch-panel-title" title="${currentTitle}">${currentTitle}</div>
      <div id="catcatchPanelContent" class="catcatch-panel-info">${t('cap_locating', '正在定位真实视频流...')}</div>
      <div class="catcatch-config-row" style="display:flex;align-items:center;gap:6px;margin:6px 0;font-size:11px;color:#a1a1aa;">
        <span>${t('cap_proxy_label', '下载代理:')}</span>
        <select id="catcatchProxySelect" style="flex:1;background:#27272a;color:#f4f4f5;border:1px solid #3f3f46;border-radius:4px;padding:3px 6px;font-size:11px;outline:none;">
          <option value="auto" selected>${t('cfg_proxy_auto', '自动匹配浏览器代理 (推荐)')}</option>
          <option value="default">${t('cfg_proxy_default', '跟随客户端全局设置')}</option>
          <option value="direct">${t('cfg_proxy_direct', '直连 (不使用代理)')}</option>
          <option value="http://127.0.0.1:7890">Clash / Verge (7890)</option>
          <option value="socks5://127.0.0.1:10808">v2rayN SOCKS5 (10808)</option>
          <option value="http://127.0.0.1:10809">v2rayN HTTP (10809)</option>
        </select>
      </div>
      <div class="catcatch-panel-actions">
        <button id="catcatchPushBtn" class="catcatch-btn primary" disabled>${t('cap_push_btn', '推送到星流下载器')}</button>
        <button id="catcatchCopyCmdBtn" class="catcatch-btn" disabled>${t('cap_copy_cmd', '复制命令')}</button>
        <button id="catcatchCopyBtn" class="catcatch-btn" disabled>${t('cap_copy_link', '复制原链')}</button>
        <button id="catcatchCopyB64Btn" class="catcatch-btn" disabled>${t('cap_copy_b64', '复制Base64')}</button>
        <button id="catcatchCloseBtn" class="catcatch-btn">${t('cap_close', '关闭')}</button>
      </div>
    `;

    document.body.appendChild(panel);
    activePanel = panel;

    // 解析真实地址
    const mediaInfo = await resolveRealMediaUrl(mediaEl);
    if (mediaInfo && mediaInfo.url) {
      // 记录"这个播放器当前对应的流地址"，后续元数据同步只更新这一条
      mediaEl.__catcatch_stream_url = mediaInfo.url;
      syncMediaMetadata(mediaEl);
    }
    const contentDiv = panel.querySelector('#catcatchPanelContent');
    const proxySelect = panel.querySelector('#catcatchProxySelect');
    const pushBtn = panel.querySelector('#catcatchPushBtn');
    const copyCmdBtn = panel.querySelector('#catcatchCopyCmdBtn');
    const copyBtn = panel.querySelector('#catcatchCopyBtn');
    const copyB64Btn = panel.querySelector('#catcatchCopyB64Btn');
    const closeBtn = panel.querySelector('#catcatchCloseBtn');

    closeBtn.addEventListener('click', () => removeFloatingBar());

    if (!mediaInfo) {
      contentDiv.innerHTML = `<span style="color:#fbbf24;">${t('cap_no_stream', '未抓取到流地址，请点击播放视频后重试')}</span>`;
      return;
    }

    // 智能修正标题: 若在 iframe 中且原标题为 DPlayer 等通用播放器名，替换为主网页真实标题
    if (mediaInfo.tabTitle) {
      currentTitle = cleanVideoTitle(document.title, mediaInfo.tabTitle);
      const titleEl = panel.querySelector('.catcatch-panel-title');
      if (titleEl) {
        titleEl.textContent = currentTitle;
        titleEl.title = currentTitle;
      }
    }

    // 直播流的 duration 可能为 Infinity，先过滤再格式化
    const rawDurSec = Number(mediaEl.duration);
    const durSec = Number.isFinite(rawDurSec) && rawDurSec > 0 ? Math.floor(rawDurSec) : 0;
    const durStr = formatDurLabel(durSec);
    const resLabel = formatResLabel(mediaInfo.resolution || ((mediaEl.videoWidth && mediaEl.videoHeight) ? `${mediaEl.videoWidth}x${mediaEl.videoHeight}` : ''));

    contentDiv.innerHTML = `
      <span class="catcatch-badge accent">${mediaInfo.format}</span>
      <span class="catcatch-badge">${resLabel}</span>
      ${durStr ? `<span class="catcatch-badge">${durStr}</span>` : ''}
    `;

    pushBtn.disabled = false;
    copyCmdBtn.disabled = false;
    copyBtn.disabled = false;
    copyB64Btn.disabled = false;

    copyCmdBtn.addEventListener('click', () => {
      const pChoice = proxySelect.value;
      const safeTitle = (currentTitle || 'video').replace(/[\\/*?:"<>|]/g, '_');
      let cmd = `N_m3u8DL-RE "${mediaInfo.url}" --save-name "${safeTitle}" --auto-select -M format=mp4`;
      if (pChoice && pChoice !== 'default' && pChoice !== 'direct' && pChoice !== 'auto') {
        cmd += ` --custom-proxy "${pChoice}"`;
      }
      cmd += ` -H "Referer: ${mediaInfo.referer || window.location.href}" -H "User-Agent: ${mediaInfo.userAgent || navigator.userAgent}"`;
      if (mediaInfo.cookie) cmd += ` -H "Cookie: ${mediaInfo.cookie}"`;

      navigator.clipboard.writeText(cmd).then(() => {
        copyCmdBtn.textContent = t('cap_copied_cmd', '已复制命令');
        setTimeout(() => (copyCmdBtn.textContent = t('cap_copy_cmd', '复制命令')), 1500);
      });
    });

    pushBtn.addEventListener('click', async () => {
      pushBtn.textContent = t('cap_pushing', '正在推送...');
      pushBtn.disabled = true;

      const pVal = proxySelect.value;
      let finalProxy = pVal;

      if (pVal === 'auto') {
        try {
          const proxyInfo = await new Promise((res) => {
            chrome.runtime.sendMessage({ action: 'DETECT_BROWSER_PROXY' }, res);
          });
          if (proxyInfo && proxyInfo.proxyUrl) {
            finalProxy = proxyInfo.proxyUrl;
          } else if (proxyInfo && proxyInfo.mode === 'direct') {
            finalProxy = 'none';
          } else {
            finalProxy = 'auto';
          }
        } catch (e) {
          finalProxy = 'auto';
        }
      }

      const taskData = {
        url: mediaInfo.url,
        audioUrl: mediaInfo.audioUrl || '',
        title: currentTitle,
        saveName: currentTitle,
        mediaType: mediaInfo.mediaType,
        resolution: mediaInfo.resolution || resStr || '',
        duration: mediaInfo.duration || durSec || 0,
        proxy: finalProxy,
        pageUrl: window.location.href,
        referer: mediaInfo.referer || window.location.href,
        headers: {
          Referer: mediaInfo.referer || window.location.href,
          Origin: (() => { try { return new URL(mediaInfo.referer || window.location.href).origin; } catch (e) { return window.location.origin; } })(),
          'User-Agent': mediaInfo.userAgent || navigator.userAgent,
          Cookie: mediaInfo.cookie || ''
        }
      };

      let pushed = false;
      try {
        Object.keys(taskData.headers).forEach((k) => {
          if (!taskData.headers[k]) delete taskData.headers[k];
        });
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 2500);
        const resp = await fetch(`http://127.0.0.1:18910/api/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData),
          signal: controller.signal
        });
        clearTimeout(timer);
        if (resp && resp.ok) {
          pushed = true;
          pushBtn.textContent = t('cap_pushed', '已加入下载队列');
          pushBtn.className = 'catcatch-btn success';
          setTimeout(() => removeFloatingBar(), 1500);
          return;
        }
      } catch (err) {}

      if (!pushed) {
        chrome.runtime.sendMessage({
          action: 'PUSH_TO_CLIENT',
          data: taskData
        }, (res) => {
          if (res && res.success) {
            pushBtn.textContent = t('cap_pushed', '已加入下载队列');
            pushBtn.className = 'catcatch-btn success';
          } else {
            pushBtn.textContent = t('cap_client_offline', '客户端未连接');
          }
          setTimeout(() => removeFloatingBar(), 1500);
        });
      }
    });

    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(mediaInfo.url).then(() => {
        copyBtn.textContent = t('cap_copied_link', '已复制原链');
        setTimeout(() => (copyBtn.textContent = t('cap_copy_link', '复制原链')), 1500);
      });
    });

    copyB64Btn.addEventListener('click', () => {
      const b64 = toBase64(mediaInfo.url);
      navigator.clipboard.writeText(b64).then(() => {
        copyB64Btn.textContent = t('cap_copied_b64', '已复制Base64');
        setTimeout(() => (copyB64Btn.textContent = t('cap_copy_b64', '复制Base64')), 1500);
      });
    });
  }

  function removeFloatingBar() {
    if (autoHideTimer) {
      clearTimeout(autoHideTimer);
      autoHideTimer = null;
    }
    isMouseOverBtn = false;
    if (activeFloatingBtn) {
      activeFloatingBtn.remove();
      activeFloatingBtn = null;
    }
    if (activePanel) {
      activePanel.remove();
      activePanel = null;
    }
  }

  window.addEventListener('scroll', () => {
    if (activeFloatingBtn && activeFloatingBtn.__targetMedia) {
      const rect = activeFloatingBtn.__targetMedia.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        removeFloatingBar();
      } else {
        activeFloatingBtn.style.top = `${window.scrollY + rect.top + 10}px`;
        activeFloatingBtn.style.right = `${window.innerWidth - (window.scrollX + rect.right) + 12}px`;
      }
    }
  }, { passive: true });

  // 4. 针对主流短视频平台 (抖音/B站/快手/小红书) 的全自动嗅探与智能解析
  function initShortVideoAutoSniffer() {
    const host = window.location.hostname.toLowerCase();
    const isDouyin = host.includes('douyin.com') || host.includes('iesdouyin.com');
    const isBili = host.includes('bilibili.com');
    const isKwai = host.includes('kuaishou.com') || host.includes('kwai.com');
    const isXhs = host.includes('xiaohongshu.com');

    if (!isDouyin && !isBili && !isKwai && !isXhs) return;

    const seenUrls = new Set();

    function scanShortVideoElements() {
      const videos = document.querySelectorAll('video');
      videos.forEach((v) => {
        const src = v.currentSrc || v.src || '';
        if (!src || src.startsWith('blob:') || seenUrls.has(src) || isFragmentUrl(src)) return;

        seenUrls.add(src);

        // 提取精准标题
        let title = '';
        if (isDouyin) {
          const titleEl = document.querySelector('.title, .desc, [data-e2e="video-desc"], h1');
          if (titleEl && titleEl.textContent) title = titleEl.textContent.trim();
        } else if (isBili) {
          const titleEl = document.querySelector('.video-title, h1.tit, .bpx-player-top-left');
          if (titleEl && titleEl.textContent) title = titleEl.textContent.trim();
        } else if (isKwai) {
          const titleEl = document.querySelector('.video-info-title, .caption, h1');
          if (titleEl && titleEl.textContent) title = titleEl.textContent.trim();
        } else if (isXhs) {
          const titleEl = document.querySelector('.note-content .title, .title, #detail-title');
          if (titleEl && titleEl.textContent) title = titleEl.textContent.trim();
        }

        if (!title) {
          title = cleanVideoTitle(document.title);
        }

        chrome.runtime.sendMessage({
          action: 'SNIFFED_MEDIA',
          data: {
            url: src,
            title: title,
            pageUrl: window.location.href,
            mediaType: 'video',
            sourceType: 'short_video_auto'
          }
        }).catch(() => {});
      });
    }

    // 初始扫描 + 定时轮询 + 动态 DOM 监听
    scanShortVideoElements();
    setInterval(scanShortVideoElements, 1500);

    const observer = new MutationObserver(() => {
      scanShortVideoElements();
    });
    observer.observe(document.body || document.documentElement, {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initFloatingDownloadBar();
      initShortVideoAutoSniffer();
    });
  } else {
    initFloatingDownloadBar();
    initShortVideoAutoSniffer();
  }
})();

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

  // 严格过滤已知切片分片
  const FRAGMENT_REGEX = /(\.ts|\.m4s|\.m4v|\.vtt|\.srt|\.key|\.mp2t)(\?|#|$)|([-_/](seg|segment|chunk|frag|slice|part)[-_/\d]+)|(\b(init\.mp4|range=|\/stream\/segment))/i;

  // 2. 接收来自 inject.js 的深层嗅探消息
  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data || event.data.source !== 'CATCATCH_INJECTOR') return;
    const payload = event.data.payload;
    if (!payload || !payload.url || payload.url.startsWith('blob:') || FRAGMENT_REGEX.test(payload.url)) return;

    chrome.runtime.sendMessage({
      action: 'SNIFFED_MEDIA',
      data: payload
    }).catch(() => {});
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

  function showFloatingBarForMedia(mediaEl) {
    if (mediaEl.__catcatch_dismissed) return;

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
    btn.innerHTML = `
      <div class="catcatch-btn-main" style="display:inline-flex;align-items:center;gap:5px;">
        ${SVG_DOWNLOAD_ICON}
        <span>下载视频</span>
      </div>
      <span class="catcatch-close-badge" title="关闭悬浮角标">×</span>
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

  async function resolveRealMediaUrl(mediaEl) {
    const rawSrc = mediaEl.currentSrc || mediaEl.src || '';
    // 如果不是 blob:，且为标准网络链接，直接使用
    if (rawSrc && !rawSrc.startsWith('blob:') && (rawSrc.startsWith('http://') || rawSrc.startsWith('https://'))) {
      return { url: rawSrc, mediaType: 'video', format: 'MP4' };
    }

    // 若为 blob: 协议（MediaSource 流），向 background 获取该页面真实嗅探到的网络流 (如 m3u8 / mpd)
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: 'GET_MEDIA_FOR_TAB',
        pageUrl: window.location.href
      }, (res) => {
        if (res && res.media && res.media.length > 0) {
          // 优先选择流媒体 (m3u8 > mpd > video)
          const m3u8Item = res.media.find(i => i.mediaType === 'm3u8');
          const chosen = m3u8Item || res.media[0];
          resolve({
            url: chosen.url,
            mediaType: chosen.mediaType || 'm3u8',
            format: (chosen.mediaType || 'm3u8').toUpperCase(),
            resolution: chosen.resolution || '',
            duration: chosen.duration || 0
          });
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

    const title = document.title || '网页视频';
    const rect = anchorBtn.getBoundingClientRect();

    const panel = document.createElement('div');
    panel.className = 'catcatch-floating-panel';
    panel.style.top = `${window.scrollY + rect.bottom + 6}px`;
    panel.style.right = `${window.innerWidth - (window.scrollX + rect.right)}px`;

    panel.innerHTML = `
      <div class="catcatch-panel-title" title="${title}">${title}</div>
      <div id="catcatchPanelContent" class="catcatch-panel-info">正在定位真实视频流...</div>
      <div class="catcatch-config-row" style="display:flex;align-items:center;gap:6px;margin:6px 0;font-size:11px;color:#a1a1aa;">
        <span>下载代理:</span>
        <select id="catcatchProxySelect" style="flex:1;background:#27272a;color:#f4f4f5;border:1px solid #3f3f46;border-radius:4px;padding:3px 6px;font-size:11px;outline:none;">
          <option value="auto">🎯 自动匹配浏览器代理</option>
          <option value="default" selected>💻 跟随客户端全局设置</option>
          <option value="direct">⚡ 直连 (不走任何代理)</option>
          <option value="http://127.0.0.1:7890">Clash / Verge (7890)</option>
          <option value="socks5://127.0.0.1:10808">v2rayN SOCKS5 (10808)</option>
          <option value="http://127.0.0.1:10809">v2rayN HTTP (10809)</option>
        </select>
      </div>
      <div class="catcatch-panel-actions">
        <button id="catcatchPushBtn" class="catcatch-btn primary" disabled>推送到星流下载器</button>
        <button id="catcatchCopyCmdBtn" class="catcatch-btn" disabled>复制命令</button>
        <button id="catcatchCopyBtn" class="catcatch-btn" disabled>复制链接</button>
        <button id="catcatchCloseBtn" class="catcatch-btn">关闭</button>
      </div>
    `;

    document.body.appendChild(panel);
    activePanel = panel;

    // 解析真实地址
    const mediaInfo = await resolveRealMediaUrl(mediaEl);
    const contentDiv = panel.querySelector('#catcatchPanelContent');
    const proxySelect = panel.querySelector('#catcatchProxySelect');
    const pushBtn = panel.querySelector('#catcatchPushBtn');
    const copyCmdBtn = panel.querySelector('#catcatchCopyCmdBtn');
    const copyBtn = panel.querySelector('#catcatchCopyBtn');
    const closeBtn = panel.querySelector('#catcatchCloseBtn');

    closeBtn.addEventListener('click', () => removeFloatingBar());

    if (!mediaInfo) {
      contentDiv.innerHTML = `<span style="color:#fbbf24;">未抓取到流地址，请点击播放视频后重试</span>`;
      return;
    }

    const durSec = Math.floor(mediaEl.duration || 0);
    const durStr = durSec > 0 ? `${Math.floor(durSec / 60)}分${durSec % 60}秒` : '';
    const resStr = mediaInfo.resolution || ((mediaEl.videoWidth && mediaEl.videoHeight) ? `${mediaEl.videoWidth}x${mediaEl.videoHeight}` : '高清流');

    contentDiv.innerHTML = `
      <span class="catcatch-badge accent">${mediaInfo.format}</span>
      <span class="catcatch-badge">${resStr}</span>
      ${durStr ? `<span class="catcatch-badge">${durStr}</span>` : ''}
    `;

    pushBtn.disabled = false;
    copyCmdBtn.disabled = false;
    copyBtn.disabled = false;

    copyCmdBtn.addEventListener('click', () => {
      const pChoice = proxySelect.value;
      const safeTitle = (title || 'video').replace(/[\\/*?:"<>|]/g, '_');
      let cmd = `N_m3u8DL-RE "${mediaInfo.url}" --save-name "${safeTitle}" --auto-select -M format=mp4`;
      if (pChoice && pChoice !== 'default' && pChoice !== 'direct' && pChoice !== 'auto') {
        cmd += ` --custom-proxy "${pChoice}"`;
      }
      cmd += ` -H "Referer: ${window.location.href}" -H "User-Agent: ${navigator.userAgent}"`;

      navigator.clipboard.writeText(cmd).then(() => {
        copyCmdBtn.textContent = '已复制命令';
        setTimeout(() => (copyCmdBtn.textContent = '复制命令'), 1500);
      });
    });

    pushBtn.addEventListener('click', async () => {
      pushBtn.textContent = '正在推送...';
      pushBtn.disabled = true;

      const pVal = proxySelect.value;
      const taskData = {
        url: mediaInfo.url,
        title: title,
        saveName: title,
        mediaType: mediaInfo.mediaType,
        resolution: mediaInfo.resolution || resStr || '',
        duration: mediaInfo.duration || durSec || 0,
        proxy: pVal,
        headers: {
          Referer: window.location.href,
          'User-Agent': navigator.userAgent
        }
      };

      try {
        const resp = await fetch('http://127.0.0.1:18910/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData)
        });
        if (resp.ok) {
          pushBtn.textContent = '已加入下载队列';
          pushBtn.className = 'catcatch-btn success';
          setTimeout(() => removeFloatingBar(), 1500);
          return;
        }
      } catch (err) {
        chrome.runtime.sendMessage({
          action: 'PUSH_TO_CLIENT',
          data: taskData
        }, (res) => {
          if (res && res.success) {
            pushBtn.textContent = '已加入下载队列';
            pushBtn.className = 'catcatch-btn success';
          } else {
            pushBtn.textContent = '客户端未连接';
          }
          setTimeout(() => removeFloatingBar(), 1500);
        });
      }
    });

    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(mediaInfo.url).then(() => {
        copyBtn.textContent = '已复制';
        setTimeout(() => (copyBtn.textContent = '复制链接'), 1500);
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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFloatingDownloadBar);
  } else {
    initFloatingDownloadBar();
  }
})();

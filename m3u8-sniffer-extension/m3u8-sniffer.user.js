// ==UserScript==
// @name         M3U8 Sniffer - 视频嗅探下载助手
// @namespace    https://github.com/m3u8-sniffer
// @version      1.0.0
// @description  嗅探网页 M3U8/HLS 视频地址，一键生成 bat 下载脚本，配合 N_m3u8DL-RE 使用
// @author       M3U8 Sniffer
// @match        *://*/*
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_xmlhttpRequest
// @grant        GM_download
// @connect      *
// @run-at       document-start
// @license      MIT
// ==/UserScript==

(function() {
  'use strict';

  // ==================== 配置 ====================
  const M3U8_PATTERN = /\.m3u8([?#].*)?$/i;
  const MAX_ITEMS = 50;

  const DEFAULTS = {
    saveDir: '',
    version: 'RE',
    threadCount: 16,
    merge: true,
    delAfterDone: true,
    projectDir: '',
    configured: false,  // 是否已完成首次配置
  };

  // ==================== 存储 ====================
  function loadSettings() {
    const settings = {};
    for (const [k, v] of Object.entries(DEFAULTS)) {
      settings[k] = GM_getValue('setting_' + k, v);
    }
    return settings;
  }

  function saveSettings(settings) {
    for (const [k, v] of Object.entries(settings)) {
      GM_setValue('setting_' + k, v);
    }
  }

  // ==================== M3U8 嗅探 ====================
  const sniffedItems = [];
  const seenUrls = new Set();

  function addItem(url, initiator) {
    if (seenUrls.has(url)) return;
    seenUrls.add(url);

    // 计算 baseUrl
    let baseUrl = '';
    try {
      const u = new URL(url);
      const parts = u.pathname.split('/');
      parts.pop();
      baseUrl = u.origin + parts.join('/') + '/';
    } catch (e) {
      baseUrl = url.substring(0, url.lastIndexOf('/') + 1);
    }

    const item = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
      url: url,
      pageTitle: document.title || '',
      pageUrl: location.href,
      referer: location.href,
      userAgent: navigator.userAgent,
      origin: initiator || '',
      baseUrl: baseUrl,
      duration: 0,
      resolution: '',
      timestamp: Date.now(),
    };

    sniffedItems.unshift(item);
    if (sniffedItems.length > MAX_ITEMS) sniffedItems.length = MAX_ITEMS;
    updatePanelList();

    // 后台解析 M3U8 内容获取时长和分辨率
    fetchM3u8Metadata(item);
  }

  function fetchM3u8Metadata(item) {
    GM_xmlhttpRequest({
      method: 'GET',
      url: item.url,
      headers: {
        Referer: item.referer || item.pageUrl,
        'User-Agent': item.userAgent || navigator.userAgent,
      },
      onload: function(resp) {
        const text = resp.responseText;
        if (!text) return;

        let resolution = '';
        let totalDuration = 0;

        if (text.includes('#EXT-X-STREAM-INF')) {
          const re = /#EXT-X-STREAM-INF:.*RESOLUTION=(\d+x\d+)/gi;
          let match, maxW = 0;
          while ((match = re.exec(text)) !== null) {
            const [w, h] = match[1].split('x').map(Number);
            if (w > maxW) { maxW = w; resolution = match[1]; }
          }
        } else if (text.includes('#EXTINF')) {
          const re = /#EXTINF:([\d.]+)/gi;
          let match;
          while ((match = re.exec(text)) !== null) {
            totalDuration += parseFloat(match[1]) || 0;
          }
        }

        if (resolution || totalDuration > 0) {
          const found = sniffedItems.find(i => i.url === item.url);
          if (found) {
            found.resolution = resolution;
            found.duration = totalDuration;
            updatePanelList();
          }
        }
      },
      onerror: function() { /* 静默忽略 */ }
    });
  }

  // ==================== 请求拦截 ====================
  // 拦截 XMLHttpRequest
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function(method, url) {
    this._sniffUrl = url;
    return origOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function() {
    if (this._sniffUrl && M3U8_PATTERN.test(this._sniffUrl)) {
      addItem(this._sniffUrl, 'xhr');
    }
    return origSend.apply(this, arguments);
  };

  // 拦截 fetch
  const origFetch = window.fetch;
  window.fetch = function(input, init) {
    const url = typeof input === 'string' ? input : (input && input.url);
    if (url && M3U8_PATTERN.test(url)) {
      addItem(url, 'fetch');
    }
    return origFetch.apply(this, arguments);
  };

  // ==================== 浮动面板 UI ====================
  function createPanel() {
    const panel = document.createElement('div');
    panel.id = 'm3u8-sniffer-panel';
    panel.innerHTML = `
      <style>
        /* ===== 全局重置 — 隔绝页面CSS污染 ===== */
        #m3u8-sniffer-panel, #m3u8-sniffer-panel *,
        #m3u8-sniffer-panel *::before, #m3u8-sniffer-panel *::after {
          box-sizing: border-box;
          line-height: 1.4;
        }
        #m3u8-sniffer-panel {
          all: initial;
          position: fixed; bottom: 20px; right: 20px;
          z-index: 2147483647;
          width: 370px; max-height: 520px;
          background: #fff; color: #1a1a2e;
          border-radius: 12px; overflow: hidden;
          box-shadow: 0 8px 32px rgba(0,0,0,0.25);
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 13px;
          display: flex; flex-direction: column;
          transition: all 0.2s;
          color-scheme: only light;           /* 强制浅色模式，防止暗色页面污染表单控件 */
          -webkit-color-scheme: only light;
        }
        #m3u8-sniffer-panel.minimized { max-height: 44px; }
        /* 泛化重置：所有文本元素设为深色，防止从暗色页面继承白色 */
        #m3u8-sniffer-panel div, #m3u8-sniffer-panel span,
        #m3u8-sniffer-panel button, #m3u8-sniffer-panel input,
        #m3u8-sniffer-panel select, #m3u8-sniffer-panel label,
        #m3u8-sniffer-panel option, #m3u8-sniffer-panel optgroup,
        #m3u8-sniffer-panel textarea { color: #1a1a2e; }
        #m3u8-sniffer-panel option { background: #fff; }

        /* ===== Header ===== */
        .ms-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 10px 14px; flex-shrink: 0; cursor: move; user-select: none;
          background: linear-gradient(135deg, #4A3AD5, #6C5CE7); color: #fff !important;
        }
        .ms-header span, .ms-header button { color: #fff !important; }
        .ms-logo { font-weight: 700; font-size: 14px; letter-spacing: -0.3px; color: #fff !important; }
        .ms-badge {
          background: rgba(255,255,255,0.25); color: #fff !important;
          border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: 600;
        }
        .ms-header-btns { display: flex; gap: 4px; }
        .ms-btn-icon {
          width: 26px; height: 26px; border: none; border-radius: 5px;
          background: rgba(255,255,255,0.18); color: #fff !important;
          font-size: 14px; cursor: pointer; line-height: 26px; text-align: center;
          transition: background 0.15s;
        }
        .ms-btn-icon:hover { background: rgba(255,255,255,0.3); }

        /* ===== List ===== */
        .ms-list {
          flex: 1; overflow-y: auto; padding: 6px; max-height: 350px;
          background: #f8f9fc; color: #1a1a2e !important;
        }
        .ms-list::-webkit-scrollbar { width: 5px; }
        .ms-list::-webkit-scrollbar-thumb { background: #d6d3ea; border-radius: 3px; }
        .ms-empty {
          text-align: center; padding: 30px 20px; color: #999 !important;
        }
        .ms-empty div { color: #999 !important; }
        .ms-empty-icon { font-size: 28px; margin-bottom: 6px; }
        .ms-empty-hint { font-size: 11px; color: #bbb !important; }

        /* ===== Card ===== */
        .ms-card {
          background: #fff; color: #1a1a2e !important;
          border-radius: 8px; padding: 8px 10px; margin-bottom: 5px;
          border: 1px solid #ddd; transition: border-color 0.15s;
        }
        .ms-card:hover { border-color: #4A3AD5; }
        .ms-card-title {
          font-weight: 600; font-size: 12px; margin-bottom: 2px;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          color: #1a1a2e !important;
        }
        .ms-card-url {
          font-size: 10px; color: #888 !important;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          margin-bottom: 4px;
        }
        .ms-card-meta {
          display: flex; flex-wrap: wrap; gap: 3px; margin-bottom: 6px;
        }
        .ms-tag {
          font-size: 10px; padding: 2px 5px; border-radius: 3px;
          white-space: nowrap; max-width: 100%; overflow: hidden; text-overflow: ellipsis;
        }
        .ms-tag.dur { background: #e8f5e9; color: #2e7d32 !important; }
        .ms-tag.res { background: #e3f2fd; color: #1565c0 !important; }
        .ms-tag.ref { background: #f0edff; color: #4A3AD5 !important; }
        .ms-card-actions {
          display: flex; gap: 5px; align-items: center;
        }

        /* ===== Inputs ===== */
        .ms-input-sm {
          flex: 1; padding: 4px 7px; border: 1px solid #ccc;
          border-radius: 4px; font-size: 11px; color: #1a1a2e !important;
          background: #fff !important;
        }
        .ms-input-sm:focus { outline: none; border-color: #4A3AD5; }
        .ms-select-sm {
          padding: 4px 6px; border: 1px solid #ccc;
          border-radius: 4px; font-size: 11px; color: #1a1a2e !important;
          background: #fff !important;
        }
        .ms-btn-dl {
          padding: 4px 14px; background: #4A3AD5; color: #fff !important;
          border: none; border-radius: 5px; font-size: 11px; font-weight: 600;
          cursor: pointer; white-space: nowrap; transition: background 0.15s;
        }
        .ms-btn-dl:hover { background: #3B2CC4; }
        .ms-btn-dl.done { background: #00b894; color: #fff !important; }
        /* ===== Settings ===== */
        .ms-settings {
          border-top: 1px solid #e0e0e0; padding: 8px 12px;
          background: #fff; color: #1a1a2e !important;
          font-size: 11px; flex-shrink: 0;
        }
        .ms-setting-row {
          display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
          flex-wrap: wrap;
        }
        .ms-setting-row:last-child { margin-bottom: 0; }
        .ms-setting-row label { color: #555 !important; white-space: nowrap; font-size: 11px; }
        .ms-check-label {
          display: inline-flex; align-items: center; gap: 2px;
          cursor: pointer; font-size: 11px; color: #555 !important;
        }
      </style>
      <div class="ms-header" id="ms-header">
        <span class="ms-logo">🔍 M3U8 Sniffer</span>
        <span class="ms-badge" id="ms-count">0</span>
        <div class="ms-header-btns">
          <button class="ms-btn-icon" id="ms-setup" title="配置">⚙</button>
          <button class="ms-btn-icon" id="ms-clear" title="清空列表">✕</button>
          <button class="ms-btn-icon" id="ms-minimize" title="最小化">−</button>
        </div>
      </div>
      <div class="ms-list" id="ms-list">
        <div class="ms-empty">
          <div class="ms-empty-icon">📡</div>
          <div>正在监听 M3U8 请求...</div>
          <div class="ms-empty-hint">页面播放视频后地址会自动出现</div>
        </div>
      </div>
      <div class="ms-settings" id="ms-settings">
        <div class="ms-setting-row">
          <label>保存目录:</label>
          <input type="text" id="ms-saveDir" class="ms-input-sm" style="flex:1;min-width:100px">
          <label>线程:</label>
          <input type="number" id="ms-threads" class="ms-input-sm" style="width:50px;flex:0 0 50px" min="1" max="64">
        </div>
        <div class="ms-setting-row">
          <label class="ms-check-label"><input type="checkbox" id="ms-merge" checked> 合并</label>
          <label class="ms-check-label"><input type="checkbox" id="ms-del" checked> 删临时文件</label>
          <label>版本:</label>
          <select id="ms-version" class="ms-select-sm">
            <option value="RE">RE</option>
            <option value="V3">V3</option>
          </select>
        </div>
      </div>
    `;
    document.body.appendChild(panel);
    bindPanelEvents();
    applySettings();
  }

  function bindPanelEvents() {
    const panel = document.getElementById('m3u8-sniffer-panel');
    const header = document.getElementById('ms-header');

    // 拖拽
    let dragging = false, ox, oy, px, py;
    header.addEventListener('mousedown', function(e) {
      if (e.target.tagName === 'BUTTON') return;
      dragging = true;
      ox = e.clientX; oy = e.clientY;
      const rect = panel.getBoundingClientRect();
      px = rect.left; py = rect.top;
      panel.style.transition = 'none';
      e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
      if (!dragging) return;
      const dx = e.clientX - ox, dy = e.clientY - oy;
      panel.style.right = 'auto';
      panel.style.bottom = 'auto';
      panel.style.left = (px + dx) + 'px';
      panel.style.top = (py + dy) + 'px';
    });
    document.addEventListener('mouseup', function() {
      if (dragging) {
        dragging = false;
        panel.style.transition = 'all 0.2s';
        // 贴边吸附
        const rect = panel.getBoundingClientRect();
        if (rect.left < 5) panel.style.left = '5px';
        if (rect.top < 5) panel.style.top = '5px';
        if (rect.right > window.innerWidth - 5) {
          panel.style.left = 'auto';
          panel.style.right = '5px';
        }
        if (rect.bottom > window.innerHeight - 5) {
          panel.style.top = 'auto';
          panel.style.bottom = '5px';
        }
      }
    });

    // 最小化
    document.getElementById('ms-minimize').addEventListener('click', function() {
      panel.classList.toggle('minimized');
      this.textContent = panel.classList.contains('minimized') ? '+' : '−';
    });

    // 配置
    document.getElementById('ms-setup').addEventListener('click', showSetupDialog);

    // 清空
    document.getElementById('ms-clear').addEventListener('click', function() {
      if (!confirm('确定清空所有嗅探记录？')) return;
      sniffedItems.length = 0;
      seenUrls.clear();
      updatePanelList();
    });

    // 设置变更
    document.getElementById('ms-saveDir').addEventListener('change', onSettingChange);
    document.getElementById('ms-threads').addEventListener('change', onSettingChange);
    document.getElementById('ms-merge').addEventListener('change', onSettingChange);
    document.getElementById('ms-del').addEventListener('change', onSettingChange);
    document.getElementById('ms-version').addEventListener('change', onSettingChange);

    // 事件委托：下载按钮
    document.getElementById('ms-list').addEventListener('click', function(e) {
      const btn = e.target.closest('.ms-btn-dl');
      if (btn && btn.dataset.id) downloadBat(btn.dataset.id, btn);
    });
  }

  function applySettings() {
    const s = loadSettings();
    const saveDirEl = document.getElementById('ms-saveDir');
    if (saveDirEl) saveDirEl.value = s.saveDir || s.projectDir || '';
    const threadsEl = document.getElementById('ms-threads');
    if (threadsEl) threadsEl.value = s.threadCount;
    const mergeEl = document.getElementById('ms-merge');
    if (mergeEl) mergeEl.checked = s.merge;
    const delEl = document.getElementById('ms-del');
    if (delEl) delEl.checked = s.delAfterDone;
    const verEl = document.getElementById('ms-version');
    if (verEl) verEl.value = s.version;
  }

  function onSettingChange() {
    const settings = {
      saveDir: document.getElementById('ms-saveDir').value || DEFAULTS.saveDir,
      threadCount: Math.max(1, Math.min(64, parseInt(document.getElementById('ms-threads').value) || DEFAULTS.threadCount)),
      merge: document.getElementById('ms-merge').checked,
      delAfterDone: document.getElementById('ms-del').checked,
      version: document.getElementById('ms-version').value,
    };
    saveSettings(settings);
    // 同步回输入框
    document.getElementById('ms-threads').value = settings.threadCount;
  }

  function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return h > 0 ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` : `${m}:${String(s).padStart(2,'0')}`;
  }

  function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return [d.getHours(), d.getMinutes(), d.getSeconds()].map(n => String(n).padStart(2,'0')).join(':');
  }

  function updatePanelList() {
    const listEl = document.getElementById('ms-list');
    const countEl = document.getElementById('ms-count');
    if (!listEl) return;

    countEl.textContent = sniffedItems.length;
    const settings = loadSettings();

    if (sniffedItems.length === 0) {
      listEl.innerHTML = `
        <div class="ms-empty">
          <div class="ms-empty-icon">📡</div>
          <div>正在监听 M3U8 请求...</div>
          <div class="ms-empty-hint">页面播放视频后地址会自动出现</div>
        </div>`;
      return;
    }

    const esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

    listEl.innerHTML = sniffedItems.map(item => `
      <div class="ms-card">
        <div class="ms-card-title">${esc(item.pageTitle || '(未知标题)')}</div>
        <div class="ms-card-url" title="${esc(item.url)}">${esc(item.url.length > 55 ? item.url.slice(0,52)+'...' : item.url)}</div>
        <div class="ms-card-meta">
          ${item.duration ? `<span class="ms-tag dur">⏱ ${formatDuration(item.duration)}</span>` : ''}
          ${item.resolution ? `<span class="ms-tag res">📐 ${esc(item.resolution)}</span>` : ''}
          ${item.referer ? `<span class="ms-tag ref">🔗 ${esc(item.referer.length > 25 ? item.referer.slice(0,22)+'...' : item.referer)}</span>` : ''}
          <span class="ms-tag ref">🕐 ${formatTime(item.timestamp)}</span>
        </div>
        <div class="ms-card-actions">
          <input type="text" class="ms-input-sm ms-dir" value="${esc(settings.saveDir || settings.projectDir)}" placeholder="保存目录">
          <select class="ms-select-sm ms-ver">
            <option value="RE" ${settings.version==='RE'?'selected':''}>RE</option>
            <option value="V3" ${settings.version==='V3'?'selected':''}>V3</option>
          </select>
          <button class="ms-btn-dl" data-id="${item.id}">⬇ 下载</button>
        </div>
      </div>
    `).join('');
  }

  // ==================== 生成 bat 并下载 ====================
  function downloadBat(id, btn) {
    const item = sniffedItems.find(i => i.id === id);
    if (!item) return;

    const settings = loadSettings();
    if (!settings.configured || !settings.projectDir) {
      alert('请先完成配置：点击面板标题栏的 ⚙ 按钮，填写 N_m3u8DL 项目目录路径。');
      showSetupDialog();
      return;
    }

    const card = btn.closest('.ms-card');
    const saveDir = card.querySelector('.ms-dir')?.value || settings.saveDir || settings.projectDir;
    const version = card.querySelector('.ms-ver')?.value || settings.version;

    let saveName = (item.pageTitle || 'video').replace(/[<>:"/\\|?*]/g, '_').trim() || 'video';

    const projectDir = settings.projectDir;
    const exeName = version === 'V3' ? 'N_m3u8DL-CLI_v3.0.2.exe' : 'N_m3u8DL-RE.exe';
    const exePath = projectDir + '\\' + exeName;

    // 构造命令行
    let cmd;
    if (version === 'V3') {
      cmd = `"${exePath}" "${item.url}" --workDir "${saveDir}" --saveName "${saveName}"`;
      if (item.referer) cmd += ` --headers "Referer:${item.referer}|User-Agent:${item.userAgent || navigator.userAgent}"`;
      cmd += ` --maxThreads "${settings.threadCount}"`;
      if (settings.delAfterDone) cmd += ` --enableDelAfterDone`;
    } else {
      cmd = `"${exePath}" "${item.url}" --save-dir "${saveDir}" --save-name "${saveName}"`;
      if (item.baseUrl) cmd += ` --base-url "${item.baseUrl}"`;
      if (item.referer) cmd += ` -H "Referer: ${item.referer}" -H "User-Agent: ${item.userAgent || navigator.userAgent}"`;
      cmd += ` --thread-count ${settings.threadCount}`;
      if (!settings.merge) cmd += ` --skip-merge`;
      if (settings.delAfterDone) cmd += ` --del-after-done`;
    }

    // 生成完整的 bat 文件内容
    const batContent = [
      '@echo off',
      'chcp 65001 >nul',
      `cd /d "${projectDir}"`,
      'echo 启动下载: ' + saveName,
      cmd,
      'echo.',
      'echo 下载完成，按任意键关闭...',
      'pause >nul',
    ].join('\r\n');

    // 触发浏览器下载
    const blob = new Blob([batContent], { type: 'application/bat' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = saveName + '.bat';
    a.click();
    URL.revokeObjectURL(a.href);

    btn.textContent = '✓ 已生成';
    btn.classList.add('done');
  }

  // ==================== 首次配置对话框 ====================
  function showSetupDialog() {
    // 移除已有对话框
    const existing = document.getElementById('ms-setup-overlay');
    if (existing) existing.remove();

    const settings = loadSettings();

    const overlay = document.createElement('div');
    overlay.id = 'ms-setup-overlay';
    overlay.innerHTML = `
      <style>
        /* 隔绝页面 CSS 污染 */
        #ms-setup-overlay, #ms-setup-overlay *,
        #ms-setup-overlay *::before, #ms-setup-overlay *::after { box-sizing: border-box; }
        #ms-setup-overlay {
          all: initial;
          position: fixed; inset: 0; z-index: 2147483648;
          background: rgba(0,0,0,0.55); color: #1a1a2e;
          display: flex; align-items: center; justify-content: center;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 13px;
          color-scheme: only light;
          -webkit-color-scheme: only light;
        }
        #ms-setup-overlay div, #ms-setup-overlay h2,
        #ms-setup-overlay input, #ms-setup-overlay select,
        #ms-setup-overlay label, #ms-setup-overlay button,
        #ms-setup-overlay option { color: #1a1a2e; }
        #ms-setup-overlay option { background: #fff; }
        .ms-setup-box {
          background: #fff; color: #1a1a2e; border-radius: 14px;
          padding: 28px 32px; width: 420px; max-width: 90vw;
          box-shadow: 0 16px 48px rgba(0,0,0,0.3); font-size: 13px;
        }
        .ms-setup-box h2 {
          margin: 0 0 6px; font-size: 18px; color: #4A3AD5;
        }
        .ms-setup-box .ms-sub { color: #888; font-size: 12px; margin-bottom: 18px; }
        .ms-setup-row {
          display: flex; align-items: center; margin-bottom: 12px; gap: 8px;
        }
        .ms-setup-row label {
          min-width: 90px; font-weight: 600; color: #333; font-size: 13px;
        }
        .ms-setup-row input, .ms-setup-row select {
          flex: 1; padding: 7px 10px; border: 1px solid #ddd;
          border-radius: 6px; font-size: 13px;
          color: #1a1a2e; background: #fff;
        }
        .ms-setup-row input:focus, .ms-setup-row select:focus {
          outline: none; border-color: #4A3AD5;
          box-shadow: 0 0 0 2px rgba(74,58,213,0.15);
        }
        .ms-setup-hint {
          font-size: 11px; color: #999; margin-top: -8px; margin-bottom: 10px;
          margin-left: 98px;
        }
        .ms-setup-btns {
          display: flex; gap: 8px; justify-content: flex-end; margin-top: 18px;
        }
        .ms-setup-btn {
          padding: 8px 24px; border: none; border-radius: 6px;
          font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.15s;
        }
        .ms-setup-btn.primary { background: #4A3AD5; color: #fff; }
        .ms-setup-btn.primary:hover { background: #3B2CC4; }
        .ms-setup-btn.ghost { background: #f0f0f0; color: #666; }
        .ms-setup-btn.ghost:hover { background: #e0e0e0; }
        .ms-setup-error {
          color: #e74c3c; font-size: 12px; margin-top: 8px; display: none;
        }
      </style>
      <div class="ms-setup-box">
        <h2>⚙ 首次配置</h2>
        <div class="ms-sub">请填写 N_m3u8DL 所在的目录路径，之后即可正常使用。</div>
        <div class="ms-setup-row">
          <label>项目目录</label>
          <input type="text" id="ms-cfg-projectDir" placeholder="例如: D:\\Tools\\N_m3u8DL" value="${escHtml(settings.projectDir)}" style="flex:1">
        </div>
        <div class="ms-setup-hint">N_m3u8DL-RE.exe / N_m3u8DL-CLI_v3.0.2.exe 所在的文件夹路径</div>
        <div class="ms-setup-row">
          <label>默认保存目录</label>
          <input type="text" id="ms-cfg-saveDir" placeholder="例如: D:\\Downloads" value="${escHtml(settings.saveDir)}" style="flex:1">
        </div>
        <div class="ms-setup-hint">下载的视频保存到哪里</div>
        <div class="ms-setup-row">
          <label>默认线程数</label>
          <input type="number" id="ms-cfg-threads" min="1" max="64" value="${settings.threadCount}" style="max-width:80px">
        </div>
        <div class="ms-setup-row">
          <label>CLI 版本</label>
          <select id="ms-cfg-version">
            <option value="RE" ${settings.version==='RE'?'selected':''}>N_m3u8DL-RE (推荐)</option>
            <option value="V3" ${settings.version==='V3'?'selected':''}>N_m3u8DL-CLI v3.0.2</option>
          </select>
        </div>
        <div class="ms-setup-error" id="ms-setup-error"></div>
        <div class="ms-setup-btns">
          <button class="ms-setup-btn ghost" id="ms-setup-cancel">取消</button>
          <button class="ms-setup-btn primary" id="ms-setup-save">保存配置</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    // 事件
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) overlay.remove();
    });
    document.getElementById('ms-setup-cancel').addEventListener('click', function() {
      overlay.remove();
    });
    document.getElementById('ms-setup-save').addEventListener('click', function() {
      const projectDir = document.getElementById('ms-cfg-projectDir').value.trim();
      const saveDir = document.getElementById('ms-cfg-saveDir').value.trim();
      const errEl = document.getElementById('ms-setup-error');

      if (!projectDir) {
        errEl.textContent = '请填写项目目录路径（N_m3u8DL 所在文件夹）';
        errEl.style.display = 'block';
        return;
      }

      const newSettings = {
        projectDir: projectDir,
        saveDir: saveDir || projectDir,
        threadCount: Math.max(1, Math.min(64, parseInt(document.getElementById('ms-cfg-threads').value) || 16)),
        version: document.getElementById('ms-cfg-version').value,
        merge: true,
        delAfterDone: true,
        configured: true,
      };
      saveSettings(newSettings);
      applySettings();
      overlay.remove();
      console.log('[M3U8 Sniffer] 配置已保存:', newSettings);
    });

    // ESC 关闭
    overlay.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') overlay.remove();
    });
    document.getElementById('ms-cfg-projectDir').focus();
  }

  function escHtml(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // ==================== 启动 ====================
  function tryCreatePanel(retries) {
    retries = retries || 0;
    if (document.body) {
      createPanel();
      // 首次使用弹配置框
      const settings = loadSettings();
      if (!settings.configured) {
        setTimeout(showSetupDialog, 500);
      }
      console.log('[M3U8 Sniffer] 面板已就绪 — 正在监听 M3U8 请求...');
      return;
    }
    if (retries < 20) {
      setTimeout(function() { tryCreatePanel(retries + 1); }, 200);
    } else {
      console.error('[M3U8 Sniffer] 面板创建失败: document.body 超时');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      tryCreatePanel();
    });
  } else {
    tryCreatePanel();
  }

  console.log('[M3U8 Sniffer] 油猴脚本已加载 — 正在监听页面 M3U8 请求...');
})();

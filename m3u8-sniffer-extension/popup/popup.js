// popup.js - CatCatch Pro Modern Minimalist Controller
(function () {
  'use strict';

  let currentCategory = 'all';
  let searchKeyword = '';
  let mediaList = [];
  let selectedIds = new Set();
  let clientOnline = false;
  let clientPort = 18910;
  let activeHls = null;
  let detectedProxy = { mode: 'system', proxyUrl: '', label: '跟随系统代理' };

  // DOM 元素引用
  const mediaListContainer = document.getElementById('mediaListContainer');
  const emptyPlaceholder = document.getElementById('emptyPlaceholder');
  const clientStatusBadge = document.getElementById('clientStatusBadge');
  const clientStatusText = document.getElementById('clientStatusText');
  const selectAllCheckbox = document.getElementById('selectAllCheckbox');
  const searchInput = document.getElementById('searchInput');
  const batchBar = document.getElementById('batchBar');
  const batchCountText = document.getElementById('batchCountText');
  const previewModal = document.getElementById('previewModal');
  const previewVideo = document.getElementById('previewVideo');
  const previewAudio = document.getElementById('previewAudio');
  const previewTitle = document.getElementById('previewTitle');
  const settingsPanel = document.getElementById('settingsPanel');

  document.addEventListener('DOMContentLoaded', async () => {
    // 弹窗打开表示用户已查阅当前页面的嗅探结果，清除未读角标提示
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs && tabs[0] && tabs[0].id) {
        chrome.action.setBadgeText({ tabId: tabs[0].id, text: '' });
      }
    });
    chrome.action.setBadgeText({ text: '' });

    bindEvents();
    try {
      chrome.runtime.sendMessage({ action: 'DETECT_BROWSER_PROXY' }, (res) => {
        if (res) {
          detectedProxy = res;
          document.querySelectorAll('.cfg-proxy-tip').forEach((el) => {
            el.textContent = detectedProxy.proxyUrl
              ? `⚡ 检测到当前浏览器代理: ${detectedProxy.proxyUrl}`
              : (detectedProxy.label ? `⚡ 当前浏览器网络环境: ${detectedProxy.label}` : '⚡ 当前浏览器代理: 跟随系统');
          });
        }
      });
    } catch (e) {}
    await loadSettings();
    await checkClientStatus();
    loadAndRenderMedia();

    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === 'local' && changes.mediaList) {
        mediaList = changes.mediaList.newValue || [];
        renderList();
        updateCategoryCounts();
      }
    });
  });

  function bindEvents() {
    document.querySelectorAll('.tab-item').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-item').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentCategory = btn.dataset.cat;
        renderList();
      });
    });

    searchInput.addEventListener('input', (e) => {
      searchKeyword = e.target.value.trim().toLowerCase();
      renderList();
    });

    selectAllCheckbox.addEventListener('change', (e) => {
      const checked = e.target.checked;
      const visibleItems = getFilteredItems();
      if (checked) {
        visibleItems.forEach((it) => selectedIds.add(it.id));
      } else {
        visibleItems.forEach((it) => selectedIds.delete(it.id));
      }
      renderList();
      updateBatchBar();
    });

    document.getElementById('btnClear').addEventListener('click', async () => {
      if (confirm('确定要清空全部已嗅探的媒体记录吗？')) {
        await chrome.storage.local.set({ mediaList: [] });
        selectedIds.clear();
        mediaList = [];
        renderList();
        updateCategoryCounts();
        chrome.action.setBadgeText({ text: '' });
      }
    });

    document.getElementById('btnBatchPush').addEventListener('click', async () => {
      const selectedItems = mediaList.filter((it) => selectedIds.has(it.id));
      if (!selectedItems.length) return;

      const btn = document.getElementById('btnBatchPush');
      btn.textContent = '推送中...';
      btn.disabled = true;

      const tasks = selectedItems.map((it) => ({
        url: it.url,
        title: it.pageTitle || 'video',
        saveName: it.pageTitle || 'video',
        mediaType: it.mediaType,
        resolution: it.resolution || '',
        duration: it.duration || 0,
        headers: {
          Referer: it.referer || '',
          'User-Agent': it.userAgent || '',
          Cookie: it.cookie || ''
        },
        baseUrl: it.baseUrl || ''
      }));

      try {
        const resp = await fetch(`http://127.0.0.1:${clientPort}/api/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tasks)
        });
        if (resp.ok) {
          btn.textContent = `已推送 ${tasks.length} 项`;
          setTimeout(() => {
            btn.textContent = '批量推送到客户端';
            btn.disabled = false;
          }, 2000);
          return;
        }
      } catch (err) {}

      chrome.runtime.sendMessage({ action: 'PUSH_TO_CLIENT', data: tasks }, (res) => {
        btn.textContent = res && res.success ? `已推送 ${tasks.length} 项` : '客户端未运行';
        setTimeout(() => {
          btn.textContent = '批量推送到客户端';
          btn.disabled = false;
        }, 2000);
      });
    });

    document.getElementById('btnBatchCopy').addEventListener('click', () => {
      const selectedItems = mediaList.filter((it) => selectedIds.has(it.id));
      const urls = selectedItems.map((it) => it.url).join('\n');
      navigator.clipboard.writeText(urls).then(() => {
        const btn = document.getElementById('btnBatchCopy');
        btn.textContent = '已复制全部';
        setTimeout(() => (btn.textContent = '复制链接'), 1500);
      });
    });

    document.getElementById('btnBatchDelete').addEventListener('click', async () => {
      mediaList = mediaList.filter((it) => !selectedIds.has(it.id));
      selectedIds.clear();
      await chrome.storage.local.set({ mediaList });
      renderList();
      updateCategoryCounts();
      updateBatchBar();
    });

    document.getElementById('closePreviewBtn').addEventListener('click', closePreviewModal);
    previewModal.addEventListener('click', (e) => {
      if (e.target === previewModal) closePreviewModal();
    });

    document.getElementById('btnSettings').addEventListener('click', () => {
      settingsPanel.classList.remove('hidden');
    });
    document.getElementById('closeSettingsBtn').addEventListener('click', () => {
      settingsPanel.classList.add('hidden');
    });
    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);
  }

  async function checkClientStatus() {
    try {
      const resp = await fetch(`http://127.0.0.1:${clientPort}/api/status`, {
        method: 'GET',
        cache: 'no-store'
      });
      if (resp.ok) {
        clientOnline = true;
        clientStatusBadge.className = 'status-pill online';
        clientStatusText.textContent = '客户端已连接';
        return;
      }
    } catch (e) {}

    clientOnline = false;
    clientStatusBadge.className = 'status-pill offline';
    clientStatusText.textContent = '客户端离线';
    clientStatusBadge.onclick = () => {
      settingsPanel.classList.remove('hidden');
    };
  }

  async function loadSettings() {
    const { settings = {} } = await chrome.storage.local.get('settings');
    clientPort = settings.serverPort || 18910;
    document.getElementById('settingPort').value = clientPort;
    document.getElementById('settingAutoPush').checked = !!settings.autoPush;
    document.getElementById('settingMinSize').value = settings.minSizeKB || 0;
  }

  async function saveSettings() {
    const port = parseInt(document.getElementById('settingPort').value, 10) || 18910;
    const autoPush = document.getElementById('settingAutoPush').checked;
    const minSizeKB = parseInt(document.getElementById('settingMinSize').value, 10) || 0;

    clientPort = port;
    await chrome.storage.local.set({
      settings: { serverPort: port, autoPush, minSizeKB }
    });

    settingsPanel.classList.add('hidden');
    await checkClientStatus();
  }

  async function loadAndRenderMedia() {
    const res = await chrome.storage.local.get('mediaList');
    mediaList = res.mediaList || [];
    renderList();
    updateCategoryCounts();
  }

  function getFilteredItems() {
    return mediaList.filter((item) => {
      if (currentCategory !== 'all' && item.mediaType !== currentCategory) {
        return false;
      }
      if (searchKeyword) {
        const title = (item.pageTitle || '').toLowerCase();
        const url = (item.url || '').toLowerCase();
        if (!title.includes(searchKeyword) && !url.includes(searchKeyword)) {
          return false;
        }
      }
      return true;
    });
  }

  function updateCategoryCounts() {
    document.getElementById('countAll').textContent = mediaList.length;
    document.getElementById('countM3u8').textContent = mediaList.filter((i) => i.mediaType === 'm3u8').length;
    document.getElementById('countVideo').textContent = mediaList.filter((i) => i.mediaType === 'video').length;
    document.getElementById('countAudio').textContent = mediaList.filter((i) => i.mediaType === 'audio').length;
    document.getElementById('countOther').textContent = mediaList.filter((i) => i.mediaType === 'other').length;
  }

  function updateBatchBar() {
    const count = selectedIds.size;
    if (count > 0) {
      batchBar.classList.remove('hidden');
      batchCountText.textContent = `已选 ${count} 项`;
    } else {
      batchBar.classList.add('hidden');
    }
  }

  function renderList() {
    const items = getFilteredItems();
    mediaListContainer.innerHTML = '';

    if (!items.length) {
      mediaListContainer.appendChild(emptyPlaceholder);
      return;
    }

    items.forEach((item) => {
      const card = createMediaCard(item);
      mediaListContainer.appendChild(card);
    });
  }

  function createMediaCard(item) {
    const card = document.createElement('div');
    card.className = 'media-card';

    const isChecked = selectedIds.has(item.id);
    const domain = getDomain(item.url);
    const title = item.pageTitle || '未命名媒体';

    let tagsHtml = `<span class="tag-badge tag-type">${item.mediaType.toUpperCase()}</span>`;
    if (item.resolution) {
      tagsHtml += `<span class="tag-badge tag-res">${item.resolution}</span>`;
    }
    if (item.duration > 0) {
      const m = Math.floor(item.duration / 60);
      const s = item.duration % 60;
      tagsHtml += `<span class="tag-badge tag-dur">${m}:${s < 10 ? '0' : ''}${s}</span>`;
    }
    if (item.contentLength > 0) {
      tagsHtml += `<span class="tag-badge tag-size">${formatSize(item.contentLength)}</span>`;
    }
    if (item.hasKey) {
      tagsHtml += `<span class="tag-badge tag-key">加密 (KEY)</span>`;
    }
    tagsHtml += `<span class="tag-badge tag-domain">${domain}</span>`;

    const proxyTipText = detectedProxy.proxyUrl
      ? `⚡ 检测到当前浏览器代理: ${detectedProxy.proxyUrl}`
      : (detectedProxy.label ? `⚡ 当前浏览器网络环境: ${detectedProxy.label}` : '⚡ 当前浏览器代理: 跟随系统');

    card.innerHTML = `
      <div class="card-top">
        <input type="checkbox" class="card-checkbox" ${isChecked ? 'checked' : ''}>
        <div class="card-title-wrap">
          <input type="text" class="card-title-input" value="${escapeHtml(title)}" title="点击修改保存名称">
        </div>
      </div>
      <div class="card-tags">${tagsHtml}</div>
      <div class="card-url-box" title="点击复制完整直链">${escapeHtml(item.url)}</div>
      <div class="card-actions">
        <button class="btn-sm btn-primary action-push">下载 (推送)</button>
        <button class="btn-sm btn-secondary action-config" title="配置该视频独立保存目录、线程数与代理">⚙️ 配置</button>
        <button class="btn-sm btn-secondary action-copy-cmd" title="复制 N_m3u8DL-RE 独立运行命令 (免客户端)">复制命令</button>
        <button class="btn-sm btn-secondary action-preview">预览</button>
        <button class="btn-sm btn-secondary action-copy">复制</button>
        <button class="btn-sm btn-danger action-del">删除</button>
      </div>
      <div class="card-config-panel hidden">
        <div class="config-row">
          <span class="config-label">📁 保存目录:</span>
          <input type="text" class="config-input cfg-savedir" placeholder="留空使用客户端配置 (如 D:\\Downloads)">
        </div>
        <div class="config-row">
          <span class="config-label">⚡ 并发线程:</span>
          <select class="config-select cfg-threads">
            <option value="">跟随客户端设置 (默认 16)</option>
            <option value="4">4 线程 (稳定防限流)</option>
            <option value="8">8 线程 (平衡加速)</option>
            <option value="16">16 线程 (极速推荐)</option>
            <option value="32">32 线程 (极限并发)</option>
          </select>
        </div>
        <div class="config-row">
          <span class="config-label">🌐 下载代理:</span>
          <select class="config-select cfg-proxy">
            <option value="auto">🎯 自动匹配浏览器代理</option>
            <option value="default" selected>💻 跟随客户端全局设置</option>
            <option value="direct">⚡ 直连 (不走任何代理)</option>
            <option value="http://127.0.0.1:7890">Clash / Verge (7890)</option>
            <option value="socks5://127.0.0.1:10808">v2rayN SOCKS5 (10808)</option>
            <option value="http://127.0.0.1:10809">v2rayN HTTP (10809)</option>
            <option value="custom">✏️ 手动输入代理地址...</option>
          </select>
        </div>
        <div class="config-row cfg-custom-proxy-row hidden">
          <span class="config-label">代理地址:</span>
          <input type="text" class="config-input cfg-custom-proxy" placeholder="例如 http://127.0.0.1:7890 或 socks5://127.0.0.1:10808">
        </div>
        <div class="config-tip cfg-proxy-tip">${proxyTipText}</div>
        <button class="btn-copy-cli-inside">📋 复制 N_m3u8DL-RE 完整运行命令 (脱离客户端独立运行)</button>
      </div>
    `;

    const checkbox = card.querySelector('.card-checkbox');
    checkbox.addEventListener('change', (e) => {
      if (e.target.checked) selectedIds.add(item.id);
      else selectedIds.delete(item.id);
      updateBatchBar();
    });

    const titleInput = card.querySelector('.card-title-input');
    titleInput.addEventListener('change', (e) => {
      item.pageTitle = e.target.value.trim();
      chrome.storage.local.set({ mediaList });
    });

    const urlBox = card.querySelector('.card-url-box');
    urlBox.addEventListener('click', () => {
      navigator.clipboard.writeText(item.url).then(() => {
        const oldText = urlBox.textContent;
        urlBox.textContent = '已复制直链到剪贴板';
        setTimeout(() => (urlBox.textContent = oldText), 1500);
      });
    });

    // 展开/收起视频独立下载配置面板
    const configBtn = card.querySelector('.action-config');
    const configPanel = card.querySelector('.card-config-panel');
    configBtn.addEventListener('click', () => {
      configPanel.classList.toggle('hidden');
    });

    const proxySelect = configPanel.querySelector('.cfg-proxy');
    const customProxyRow = configPanel.querySelector('.cfg-custom-proxy-row');
    const customProxyInput = configPanel.querySelector('.cfg-custom-proxy');
    proxySelect.addEventListener('change', () => {
      if (proxySelect.value === 'custom') {
        customProxyRow.classList.remove('hidden');
      } else {
        customProxyRow.classList.add('hidden');
      }
    });

    function getTaskConfigOptions() {
      const saveDir = configPanel.querySelector('.cfg-savedir').value.trim();
      const threadCount = configPanel.querySelector('.cfg-threads').value;
      const pVal = proxySelect.value;
      let finalProxy = '';
      if (pVal === 'auto') {
        finalProxy = detectedProxy.proxyUrl || (detectedProxy.mode === 'direct' ? 'direct' : 'default');
      } else if (pVal === 'custom') {
        finalProxy = customProxyInput.value.trim();
      } else {
        finalProxy = pVal;
      }
      return { saveDir, threadCount, proxy: finalProxy };
    }

    function copyCliCommand(btnSource) {
      const cfg = getTaskConfigOptions();
      let proxyForCmd = '';
      if (cfg.proxy && cfg.proxy !== 'default' && cfg.proxy !== 'direct') {
        proxyForCmd = cfg.proxy;
      } else if (cfg.proxy === 'auto' && detectedProxy.proxyUrl) {
        proxyForCmd = detectedProxy.proxyUrl;
      }

      let cmd = `N_m3u8DL-RE "${item.url}"`;
      if (cfg.saveDir) {
        cmd += ` --save-dir "${cfg.saveDir}"`;
      }
      const safeTitle = (titleInput.value.trim() || item.pageTitle || 'video').replace(/[\\/*?:"<>|]/g, '_');
      cmd += ` --save-name "${safeTitle}"`;
      if (cfg.threadCount) {
        cmd += ` --thread-count ${cfg.threadCount}`;
      }
      cmd += ` --auto-select -M format=mp4`;
      if (proxyForCmd) {
        cmd += ` --custom-proxy "${proxyForCmd}"`;
      }
      if (item.referer) {
        cmd += ` -H "Referer: ${item.referer}"`;
      }
      if (item.userAgent) {
        cmd += ` -H "User-Agent: ${item.userAgent}"`;
      }

      navigator.clipboard.writeText(cmd).then(() => {
        const originalText = btnSource.textContent;
        btnSource.textContent = '已复制 N_m3u8DL 命令！';
        setTimeout(() => (btnSource.textContent = originalText), 1800);
      });
    }

    const copyCmdBtn = card.querySelector('.action-copy-cmd');
    copyCmdBtn.addEventListener('click', () => copyCliCommand(copyCmdBtn));

    const copyInsideBtn = configPanel.querySelector('.btn-copy-cli-inside');
    copyInsideBtn.addEventListener('click', () => copyCliCommand(copyInsideBtn));

    const pushBtn = card.querySelector('.action-push');
    pushBtn.addEventListener('click', async () => {
      pushBtn.textContent = '推送中...';
      pushBtn.disabled = true;

      const cfg = getTaskConfigOptions();
      const taskData = {
        url: item.url,
        title: titleInput.value.trim() || item.pageTitle || 'video',
        saveName: titleInput.value.trim() || item.pageTitle || 'video',
        mediaType: item.mediaType,
        resolution: item.resolution || '',
        duration: item.duration || 0,
        headers: {
          Referer: item.referer || '',
          'User-Agent': item.userAgent || '',
          Cookie: item.cookie || ''
        },
        baseUrl: item.baseUrl || '',
        saveDir: cfg.saveDir,
        threadCount: cfg.threadCount,
        proxy: cfg.proxy
      };

      try {
        const resp = await fetch(`http://127.0.0.1:${clientPort}/api/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData)
        });
        if (resp.ok) {
          pushBtn.textContent = '已加入队列';
          pushBtn.style.backgroundColor = '#166534';
          pushBtn.style.color = '#ffffff';
          return;
        }
      } catch (err) {}

      chrome.runtime.sendMessage({ action: 'PUSH_TO_CLIENT', data: taskData }, (res) => {
        if (res && res.success) {
          pushBtn.textContent = '已加入队列';
          pushBtn.style.backgroundColor = '#166534';
          pushBtn.style.color = '#ffffff';
        } else {
          pushBtn.textContent = '客户端离线';
          pushBtn.disabled = false;
        }
      });
    });

    const previewBtn = card.querySelector('.action-preview');
    previewBtn.addEventListener('click', () => {
      openPreviewModal(item);
    });

    const copyBtn = card.querySelector('.action-copy');
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(item.url).then(() => {
        copyBtn.textContent = '已复制';
        setTimeout(() => (copyBtn.textContent = '复制'), 1500);
      });
    });

    const delBtn = card.querySelector('.action-del');
    delBtn.addEventListener('click', async () => {
      mediaList = mediaList.filter((it) => it.id !== item.id);
      selectedIds.delete(item.id);
      await chrome.storage.local.set({ mediaList });
      renderList();
      updateCategoryCounts();
      updateBatchBar();

      // 同步更新剩余角标
      if (item.tabId !== undefined && item.tabId >= 0) {
        const remaining = mediaList.filter((i) => i.tabId === item.tabId).length;
        const text = remaining > 0 ? (remaining > 99 ? '99+' : String(remaining)) : '';
        chrome.action.setBadgeText({ tabId: item.tabId, text });
      }
      if (mediaList.length === 0) {
        chrome.action.setBadgeText({ text: '' });
      }
    });

    return card;
  }

  function openPreviewModal(item) {
    previewTitle.textContent = item.pageTitle || '媒体预览';
    previewModal.classList.remove('hidden');

    if (item.mediaType === 'audio') {
      previewVideo.classList.add('hidden');
      previewAudio.classList.remove('hidden');
      previewAudio.src = item.url;
      previewAudio.play().catch(() => {});
    } else {
      previewAudio.classList.add('hidden');
      previewVideo.classList.remove('hidden');

      if (item.mediaType === 'm3u8' && window.Hls && Hls.isSupported()) {
        if (activeHls) activeHls.destroy();
        activeHls = new Hls();
        activeHls.loadSource(item.url);
        activeHls.attachMedia(previewVideo);
        activeHls.on(Hls.Events.MANIFEST_PARSED, () => {
          previewVideo.play().catch(() => {});
        });
      } else {
        previewVideo.src = item.url;
        previewVideo.play().catch(() => {});
      }
    }
  }

  function closePreviewModal() {
    previewModal.classList.add('hidden');
    if (activeHls) {
      activeHls.destroy();
      activeHls = null;
    }
    previewVideo.pause();
    previewVideo.removeAttribute('src');
    previewVideo.load();
    previewAudio.pause();
    previewAudio.removeAttribute('src');
    previewAudio.load();
  }

  function getDomain(url) {
    try {
      return new URL(url).hostname;
    } catch (e) {
      return '未知站点';
    }
  }

  function formatSize(bytes) {
    if (!bytes || bytes <= 0) return '未知';
    const units = ['B', 'KB', 'MB', 'GB'];
    let idx = 0;
    while (bytes >= 1024 && idx < units.length - 1) {
      bytes /= 1024;
      idx++;
    }
    return `${bytes.toFixed(1)} ${units[idx]}`;
  }

  function escapeHtml(str) {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
})();

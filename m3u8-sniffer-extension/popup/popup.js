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
        <button class="btn-sm btn-secondary action-preview">预览</button>
        <button class="btn-sm btn-secondary action-copy">复制</button>
        <button class="btn-sm btn-danger action-del">删除</button>
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

    const pushBtn = card.querySelector('.action-push');
    pushBtn.addEventListener('click', async () => {
      pushBtn.textContent = '推送中...';
      pushBtn.disabled = true;

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
        baseUrl: item.baseUrl || ''
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

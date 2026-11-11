// popup.js - CatCatch Pro Modern Minimalist Controller
// 支持：仅抓取整个完整视频、页面消失自动刷新清除、本地活跃代理自动对齐、分片文件夹管理
(function () {
  'use strict';

  // 精确分片识别：m3u8/mpd 清单永远放行，避免误杀深层高画质地址
  const PLAYLIST_REGEX = /\.(m3u8|mpd)(\?|#|$)/i;
  const SEGMENT_REGEX = /\.(ts|m4s|m4v|mp2t|cmfv|cmfa|vtt|srt|ass|key)(\?|#|$)/i;
  function isFragmentUrl(url) {
    if (!url) return true;
    const clean = String(url).split('#')[0];
    if (PLAYLIST_REGEX.test(clean)) return false;
    if (SEGMENT_REGEX.test(clean)) return true;
    if (/(^|\/)(init\.mp4|init\.m4s)$/i.test(clean.split('?')[0])) return true;
    if (/(^|\/)(segment|chunk|frag|seg|part)[-_.]?\d+\.(ts|m4s|mp4|m4v)/i.test(clean)) return true;
    return false;
  }

  let currentCategory = 'all';
  let currentScope = 'current'; // 'current': 仅当前网页 | 'all': 全部仍打开网页
  let currentActiveTabId = -1;
  let liveTabIds = new Set();
  let searchKeyword = '';
  let mediaList = [];
  let selectedIds = new Set();
  let clientOnline = false;
  let clientPort = 18910;
  let activeHls = null;
  let detectedProxy = { mode: 'system', proxyUrl: '', label: '跟随系统代理' };
  let clientDetectedProxies = [];
  let clientEffectiveProxy = '';
  let clientTempDir = 'Temp_Segments';

  function toBase64(str) {
    if (!str) return '';
    try {
      return btoa(unescape(encodeURIComponent(str)));
    } catch (e) {
      return btoa(str);
    }
  }

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
  const fragmentsModal = document.getElementById('fragmentsModal');

  function applyI18nUI() {
    if (typeof ExtI18n === 'undefined') return;
    const t = ExtI18n.t;
    const el = (id) => document.getElementById(id);

    if (el('brandTitle')) el('brandTitle').textContent = t('brand_title');
    if (el('clientStatusText')) el('clientStatusText').textContent = clientOnline ? t('status_online') : t('status_offline');
    if (el('btnFragments')) el('btnFragments').title = t('tip_fragments');
    if (el('btnSettings')) el('btnSettings').title = t('tip_settings');
    if (el('btnClear')) el('btnClear').title = t('tip_clear');
    if (el('btnLang')) el('btnLang').title = t('tip_lang');

    if (el('scopeCurrentTab')) el('scopeCurrentTab').textContent = t('scope_current');
    if (el('scopeAllTabs')) el('scopeAllTabs').textContent = t('scope_all');

    const tabAll = document.querySelector('.tab-item[data-cat="all"]');
    if (tabAll && tabAll.childNodes[0]) tabAll.childNodes[0].textContent = t('tab_all') + ' ';
    const tabM3u8 = document.querySelector('.tab-item[data-cat="m3u8"]');
    if (tabM3u8 && tabM3u8.childNodes[0]) tabM3u8.childNodes[0].textContent = t('tab_stream') + ' ';
    const tabVideo = document.querySelector('.tab-item[data-cat="video"]');
    if (tabVideo && tabVideo.childNodes[0]) tabVideo.childNodes[0].textContent = t('tab_video') + ' ';
    const tabAudio = document.querySelector('.tab-item[data-cat="audio"]');
    if (tabAudio && tabAudio.childNodes[0]) tabAudio.childNodes[0].textContent = t('tab_audio') + ' ';
    const tabOther = document.querySelector('.tab-item[data-cat="other"]');
    if (tabOther && tabOther.childNodes[0]) tabOther.childNodes[0].textContent = t('tab_other') + ' ';

    const selAllLabel = document.querySelector('.search-bar label:nth-child(1)');
    if (selAllLabel && selAllLabel.childNodes.length > 1) {
      selAllLabel.childNodes[selAllLabel.childNodes.length - 1].textContent = ' ' + t('select_all');
    }
    const filterAdsLabel = document.querySelector('.search-bar label:nth-child(2)');
    if (filterAdsLabel && filterAdsLabel.childNodes.length > 1) {
      filterAdsLabel.title = t('filter_ads');
      filterAdsLabel.childNodes[filterAdsLabel.childNodes.length - 1].textContent = ' ' + t('filter_ads');
    }

    if (el('searchInput')) el('searchInput').placeholder = t('search_placeholder');
    if (el('btnBatchPush')) el('btnBatchPush').textContent = t('batch_push');
    if (el('btnBatchCopy')) el('btnBatchCopy').textContent = t('batch_copy');
    if (el('btnBatchCopyB64')) el('btnBatchCopyB64').textContent = t('batch_copy_b64');
    if (el('btnBatchDelete')) el('btnBatchDelete').textContent = t('batch_delete');

    const emptyTitle = document.querySelector('.empty-title');
    if (emptyTitle) emptyTitle.textContent = t('empty_title');
    const emptyDesc = document.querySelector('.empty-desc');
    if (emptyDesc) emptyDesc.textContent = t('empty_desc');

    if (el('previewTitle')) el('previewTitle').textContent = t('btn_preview');
    const fragTitle = document.querySelector('#fragmentsModal .modal-title');
    if (fragTitle) fragTitle.textContent = t('frag_title');
    if (el('btnCleanAllFrags')) el('btnCleanAllFrags').textContent = t('btn_clean_all');
    if (el('btnRefreshFrags')) el('btnRefreshFrags').textContent = t('btn_refresh');
    if (el('btnCloseFrags')) el('btnCloseFrags').textContent = t('btn_close');

    if (el('settingsTitle')) el('settingsTitle').textContent = t('settings_title');
    if (el('lblSettingLang')) el('lblSettingLang').textContent = t('setting_lang');
    if (el('lblSettingPort')) el('lblSettingPort').textContent = t('setting_port');
    if (el('lblSettingMinSize')) el('lblSettingMinSize').textContent = t('setting_min_size');
    if (el('lblSettingFilterFrags')) {
      const span = el('lblSettingFilterFrags').querySelector('span');
      if (span) span.innerHTML = `<strong>${t('setting_filter_frags')}</strong>`;
    }
    if (el('lblSettingAutoPurge')) {
      const span = el('lblSettingAutoPurge').querySelector('span');
      if (span) span.innerHTML = `<strong>${t('setting_auto_purge')}</strong>`;
    }
    if (el('lblSettingAutoPush')) {
      const span = el('lblSettingAutoPush').querySelector('span');
      if (span) span.textContent = t('setting_auto_push');
    }
    if (el('helpTitle')) el('helpTitle').textContent = t('setting_frag_manage');
    if (el('helpDesc')) el('helpDesc').innerHTML = t('setting_frag_desc');
    if (el('saveSettingsBtn')) el('saveSettingsBtn').textContent = t('btn_save_settings');
  }

  function initLanguageUI() {
    if (typeof ExtI18n === 'undefined') return;
    const langSelect = document.getElementById('settingLang');
    if (!langSelect) return;
    langSelect.innerHTML = '';
    const langs = ExtI18n.getSupportedLanguages();
    const cur = ExtI18n.getLang();
    for (const [code, name] of Object.entries(langs)) {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = name;
      if (code === cur) opt.selected = true;
      langSelect.appendChild(opt);
    }
    langSelect.onchange = (e) => {
      ExtI18n.setLang(e.target.value);
      applyI18nUI();
      renderList();
      syncLanguageToClient(e.target.value);
    };

    const btnLang = document.getElementById('btnLang');
    if (btnLang) {
      btnLang.onclick = () => {
        const langCodes = Object.keys(langs);
        const idx = langCodes.indexOf(ExtI18n.getLang());
        const nextLang = langCodes[(idx + 1) % langCodes.length];
        ExtI18n.setLang(nextLang);
        langSelect.value = nextLang;
        applyI18nUI();
        renderList();
        syncLanguageToClient(nextLang);
      };
    }
  }

  function syncLanguageToClient(langCode) {
    fetch(`http://127.0.0.1:${clientPort}/api/language`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: langCode })
    }).catch(() => {});
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (typeof ExtI18n !== 'undefined') {
      await ExtI18n.initLang();
      initLanguageUI();
      applyI18nUI();
    }
    await initTabTracking();

    if (currentActiveTabId >= 0) {
      chrome.action.setBadgeText({ tabId: currentActiveTabId, text: '' });
    }
    chrome.action.setBadgeText({ text: '' });

    bindEvents();
    bindTabLifecycleListeners();

    try {
      chrome.runtime.sendMessage({ action: 'DETECT_BROWSER_PROXY' }, (res) => {
        if (res) {
          detectedProxy = res;
          updateProxyTips();
        }
      });
    } catch (e) {}

    await loadSettings();
    await checkClientStatus();

    try {
      chrome.runtime.sendMessage({ action: 'PURGE_CLOSED_TABS' }, () => {
        loadAndRenderMedia();
      });
    } catch (e) {
      loadAndRenderMedia();
    }

    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === 'local' && changes.mediaList) {
        mediaList = (changes.mediaList.newValue || []).filter((it) => !isFragmentUrl(it.url));
        renderList();
        updateCategoryCounts();
      }
    });
  });

  async function initTabTracking() {
    return new Promise((resolve) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs[0]) {
          currentActiveTabId = tabs[0].id;
        }
        chrome.tabs.query({}, (allTabs) => {
          liveTabIds = new Set((allTabs || []).map((t) => t.id));
          resolve();
        });
      });
    });
  }

  function bindTabLifecycleListeners() {
    chrome.tabs.onActivated.addListener(async (activeInfo) => {
      currentActiveTabId = activeInfo.tabId;
      await refreshLiveTabs();
      if (currentScope === 'current') {
        renderList();
        updateCategoryCounts();
      }
    });

    chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
      if (changeInfo.status === 'loading') {
        await refreshLiveTabs();
        loadAndRenderMedia();
      }
    });

    chrome.tabs.onRemoved.addListener(async (tabId) => {
      liveTabIds.delete(tabId);
      loadAndRenderMedia();
    });
  }

  async function refreshLiveTabs() {
    return new Promise((resolve) => {
      chrome.tabs.query({}, (tabs) => {
        liveTabIds = new Set((tabs || []).map((t) => t.id));
        resolve();
      });
    });
  }

  function bindEvents() {
    const t = typeof ExtI18n !== 'undefined' ? ExtI18n.t : (k => k);

    document.querySelectorAll('.category-tabs .tab-item').forEach((tab) => {
      tab.addEventListener('click', (e) => {
        document.querySelectorAll('.category-tabs .tab-item').forEach((el) => el.classList.remove('active'));
        e.currentTarget.classList.add('active');
        currentCategory = e.currentTarget.getAttribute('data-cat');
        renderList();
      });
    });

    const btnScopeCurrent = document.getElementById('scopeCurrentTab');
    const btnScopeAll = document.getElementById('scopeAllTabs');

    btnScopeCurrent.addEventListener('click', () => {
      currentScope = 'current';
      btnScopeCurrent.classList.add('active');
      btnScopeAll.classList.remove('active');
      renderList();
      updateCategoryCounts();
    });

    btnScopeAll.addEventListener('click', () => {
      currentScope = 'all';
      btnScopeAll.classList.add('active');
      btnScopeCurrent.classList.remove('active');
      renderList();
      updateCategoryCounts();
    });

    searchInput.addEventListener('input', (e) => {
      searchKeyword = e.target.value.trim().toLowerCase();
      renderList();
    });

    selectAllCheckbox.addEventListener('change', (e) => {
      const checked = e.target.checked;
      const filtered = getFilteredMedia();
      if (checked) {
        filtered.forEach((it) => selectedIds.add(it.id));
      } else {
        selectedIds.clear();
      }
      renderList();
      updateBatchBar();
    });

    document.getElementById('filterAdsCheckbox').addEventListener('change', () => {
      renderList();
      updateCategoryCounts();
    });

    document.getElementById('btnClear').addEventListener('click', async () => {
      mediaList = [];
      selectedIds.clear();
      await chrome.storage.local.set({ mediaList: [] });
      chrome.action.setBadgeText({ text: '' });
      renderList();
      updateCategoryCounts();
      updateBatchBar();
    });

    document.getElementById('btnFragments').addEventListener('click', () => {
      openFragmentsModal();
    });
    document.getElementById('closeFragsBtn').addEventListener('click', () => {
      fragmentsModal.classList.add('hidden');
    });
    document.getElementById('btnCloseFrags').addEventListener('click', () => {
      fragmentsModal.classList.add('hidden');
    });
    document.getElementById('btnRefreshFrags').addEventListener('click', () => {
      loadFragmentsStatus();
    });
    document.getElementById('btnCleanAllFrags').addEventListener('click', () => {
      cleanAllFragments();
    });

    document.getElementById('btnBatchPush').addEventListener('click', async () => {
      const selectedItems = mediaList.filter((it) => selectedIds.has(it.id));
      if (!selectedItems.length) return;

      const btn = document.getElementById('btnBatchPush');
      btn.textContent = t('cap_pushing', '推送中...');
      btn.disabled = true;

      const tasks = selectedItems.map((it) => {
        const ref = it.referer || it.pageUrl || '';
        let orig = '';
        if (ref) {
          try { orig = new URL(ref).origin; } catch (e) {}
        }
        return {
          url: it.url,
          title: it.pageTitle || 'video',
          saveName: it.pageTitle || 'video',
          mediaType: it.mediaType,
          resolution: it.resolution || '',
          duration: it.duration || 0,
          referer: ref,
          pageUrl: it.pageUrl || ref,
          headers: {
            Referer: ref,
            Origin: orig,
            'User-Agent': it.userAgent || '',
            Cookie: it.cookie || ''
          },
          baseUrl: it.baseUrl || ''
        };
      });

      tasks.forEach((task) => {
        Object.keys(task.headers || {}).forEach((k) => {
          if (!task.headers[k]) delete task.headers[k];
        });
      });

      let pushed = false;
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 2500);
        const resp = await fetch(`http://127.0.0.1:${clientPort}/api/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tasks),
          signal: controller.signal
        });
        clearTimeout(timer);
        if (resp && resp.ok) {
          pushed = true;
          btn.textContent = `已推送 ${tasks.length} 项`;
          setTimeout(() => {
            btn.textContent = t('batch_push', '批量推送到客户端');
            btn.disabled = false;
          }, 2000);
          return;
        }
      } catch (err) {}

      if (!pushed) {
        chrome.runtime.sendMessage({ action: 'PUSH_TO_CLIENT', data: tasks }, (res) => {
          const ok = !!(res && res.success);
          btn.textContent = ok ? `已推送 ${tasks.length} 项` : t('status_offline', '客户端离线');
          setTimeout(() => {
            btn.textContent = t('batch_push', '批量推送到客户端');
            btn.disabled = false;
          }, 2000);
        });
      }
    });

    document.getElementById('btnBatchCopy').addEventListener('click', () => {
      const selectedItems = mediaList.filter((it) => selectedIds.has(it.id));
      const urls = selectedItems.map((it) => it.url).join('\n');
      navigator.clipboard.writeText(urls).then(() => {
        const btn = document.getElementById('btnBatchCopy');
        btn.textContent = t('cap_copied_link', '已复制原链');
        setTimeout(() => (btn.textContent = t('batch_copy', '复制原链')), 1500);
      });
    });

    const batchCopyB64Btn = document.getElementById('btnBatchCopyB64');
    if (batchCopyB64Btn) {
      batchCopyB64Btn.addEventListener('click', () => {
        const selectedItems = mediaList.filter((it) => selectedIds.has(it.id));
        const urls = selectedItems.map((it) => toBase64(it.url)).join('\n');
        navigator.clipboard.writeText(urls).then(() => {
          batchCopyB64Btn.textContent = t('cap_copied_b64', '已复制Base64');
          setTimeout(() => (batchCopyB64Btn.textContent = t('batch_copy_b64', '复制Base64')), 1500);
        });
      });
    }

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
    settingsPanel.addEventListener('click', (e) => {
      if (e.target === settingsPanel) settingsPanel.classList.add('hidden');
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !settingsPanel.classList.contains('hidden')) {
        settingsPanel.classList.add('hidden');
      }
    });
    document.getElementById('closeSettingsBtn').addEventListener('click', () => {
      settingsPanel.classList.add('hidden');
    });
    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);
  }

  async function checkClientStatus() {
    for (const host of ['127.0.0.1', 'localhost']) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 2000);
        const resp = await fetch(`http://${host}:${clientPort}/api/status`, {
          method: 'GET',
          cache: 'no-store',
          signal: controller.signal
        });
        clearTimeout(timer);
        if (resp && resp.ok) {
          const data = await resp.json();
          clientOnline = true;
          clientStatusBadge.className = 'status-pill online';
          clientStatusText.textContent = typeof ExtI18n !== 'undefined' ? ExtI18n.t('status_online') : '客户端已连接';
          if (data.detected_proxies) clientDetectedProxies = data.detected_proxies;
          if (data.effective_proxy) clientEffectiveProxy = data.effective_proxy;
          if (data.temp_segments_dir) clientTempDir = data.temp_segments_dir;
          if (data.language && typeof ExtI18n !== 'undefined') {
            if (data.language !== ExtI18n.getLang()) {
              ExtI18n.setLang(data.language);
              initLanguageUI();
              applyI18nUI();
              renderList();
            }
          }
          updateProxyTips();
          return;
        }
      } catch (e) {}
    }

    clientOnline = false;
    clientStatusBadge.className = 'status-pill offline';
    clientStatusText.textContent = typeof ExtI18n !== 'undefined' ? ExtI18n.t('status_offline') : '客户端离线';
    clientStatusBadge.onclick = () => {
      settingsPanel.classList.remove('hidden');
    };
  }

  async function openFragmentsModal() {
    fragmentsModal.classList.remove('hidden');
    document.getElementById('fragDirPath').textContent = clientTempDir || 'Temp_Segments';
    loadFragmentsStatus();
  }

  async function loadFragmentsStatus() {
    const statsEl = document.getElementById('fragStats');
    const container = document.getElementById('fragListContainer');
    const t = typeof ExtI18n !== 'undefined' ? ExtI18n.t : (k => k);
    statsEl.textContent = t('frag_loading');
    container.innerHTML = '<div style="color:#71717a; text-align:center; padding:10px;">...</div>';

    try {
      const res = await fetch(`http://127.0.0.1:${clientPort}/api/fragments`, { method: 'GET' });
      if (!res.ok) throw new Error();
      const data = await res.json();
      statsEl.textContent = `${t('frag_count')} ${data.folder_count} | ${t('frag_size')} ${data.total_size_formatted}`;

      if (data.folders.length === 0) {
        container.innerHTML = `<div style="color:#10b981; text-align:center; padding:20px 10px;">${t('frag_empty')}</div>`;
        return;
      }

      container.innerHTML = '';
      data.folders.forEach((f) => {
        const item = document.createElement('div');
        item.className = 'frag-item';
        item.innerHTML = `
          <div class="frag-item-info">
            <span class="frag-item-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
            <span class="frag-item-meta">${f.size_formatted} · ${f.file_count} files</span>
          </div>
          <button class="frag-del-btn" title="${t('frag_del_tip')}">${t('btn_delete')}</button>
        `;
        item.querySelector('.frag-del-btn').addEventListener('click', async () => {
          try {
            await fetch(`http://127.0.0.1:${clientPort}/api/fragments/${encodeURIComponent(f.name)}`, { method: 'DELETE' });
            loadFragmentsStatus();
          } catch (e) {}
        });
        container.appendChild(item);
      });
    } catch (e) {
      statsEl.textContent = t('frag_offline');
      container.innerHTML = `<div style="color:#ef4444; text-align:center; padding:20px 10px;">${t('frag_conn_err')}</div>`;
    }
  }

  async function cleanAllFragments() {
    const t = typeof ExtI18n !== 'undefined' ? ExtI18n.t : (k => k);
    if (!confirm(t('frag_confirm_clean'))) return;
    try {
      const res = await fetch(`http://127.0.0.1:${clientPort}/api/fragments`, { method: 'DELETE' });
      if (res.ok) {
        const d = await res.json();
        alert(t('frag_cleaned_prefix') + (d.deleted_count || 0) + t('frag_cleaned_suffix'));
        loadFragmentsStatus();
      }
    } catch (e) {
      alert(t('frag_clean_fail'));
    }
  }

  async function loadSettings() {
    const res = await chrome.storage.local.get('settings');
    const settings = res.settings || {};
    clientPort = settings.serverPort || 18910;
    document.getElementById('settingPort').value = clientPort;
    document.getElementById('settingFilterFragments').checked = settings.filterFragments !== false;
    document.getElementById('settingAutoPurge').checked = settings.onlyLiveTabs !== false;
    document.getElementById('settingAutoPush').checked = !!settings.autoPush;
    document.getElementById('settingMinSize').value = settings.minSizeKB || 0;
  }

  async function saveSettings() {
    const port = parseInt(document.getElementById('settingPort').value, 10) || 18910;
    const filterFragments = document.getElementById('settingFilterFragments').checked;
    const onlyLiveTabs = document.getElementById('settingAutoPurge').checked;
    const autoPush = document.getElementById('settingAutoPush').checked;
    const minSizeKB = parseInt(document.getElementById('settingMinSize').value, 10) || 0;

    clientPort = port;
    const settings = {
      serverPort: port,
      filterFragments,
      onlyLiveTabs,
      autoPush,
      minSizeKB
    };

    await chrome.storage.local.set({ settings });
    settingsPanel.classList.add('hidden');
    await checkClientStatus();
    loadAndRenderMedia();
  }

  async function loadAndRenderMedia() {
    const res = await chrome.storage.local.get('mediaList');
    mediaList = (res.mediaList || []).filter((it) => !isFragmentUrl(it.url));
    renderList();
    updateCategoryCounts();
    updateBatchBar();
  }

  function getFilteredMedia() {
    const isFilterAds = document.getElementById('filterAdsCheckbox').checked;
    return mediaList.filter((item) => {
      if (isFilterAds && item.isAd && !item.isMaster) {
        return false;
      }
      if (currentScope === 'current') {
        if (currentActiveTabId >= 0 && item.tabId !== currentActiveTabId) {
          return false;
        }
      } else {
        if (item.tabId && !liveTabIds.has(item.tabId)) {
          return false;
        }
      }
      if (currentCategory !== 'all') {
        if (currentCategory === 'm3u8' && item.mediaType !== 'm3u8' && item.mediaType !== 'mpd') return false;
        if (currentCategory === 'video' && item.mediaType !== 'video') return false;
        if (currentCategory === 'audio' && item.mediaType !== 'audio') return false;
        if (currentCategory === 'other' && (item.mediaType === 'm3u8' || item.mediaType === 'mpd' || item.mediaType === 'video' || item.mediaType === 'audio')) return false;
      }
      if (searchKeyword) {
        const titleMatch = (item.pageTitle || '').toLowerCase().includes(searchKeyword);
        const urlMatch = (item.url || '').toLowerCase().includes(searchKeyword);
        const resMatch = (item.resolution || '').toLowerCase().includes(searchKeyword);
        if (!titleMatch && !urlMatch && !resMatch) return false;
      }
      return true;
    });
  }

  function updateCategoryCounts() {
    const isFilterAds = document.getElementById('filterAdsCheckbox').checked;
    const scopedList = mediaList.filter((item) => {
      if (isFilterAds && item.isAd && !item.isMaster) return false;
      if (currentScope === 'current') {
        return currentActiveTabId >= 0 ? item.tabId === currentActiveTabId : true;
      } else {
        return item.tabId ? liveTabIds.has(item.tabId) : true;
      }
    });

    const counts = { all: 0, m3u8: 0, video: 0, audio: 0, other: 0 };
    scopedList.forEach((it) => {
      counts.all++;
      if (it.mediaType === 'm3u8' || it.mediaType === 'mpd') counts.m3u8++;
      else if (it.mediaType === 'video') counts.video++;
      else if (it.mediaType === 'audio') counts.audio++;
      else counts.other++;
    });

    document.getElementById('countAll').textContent = counts.all;
    document.getElementById('countM3u8').textContent = counts.m3u8;
    document.getElementById('countVideo').textContent = counts.video;
    document.getElementById('countAudio').textContent = counts.audio;
    document.getElementById('countOther').textContent = counts.other;
  }

  function renderList() {
    mediaListContainer.innerHTML = '';
    const filtered = getFilteredMedia();

    if (filtered.length === 0) {
      emptyPlaceholder.classList.remove('hidden');
      return;
    }
    emptyPlaceholder.classList.add('hidden');

    filtered.forEach((item) => {
      const card = createMediaCard(item);
      mediaListContainer.appendChild(card);
    });
  }

  function createMediaCard(item) {
    const t = typeof ExtI18n !== 'undefined' ? ExtI18n.t : (k => k);
    const card = document.createElement('div');
    card.className = `media-card ${item.isMaster ? 'master-card' : ''}`;
    card.dataset.id = item.id;

    const isChecked = selectedIds.has(item.id);
    const domain = getDomain(item.url);
    const title = item.pageTitle || '视频流';

    let tagsHtml = `<span class="tag-badge tag-type">${(item.mediaType || 'media').toUpperCase()}</span>`;
    if (item.isMaster) {
      tagsHtml += `<span class="tag-badge" style="background:#2563eb;color:#fff;font-weight:600;" title="主清单 (Master Playlist)，N_m3u8DL-RE 将自动选择最高画质 1080P">最高画质 1080P</span>`;
    }
    if (item.isAd && !item.isMaster) {
      tagsHtml += `<span class="tag-badge" style="background:#ef4444;color:#fff;" title="${item.adReason || t('tag_ad', '疑似切片')}">${t('tag_ad')}${item.duration ? ' (' + item.duration + 's)' : ''}</span>`;
    } else if (item.isFeature || item.isMaster) {
      tagsHtml += `<span class="tag-badge" style="background:#10b981;color:#fff;" title="${t('tip_feature_video', '当前页面正片视频')}">${t('tag_feature')}</span>`;
    }
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
      tagsHtml += `<span class="tag-badge tag-key">${t('tag_encrypted', '加密 (AES-128)')}</span>`;
    }
    tagsHtml += `<span class="tag-badge tag-domain">${domain}</span>`;

    const proxyTipText = detectedProxy.proxyUrl
      ? `浏览器代理: ${detectedProxy.proxyUrl}`
      : (clientEffectiveProxy ? `本地代理: ${clientEffectiveProxy}` : '代理: 直连/跟随系统');

    let proxyOptionsHtml = `
      <option value="auto" selected>${t('cfg_proxy_auto')} (推荐${clientEffectiveProxy ? ': ' + clientEffectiveProxy : ''})</option>
      <option value="direct">${t('cfg_proxy_direct')}</option>
      <option value="default">${t('cfg_proxy_default')}</option>
    `;
    if (clientDetectedProxies && clientDetectedProxies.length > 0) {
      clientDetectedProxies.forEach((p) => {
        proxyOptionsHtml += `<option value="${p.url}">${p.name}</option>`;
      });
    } else {
      proxyOptionsHtml += `
        <option value="http://127.0.0.1:1080">sing-box / SOCKS5 (1080)</option>
        <option value="http://127.0.0.1:7890">Clash / Verge (7890)</option>
        <option value="socks5://127.0.0.1:10808">v2rayN SOCKS5 (10808)</option>
        <option value="http://127.0.0.1:10809">v2rayN HTTP (10809)</option>
      `;
    }
    proxyOptionsHtml += `<option value="custom">${t('cfg_proxy_custom')}</option>`;

    card.innerHTML = `
      <div class="card-top">
        <input type="checkbox" class="card-checkbox" ${isChecked ? 'checked' : ''}>
        <div class="card-title-wrap">
          <input type="text" class="card-title-input" value="${escapeHtml(title)}" title="${t('tip_edit_title', '点击修改保存名称')}">
        </div>
      </div>
      <div class="card-tags">${tagsHtml}</div>
      <div class="card-url-box" title="${t('tip_copy_url', '点击复制完整直链')}">${escapeHtml(item.url)}</div>
      <div class="card-actions">
        <button class="btn-sm btn-primary action-push">${t('btn_push')}</button>
        <button class="btn-sm btn-secondary action-config" title="${t('btn_config')}">${t('btn_config')}</button>
        <button class="btn-sm btn-secondary action-copy-cmd" title="${t('btn_copy_cmd')}">${t('btn_copy_cmd')}</button>
        <button class="btn-sm btn-secondary action-preview">${t('btn_preview')}</button>
        <button class="btn-sm btn-secondary action-copy" title="${t('tip_copy_url', '点击复制完整直链')}">${t('btn_copy')}</button>
        <button class="btn-sm btn-secondary action-copy-b64" title="${t('tip_copy_b64', '点击复制Base64编码链接')}">${t('btn_copy_b64')}</button>
        <button class="btn-sm btn-danger action-del">${t('btn_delete')}</button>
      </div>
      <div class="card-config-panel hidden">
        <div class="config-row">
          <span class="config-label">${t('cfg_savedir')}</span>
          <input type="text" class="config-input cfg-savedir" placeholder="${t('cfg_savedir_placeholder')}">
        </div>
        <div class="config-row">
          <span class="config-label">${t('cfg_threads')}</span>
          <select class="config-select cfg-threads">
            <option value="">${t('cfg_threads_follow')}</option>
            <option value="4">${t('cfg_threads_4')}</option>
            <option value="8">${t('cfg_threads_8')}</option>
            <option value="16">${t('cfg_threads_16')}</option>
            <option value="32">${t('cfg_threads_32')}</option>
          </select>
        </div>
        <div class="config-row">
          <span class="config-label">${t('cfg_proxy')}</span>
          <select class="config-select cfg-proxy">
            ${proxyOptionsHtml}
          </select>
        </div>
        <div class="config-row cfg-custom-proxy-row hidden">
          <span class="config-label">${t('cfg_proxy_addr', '代理地址:')}</span>
          <input type="text" class="config-input cfg-custom-proxy" placeholder="${t('cfg_custom_proxy_placeholder')}">
        </div>
        <div class="config-tip cfg-proxy-tip">${proxyTipText}</div>
        <button class="btn-copy-cli-inside">${t('btn_copy_cli')}</button>
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
        urlBox.textContent = t('cap_copied_link', '已复制直链到剪贴板');
        setTimeout(() => (urlBox.textContent = oldText), 1500);
      });
    });

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
        finalProxy = detectedProxy.proxyUrl || clientEffectiveProxy || (detectedProxy.mode === 'direct' ? 'direct' : 'default');
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
      } else if (cfg.proxy === 'auto' && (detectedProxy.proxyUrl || clientEffectiveProxy)) {
        proxyForCmd = detectedProxy.proxyUrl || clientEffectiveProxy;
      }

      let cmd = `N_m3u8DL-RE "${item.url}"`;
      if (cfg.saveDir) {
        cmd += ` --save-dir "${cfg.saveDir}"`;
      }
      const safeTitle = (titleInput.value.trim() || item.pageTitle || 'video').replace(/[\\/*?:"<>|]/g, '_');
      cmd += ` --save-name "${safeTitle}"`;
      cmd += ` --tmp-dir "${clientTempDir || 'Temp_Segments'}"`;
      if (cfg.threadCount) {
        cmd += ` --thread-count ${cfg.threadCount}`;
      }
      cmd += ` --auto-select --live-perform-as-vod -M format=mp4`;
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
        btnSource.textContent = t('cap_copied_cmd', '已复制 N_m3u8DL 命令！');
        setTimeout(() => (btnSource.textContent = originalText), 1800);
      });
    }

    const copyCmdBtn = card.querySelector('.action-copy-cmd');
    copyCmdBtn.addEventListener('click', () => copyCliCommand(copyCmdBtn));

    const copyInsideBtn = configPanel.querySelector('.btn-copy-cli-inside');
    copyInsideBtn.addEventListener('click', () => copyCliCommand(copyInsideBtn));

    const pushBtn = card.querySelector('.action-push');
    pushBtn.addEventListener('click', async () => {
      pushBtn.textContent = t('cap_pushing', '推送中...');
      pushBtn.disabled = true;

      const cfg = getTaskConfigOptions();
      const ref = item.referer || item.pageUrl || '';
      let orig = '';
      if (ref) {
        try { orig = new URL(ref).origin; } catch (e) {}
      }
      const taskData = {
        url: item.url,
        title: titleInput.value.trim() || item.pageTitle || 'video',
        saveName: titleInput.value.trim() || item.pageTitle || 'video',
        mediaType: item.mediaType,
        resolution: item.resolution || '',
        duration: item.duration || 0,
        referer: ref,
        pageUrl: item.pageUrl || ref,
        headers: {
          Referer: ref,
          Origin: orig,
          'User-Agent': item.userAgent || '',
          Cookie: item.cookie || ''
        },
        baseUrl: item.baseUrl || '',
        saveDir: cfg.saveDir,
        threadCount: cfg.threadCount,
        proxy: cfg.proxy
      };
      Object.keys(taskData.headers).forEach((k) => {
        if (!taskData.headers[k]) delete taskData.headers[k];
      });

      let pushed = false;
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 2500);
        const resp = await fetch(`http://127.0.0.1:${clientPort}/api/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData),
          signal: controller.signal
        });
        clearTimeout(timer);
        if (resp && resp.ok) {
          pushed = true;
          pushBtn.textContent = t('cap_pushed', '已加入队列');
          pushBtn.style.backgroundColor = '#166534';
          pushBtn.style.color = '#ffffff';
          pushBtn.disabled = false;
          return;
        }
      } catch (err) {}

      if (!pushed) {
        chrome.runtime.sendMessage({ action: 'PUSH_TO_CLIENT', data: taskData }, (res) => {
          if (res && res.success) {
            pushBtn.textContent = t('cap_pushed', '已加入队列');
            pushBtn.style.backgroundColor = '#166534';
            pushBtn.style.color = '#ffffff';
          } else {
            pushBtn.textContent = t('status_offline', '客户端离线');
          }
          pushBtn.disabled = false;
        });
      }
    });

    const previewBtn = card.querySelector('.action-preview');
    previewBtn.addEventListener('click', () => {
      openPreviewModal(item);
    });

    const copyBtn = card.querySelector('.action-copy');
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(item.url).then(() => {
        copyBtn.textContent = t('cap_copied_link', '已复制原链');
        setTimeout(() => (copyBtn.textContent = t('btn_copy', '复制原链')), 1500);
      });
    });

    const copyB64Btn = card.querySelector('.action-copy-b64');
    if (copyB64Btn) {
      copyB64Btn.addEventListener('click', () => {
        const b64 = toBase64(item.url);
        navigator.clipboard.writeText(b64).then(() => {
          copyB64Btn.textContent = t('cap_copied_b64', '已复制Base64');
          setTimeout(() => (copyB64Btn.textContent = t('btn_copy_b64', '复制Base64')), 1500);
        });
      });
    }

    const delBtn = card.querySelector('.action-del');
    delBtn.addEventListener('click', async () => {
      mediaList = mediaList.filter((it) => it.id !== item.id);
      selectedIds.delete(item.id);
      await chrome.storage.local.set({ mediaList });
      renderList();
      updateCategoryCounts();
      updateBatchBar();
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
        activeHls = new Hls({ enableWorker: true, lowLatencyMode: false });
        activeHls.loadSource(item.url);
        activeHls.attachMedia(previewVideo);
        activeHls.on(Hls.Events.MANIFEST_PARSED, () => {
          previewVideo.play().catch(() => {});
        });
        activeHls.on(Hls.Events.ERROR, () => {
          // 若跨域或防盗链阻断，调用页面内注入播放兜底
          chrome.runtime.sendMessage({ action: 'INJECT_HLS_PLAYER', data: item });
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

  function updateBatchBar() {
    const t = typeof ExtI18n !== 'undefined' ? ExtI18n.t : (k => k);
    if (selectedIds.size > 0) {
      batchBar.classList.remove('hidden');
      batchCountText.textContent = `${t('batch_selected_prefix')} ${selectedIds.size} ${t('batch_selected_suffix')}`;
    } else {
      batchBar.classList.add('hidden');
    }
  }

  function updateProxyTips() {
    const tipText = detectedProxy.proxyUrl
      ? `浏览器代理: ${detectedProxy.proxyUrl}`
      : (clientEffectiveProxy ? `本地代理: ${clientEffectiveProxy}` : '代理: 直连/跟随系统');
    document.querySelectorAll('.cfg-proxy-tip').forEach((el) => {
      el.textContent = tipText;
    });
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

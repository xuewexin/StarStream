// popup.js - CatCatch Pro Modern Minimalist Controller
// 支持：仅抓取整个完整视频、页面消失自动刷新清除、本地活跃代理自动对齐、分片文件夹管理
(function () {
  'use strict';

  // 精确分片识别：m3u8/mpd 清单永远放行，避免误杀深层高画质地址
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
    if (isBiliDashUrl(clean)) return false; // B站音视频完整轨放行！
    if (SEGMENT_REGEX.test(clean)) return true;
    if (/(^|\/)(init\.mp4|init\.m4s)$/i.test(clean.split('?')[0])) return true;
    if (/(^|\/)(segment|chunk|frag|seg|part)[-_.]?\d+\.(ts|m4s|mp4|m4v)/i.test(clean)) return true;
    return false;
  }

  let currentCategory = 'all';
  let currentScope = 'current'; // 'current': 仅当前网页 | 'all': 全部仍打开网页
  let currentActiveTabId = -1;
  let currentActiveTabUrl = '';
  let liveTabIds = new Set();
  let searchKeyword = '';
  let mediaList = [];
  let selectedIds = new Set();
  let clientOnline = false;
  let clientPort = 18910;
  let activeHls = null;
  let currentPreviewItem = null;
  const PREVIEW_RULE_ID = 20001;
  const expandedConfigState = new Map();
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
    if (el('btnResniff')) el('btnResniff').title = typeof ExtI18n !== 'undefined' ? (ExtI18n.t('tip_resniff') || '重新嗅探 / 深度扫描当前网页视频') : '重新嗅探 / 深度扫描当前网页视频';
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

  async function initPopup() {
    if (typeof ExtI18n !== 'undefined') {
      try {
        await ExtI18n.initLang();
        initLanguageUI();
        applyI18nUI();
      } catch (e) {}
    }
    try {
      await initTabTracking();
    } catch (e) {}

    if (currentActiveTabId >= 0) {
      chrome.action.setBadgeText({ tabId: currentActiveTabId, text: '' });
    }
    chrome.action.setBadgeText({ text: '' });

    try {
      bindEvents();
    } catch (e) {
      console.error('bindEvents error:', e);
    }
    try {
      bindTabLifecycleListeners();
    } catch (e) {}

    try {
      chrome.runtime.sendMessage({ action: 'DETECT_BROWSER_PROXY' }, (res) => {
        if (res) {
          detectedProxy = res;
          updateProxyTips();
        }
      });
    } catch (e) {}

    // 立即渲染已捕获的媒体记录，不阻塞等待网络响应
    try {
      loadAndRenderMedia();
    } catch (e) {}

    try {
      chrome.runtime.sendMessage({ action: 'PURGE_CLOSED_TABS' }, () => {
        loadAndRenderMedia();
      });
    } catch (e) {}

    try {
      await loadSettings();
    } catch (e) {}

    try {
      checkClientStatus(); // 异步探测客户端，更新在线状态标记
    } catch (e) {}

    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === 'local' && changes.mediaList) {
        mediaList = (changes.mediaList.newValue || []).filter((it) => !isFragmentUrl(it.url));
        renderList();
        updateCategoryCounts();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPopup);
  } else {
    initPopup();
  }

  async function initTabTracking() {
    return new Promise((resolve) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs[0]) {
          currentActiveTabId = tabs[0].id;
          currentActiveTabUrl = tabs[0].url || '';
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
      try {
        const tab = await chrome.tabs.get(activeInfo.tabId);
        if (tab) currentActiveTabUrl = tab.url || '';
      } catch (e) {}
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
    const closeFragsBtn = document.getElementById('closeFragmentsBtn') || document.getElementById('closeFragsBtn');
    if (closeFragsBtn) {
      closeFragsBtn.addEventListener('click', () => {
        fragmentsModal.classList.add('hidden');
      });
    }
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

      if (chrome.cookies) {
        for (const it of selectedItems) {
          if (!it.cookie) {
            try {
              const u = it.pageUrl || it.referer || it.url;
              const dom = new URL(u).hostname;
              const cks = await chrome.cookies.getAll({ domain: dom });
              if (cks && cks.length > 0) {
                it.cookie = cks.map(c => `${c.name}=${c.value}`).join('; ');
              }
            } catch (e) {}
          }
        }
      }

      const tasks = selectedItems.map((it) => {
        const ref = it.referer || it.pageUrl || '';
        let orig = '';
        if (ref) {
          try { orig = new URL(ref).origin; } catch (e) {}
        }
        return {
          url: it.url,
          audioUrl: it.audioUrl || '',
          title: it.pageTitle || 'video',
          saveName: it.pageTitle || 'video',
          mediaType: it.mediaType,
          resolution: getItemResolution(it),
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

    const previewInlineBtn = document.getElementById('previewInlineBtn');
    if (previewInlineBtn) {
      previewInlineBtn.addEventListener('click', () => {
        if (currentPreviewItem) {
          chrome.runtime.sendMessage({ action: 'INJECT_HLS_PLAYER', data: currentPreviewItem }, (res) => {
            const statusEl = document.getElementById('previewStatus');
            if (res && res.success) {
              if (statusEl) statusEl.innerHTML = '<span style="color:#22c55e;">已在目标网页内启动悬浮播放窗口！</span>';
            } else {
              if (statusEl) statusEl.innerHTML = `<span style="color:#ef4444;">网页内注入播放提示: ${res && res.error ? res.error : '页面未响应'}</span>`;
            }
          });
        }
      });
    }

    const previewRawBtn = document.getElementById('previewRawBtn');
    if (previewRawBtn) {
      previewRawBtn.addEventListener('click', () => {
        if (currentPreviewItem && currentPreviewItem.url) {
          window.open(currentPreviewItem.url, '_blank');
        }
      });
    }

    const btnResniff = document.getElementById('btnResniff');
    if (btnResniff) {
      btnResniff.addEventListener('click', () => {
        triggerResniff();
      });
    }

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

  async function triggerResniff() {
    const btn = document.getElementById('btnResniff');
    if (btn) btn.classList.add('spinning');
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs && tabs[0] && tabs[0].id) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'RESNIFF_ACTIVE_TAB' }, () => {
          if (chrome.runtime.lastError) {
            try {
              chrome.scripting.executeScript({
                target: { tabId: tabs[0].id },
                files: ['content_script.js']
              }).catch(() => {});
            } catch (e) {}
          }
        });
      }
    } catch (e) {}

    setTimeout(() => {
      loadAndRenderMedia();
    }, 350);

    setTimeout(() => {
      loadAndRenderMedia();
      if (btn) btn.classList.remove('spinning');
    }, 1200);
  }

  function handleClientStatusOnline(data) {
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
  }

  async function checkClientStatus() {
    // 1. 直连 fetch 探测
    for (const host of ['127.0.0.1', 'localhost']) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 3000);
        const resp = await fetch(`http://${host}:${clientPort}/api/status`, {
          method: 'GET',
          cache: 'no-store',
          signal: controller.signal
        });
        clearTimeout(timer);
        if (resp && resp.ok) {
          const data = await resp.json();
          handleClientStatusOnline(data);
          return;
        }
      } catch (e) {}
    }

    // 2. 兜底回退：通过后台 Service Worker 隧道查询
    try {
      const res = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ action: 'CHECK_CLIENT_STATUS' }, (resp) => {
          resolve(chrome.runtime.lastError ? null : resp);
        });
      });
      if (res && res.online && res.data) {
        handleClientStatusOnline(res.data);
        return;
      }
    } catch (e) {}

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

  /** 把 "1920x1080" / "1080P" / "4K" 等写法统一换成画面高度数值，解析不出来返回 0 */
  function parseResolutionHeight(value) {
    if (!value) return 0;
    const s = String(value).toUpperCase().trim();
    const dim = s.match(/(\d{3,4})\s*[X×*]\s*(\d{3,4})/);
    if (dim) {
      const h = Math.min(parseInt(dim[1], 10), parseInt(dim[2], 10));
      return Number.isFinite(h) ? h : 0;
    }
    if (s.includes('4K') || s.includes('2160')) return 2160;
    if (s.includes('2K') || s.includes('1440')) return 1440;
    const p = s.match(/(\d{3,4})\s*P(?![A-Z0-9])/);
    if (p) {
      const h = parseInt(p[1], 10);
      return h >= 144 && h <= 4320 ? h : 0;
    }
    return 0;
  }

  /** 卡片上展示的清晰度标签：1920x1080 → 1080P，已是 1080P 就原样 */
  function formatResolutionLabel(value) {
    const h = parseResolutionHeight(value);
    if (h) return `${h}P`;
    const s = String(value || '').trim();
    return s && s !== '最高画质' ? s : '';
  }

  /** 时长展示：小于 1 小时用 m:ss，超过 1 小时用 h:mm:ss，避免出现 117:22 这类怪值 */
  function formatDurationLabel(seconds) {
    const total = Math.round(Number(seconds) || 0);
    if (!Number.isFinite(total) || total <= 0) return '';
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const mm = h > 0 ? String(m).padStart(2, '0') : String(m);
    const ss = String(s).padStart(2, '0');
    return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
  }

  /** 从地址里提取真实画质（/720p/video.m3u8、xxx_1080p.mp4、4k） */
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

  /** 展示与排序统一取值：地址里的画质标签优先于可能被播放器尺寸污染的 resolution */
  function getItemResolution(item) {
    if (!item) return '';
    return extractQualityFromUrl(item.url) || item.resolution || item.variantLabel || '';
  }

  function getMediaQualityScore(item) {
    // 优先用地址里的真实画质，其次清单解析值，最后才用码率反推
    let score = parseResolutionHeight(extractQualityFromUrl(item.url));
    if (!score) score = parseResolutionHeight(item.resolution);
    if (!score) score = parseResolutionHeight(item.variantLabel);
    if (!score && item.url) {
      const m = String(item.url).match(/(\d{3,4})P(?![A-Z0-9])/i);
      if (m) {
        const h = parseInt(m[1], 10);
        if (h >= 144 && h <= 4320) score = h;
      }
    }
    // 实在没有分辨率时，用码率反推一个近似画质，仅用于排序
    if (!score && item.bandwidth > 0) {
      const kbps = item.bandwidth / 1000;
      if (kbps >= 8000) score = 2160;
      else if (kbps >= 3500) score = 1440;
      else if (kbps >= 1800) score = 1080;
      else if (kbps >= 900) score = 720;
      else if (kbps >= 450) score = 480;
      else score = 360;
    }
    return score;
  }

  function getMediaEffectiveSize(item) {
    if (item.contentLength && item.contentLength > 0) {
      return item.contentLength;
    }
    if (item.duration && item.duration > 0) {
      const q = getMediaQualityScore(item);
      let byteRate = 250 * 1024;
      if (q >= 2160) byteRate = 600 * 1024;
      else if (q >= 1080) byteRate = 320 * 1024;
      else if (q >= 720) byteRate = 180 * 1024;
      else if (q >= 480) byteRate = 100 * 1024;
      else if (q >= 240) byteRate = 45 * 1024;
      return item.duration * byteRate;
    }
    return 0;
  }

  function getFilteredMedia() {
    const isFilterAds = document.getElementById('filterAdsCheckbox').checked;
    const filtered = mediaList.filter((item) => {
      if (isFilterAds && item.isAd && !item.isMaster) {
        return false;
      }
      if (currentScope === 'current') {
        const matchTab = currentActiveTabId >= 0 && item.tabId === currentActiveTabId;
        const matchUrl = currentActiveTabUrl && item.pageUrl && item.pageUrl === currentActiveTabUrl;
        if (!matchTab && !matchUrl && currentActiveTabId >= 0) {
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

    // 排序规则（用户指定）：时长降序 → 画面分辨率降序 → 体积降序 → 最新嗅探时间
    filtered.sort((a, b) => {
      // 1. 时长降序（时长未知的排在已知时长之后）
      const aDur = Number(a.duration) || 0;
      const bDur = Number(b.duration) || 0;
      if (aDur !== bDur) return bDur - aDur;

      // 2. 画面分辨率降序 (2160P > 1440P > 1080P > 720P > 480P > 360P > 240P)
      const aQ = getMediaQualityScore(a);
      const bQ = getMediaQualityScore(b);
      if (aQ !== bQ) return bQ - aQ;

      // 3. 体积降序
      const aSize = getMediaEffectiveSize(a);
      const bSize = getMediaEffectiveSize(b);
      if (aSize !== bSize) return bSize - aSize;

      // 4. 最新嗅探时间
      return (b.timestamp || 0) - (a.timestamp || 0);
    });

    return filtered;
  }

  function updateCategoryCounts() {
    const isFilterAds = document.getElementById('filterAdsCheckbox').checked;
    const scopedList = mediaList.filter((item) => {
      if (isFilterAds && item.isAd && !item.isMaster) return false;
      if (currentScope === 'current') {
        const matchTab = currentActiveTabId >= 0 && item.tabId === currentActiveTabId;
        const matchUrl = currentActiveTabUrl && item.pageUrl && item.pageUrl === currentActiveTabUrl;
        return currentActiveTabId >= 0 ? (matchTab || matchUrl) : true;
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
    const filtered = getFilteredMedia();

    if (filtered.length === 0) {
      emptyPlaceholder.classList.remove('hidden');
      mediaListContainer.innerHTML = '';
      return;
    }
    emptyPlaceholder.classList.add('hidden');

    // 增量 DOM 对齐更新：保留已存在卡片的原生 DOM 状态，彻底杜绝折叠面板被刷新重置
    const existingCards = new Map();
    Array.from(mediaListContainer.children).forEach((el) => {
      if (el.dataset && el.dataset.id) {
        existingCards.set(el.dataset.id, el);
      }
    });

    const newIds = new Set(filtered.map((it) => it.id));

    // 移除已不在列表中的卡片
    existingCards.forEach((el, id) => {
      if (!newIds.has(id)) {
        el.remove();
      }
    });

    // 增量插入或按顺序排列卡片
    filtered.forEach((item, index) => {
      let card = existingCards.get(item.id);
      if (!card) {
        card = createMediaCard(item);
        const refNode = mediaListContainer.children[index] || null;
        mediaListContainer.insertBefore(card, refNode);
      } else {
        const curAtPos = mediaListContainer.children[index];
        if (curAtPos !== card) {
          mediaListContainer.insertBefore(card, curAtPos || null);
        }
      }
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

    let tagsHtml = `<span class="tag-badge tag-type" style="${item.mediaType === 'bili_dash' ? 'background: linear-gradient(135deg, #ec4899, #8b5cf6); color: #fff; font-weight: bold;' : ''}">${item.mediaType === 'bili_dash' ? '音画合一' : (item.mediaType || 'media').toUpperCase()}</span>`;
    if (item.mediaType === 'bili_dash') {
      if (item.audioUrl) {
        tagsHtml += `<span class="tag-badge" style="background:#10b981;color:#fff;" title="已成功抓取并配对高品质独立音频轨">已配对音频</span>`;
      } else {
        tagsHtml += `<span class="tag-badge" style="background:#f59e0b;color:#fff;" title="正在监听音频轨，若未加载可点击上方重新嗅探">等待音频</span>`;
      }
    }
    if (item.isMaster) {
      tagsHtml += `<span class="tag-badge" style="background:#2563eb;color:#fff;font-weight:600;" title="主清单 (Master Playlist)，N_m3u8DL-RE 将自动选择最高画质 1080P">最高画质 1080P</span>`;
    }
    if (item.isAd && !item.isMaster) {
      tagsHtml += `<span class="tag-badge" style="background:#ef4444;color:#fff;" title="${item.adReason || t('tag_ad', '疑似切片')}">${t('tag_ad')}${item.duration ? ' (' + item.duration + 's)' : ''}</span>`;
    } else if (item.isFeature || item.isMaster) {
      tagsHtml += `<span class="tag-badge" style="background:#10b981;color:#fff;" title="${t('tip_feature_video', '当前页面正片视频')}">${t('tag_feature')}</span>`;
    }
    const resLabel = formatResolutionLabel(getItemResolution(item));
    if (resLabel) {
      tagsHtml += `<span class="tag-badge tag-res">${escapeHtml(resLabel)}</span>`;
    }
    const durLabel = formatDurationLabel(item.duration);
    if (durLabel) {
      tagsHtml += `<span class="tag-badge tag-dur">${durLabel}</span>`;
    } else if (item.isLive) {
      tagsHtml += `<span class="tag-badge tag-dur" title="直播式 HLS，播放器未提供总时长">直播</span>`;
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

    const browserProxyLabel = detectedProxy.proxyUrl
      ? `${t('cfg_proxy_browser', '跟随浏览器代理')} (推荐: ${detectedProxy.proxyUrl})`
      : (detectedProxy.mode === 'direct' ? `${t('cfg_proxy_browser', '跟随浏览器代理')} (直连)` : `${t('cfg_proxy_browser', '跟随浏览器代理')} (推荐)`);

    const savedCfg = expandedConfigState.get(item.id) || {};
    const isExpanded = !!savedCfg.expanded;
    const curP = savedCfg.proxy || 'auto';

    let proxyOptionsHtml = `
      <option value="auto" ${curP === 'auto' ? 'selected' : ''}>${browserProxyLabel}</option>
      <option value="direct" ${curP === 'direct' ? 'selected' : ''}>${t('cfg_proxy_direct')}</option>
      <option value="default" ${curP === 'default' ? 'selected' : ''}>${t('cfg_proxy_default')}</option>
    `;
    if (clientDetectedProxies && clientDetectedProxies.length > 0) {
      clientDetectedProxies.forEach((p) => {
        const isSel = curP === p.url ? 'selected' : '';
        proxyOptionsHtml += `<option value="${p.url}" ${isSel}>${p.name}</option>`;
      });
    } else {
      proxyOptionsHtml += `
        <option value="http://127.0.0.1:7890" ${curP === 'http://127.0.0.1:7890' ? 'selected' : ''}>Clash / Verge (7890)</option>
        <option value="http://127.0.0.1:1080" ${curP === 'http://127.0.0.1:1080' ? 'selected' : ''}>sing-box / SOCKS5 (1080)</option>
        <option value="socks5://127.0.0.1:10808" ${curP === 'socks5://127.0.0.1:10808' ? 'selected' : ''}>v2rayN SOCKS5 (10808)</option>
        <option value="http://127.0.0.1:10809" ${curP === 'http://127.0.0.1:10809' ? 'selected' : ''}>v2rayN HTTP (10809)</option>
      `;
    }
    proxyOptionsHtml += `<option value="custom" ${curP === 'custom' ? 'selected' : ''}>${t('cfg_proxy_custom')}</option>`;

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
        <button class="btn-sm btn-primary action-push">${item.mediaType === 'bili_dash' ? '一键合并下载' : t('btn_push')}</button>
        <button class="btn-sm btn-secondary action-config" title="${t('btn_config')}">${t('btn_config')}</button>
        <button class="btn-sm btn-secondary action-copy-cmd" title="${t('btn_copy_cmd')}">${t('btn_copy_cmd')}</button>
        <button class="btn-sm btn-secondary action-preview">${t('btn_preview')}</button>
        <button class="btn-sm btn-secondary action-copy" title="${t('tip_copy_url', '点击复制完整直链')}">${t('btn_copy')}</button>
        <button class="btn-sm btn-secondary action-copy-b64" title="${t('tip_copy_b64', '点击复制Base64编码链接')}">${t('btn_copy_b64')}</button>
        <button class="btn-sm btn-danger action-del">${t('btn_delete')}</button>
      </div>
      <div class="card-config-panel ${isExpanded ? '' : 'hidden'}">
        <div class="config-row">
          <span class="config-label">${t('cfg_savedir')}</span>
          <input type="text" class="config-input cfg-savedir" placeholder="${t('cfg_savedir_placeholder')}" value="${escapeHtml(savedCfg.saveDir || '')}">
        </div>
        <div class="config-row">
          <span class="config-label">${t('cfg_threads')}</span>
          <select class="config-select cfg-threads">
            <option value="" ${!savedCfg.threadCount ? 'selected' : ''}>${t('cfg_threads_follow')}</option>
            <option value="4" ${savedCfg.threadCount === '4' ? 'selected' : ''}>${t('cfg_threads_4')}</option>
            <option value="8" ${savedCfg.threadCount === '8' ? 'selected' : ''}>${t('cfg_threads_8')}</option>
            <option value="16" ${savedCfg.threadCount === '16' ? 'selected' : ''}>${t('cfg_threads_16')}</option>
            <option value="32" ${savedCfg.threadCount === '32' ? 'selected' : ''}>${t('cfg_threads_32')}</option>
          </select>
        </div>
        <div class="config-row">
          <span class="config-label">${t('cfg_proxy')}</span>
          <select class="config-select cfg-proxy">
            ${proxyOptionsHtml}
          </select>
        </div>
        <div class="config-row cfg-custom-proxy-row ${savedCfg.proxy === 'custom' ? '' : 'hidden'}">
          <span class="config-label">${t('cfg_proxy_addr', '代理地址:')}</span>
          <input type="text" class="config-input cfg-custom-proxy" placeholder="${t('cfg_custom_proxy_placeholder')}" value="${escapeHtml(savedCfg.customProxy || '')}">
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
    const proxySelect = configPanel.querySelector('.cfg-proxy');
    const customProxyRow = configPanel.querySelector('.cfg-custom-proxy-row');
    const customProxyInput = configPanel.querySelector('.cfg-custom-proxy');
    const saveDirInput = configPanel.querySelector('.cfg-savedir');
    const threadsSelect = configPanel.querySelector('.cfg-threads');

    if (savedCfg.proxy) {
      proxySelect.value = savedCfg.proxy;
    }

    function syncState() {
      expandedConfigState.set(item.id, {
        expanded: !configPanel.classList.contains('hidden'),
        saveDir: saveDirInput.value.trim(),
        threadCount: threadsSelect.value,
        proxy: proxySelect.value,
        customProxy: customProxyInput.value.trim()
      });
    }

    configBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      configPanel.classList.toggle('hidden');
      syncState();
    });

    saveDirInput.addEventListener('input', syncState);
    threadsSelect.addEventListener('change', syncState);
    proxySelect.addEventListener('change', () => {
      if (proxySelect.value === 'custom') {
        customProxyRow.classList.remove('hidden');
      } else {
        customProxyRow.classList.add('hidden');
      }
      syncState();
    });
    customProxyInput.addEventListener('input', syncState);

    function getTaskConfigOptions() {
      const saveDir = configPanel.querySelector('.cfg-savedir').value.trim();
      const threadCount = configPanel.querySelector('.cfg-threads').value;
      const pVal = proxySelect.value;
      let finalProxy = '';
      if (pVal === 'auto' || pVal === 'browser') {
        finalProxy = detectedProxy.proxyUrl || 'direct';
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
      } else if ((cfg.proxy === 'auto' || cfg.proxy === 'browser') && detectedProxy.proxyUrl) {
        proxyForCmd = detectedProxy.proxyUrl;
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
      cmd += ` --auto-select --live-perform-as-vod --append-url-params -M format=mp4`;
      if (proxyForCmd) {
        cmd += ` --custom-proxy "${proxyForCmd}"`;
      }
      if (item.referer) {
        cmd += ` -H "Referer: ${item.referer}"`;
      }
      if (item.userAgent) {
        cmd += ` -H "User-Agent: ${item.userAgent}"`;
      }
      if (item.cookie) {
        cmd += ` -H "Cookie: ${item.cookie}"`;
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

      // 推送前确保拥有最新 Cookie 凭证
      if (!item.cookie && chrome.cookies) {
        try {
          const dom = (ref ? new URL(ref).hostname : (item.url ? new URL(item.url).hostname : ''));
          if (dom) {
            const cks = await chrome.cookies.getAll({ domain: dom });
            if (cks && cks.length > 0) {
              item.cookie = cks.map(c => `${c.name}=${c.value}`).join('; ');
            }
          }
        } catch (e) {}
      }
      const taskData = {
        url: item.url,
        audioUrl: item.audioUrl || '',
        title: titleInput.value.trim() || item.pageTitle || 'video',
        saveName: titleInput.value.trim() || item.pageTitle || 'video',
        mediaType: item.mediaType,
        resolution: getItemResolution(item),
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

  function setPreviewHeaders(item, callback) {
    const ref = item.referer || item.pageUrl || '';
    let origin = '';
    if (ref) {
      try { origin = new URL(ref).origin; } catch (e) {}
    }
    const headers = [
      { header: 'Referer', operation: 'set', value: ref },
      { header: 'User-Agent', operation: 'set', value: item.userAgent || navigator.userAgent }
    ];
    if (origin) {
      headers.push({ header: 'Origin', operation: 'set', value: origin });
    }
    if (item.cookie) {
      headers.push({ header: 'Cookie', operation: 'set', value: item.cookie });
    }

    if (chrome.declarativeNetRequest && chrome.declarativeNetRequest.updateSessionRules) {
      chrome.declarativeNetRequest.updateSessionRules({
        removeRuleIds: [PREVIEW_RULE_ID],
        addRules: [{
          id: PREVIEW_RULE_ID,
          priority: 100,
          action: {
            type: 'modifyHeaders',
            requestHeaders: headers
          },
          condition: {
            resourceTypes: ['xmlhttprequest', 'media', 'image', 'other'],
            initiatorDomains: [chrome.runtime.id]
          }
        }]
      }, () => {
        if (callback) callback();
      });
    } else {
      chrome.runtime.sendMessage({ action: 'SET_PREVIEW_HEADERS', data: item }, () => {
        if (callback) callback();
      });
    }
  }

  function clearPreviewHeaders(callback) {
    if (chrome.declarativeNetRequest && chrome.declarativeNetRequest.updateSessionRules) {
      chrome.declarativeNetRequest.updateSessionRules({
        removeRuleIds: [PREVIEW_RULE_ID]
      }, () => {
        if (callback) callback();
      });
    } else {
      chrome.runtime.sendMessage({ action: 'CLEAR_PREVIEW_HEADERS' }, () => {
        if (callback) callback();
      });
    }
  }

  function openPreviewModal(item) {
    currentPreviewItem = item;
    const statusEl = document.getElementById('previewStatus');
    if (statusEl) {
      statusEl.textContent = '正在注入防盗链认证并建立连接...';
      statusEl.style.color = '#a1a1aa';
    }
    previewTitle.textContent = item.pageTitle || '媒体预览';
    previewModal.classList.remove('hidden');

    setPreviewHeaders(item, () => {
      if (item.mediaType === 'audio') {
        previewVideo.classList.add('hidden');
        previewAudio.classList.remove('hidden');
        previewAudio.src = item.url;
        previewAudio.play().catch(() => {});
        if (statusEl) statusEl.textContent = '▶ 音频播放中';
      } else {
        previewAudio.classList.add('hidden');
        previewVideo.classList.remove('hidden');

        if (item.mediaType === 'm3u8' && window.Hls && Hls.isSupported()) {
          if (activeHls) activeHls.destroy();
          activeHls = new Hls({
            enableWorker: true,
            lowLatencyMode: false
          });
          activeHls.loadSource(item.url);
          activeHls.attachMedia(previewVideo);

          let totalFragments = 0;
          activeHls.on(Hls.Events.MANIFEST_PARSED, (event, data) => {
            if (statusEl) statusEl.textContent = '▶ 播放中 · 正在探测码率与估算大小...';
            previewVideo.play().catch(() => {});
            // 注意：不要用 hls.js 的 levels[0] 回写 item.resolution。
            // levels 按码率升序排列，levels[0] 是最低画质，
            // 会把 1080P 的条目错改成 360P 并持久化到列表。
          });

          activeHls.on(Hls.Events.LEVEL_LOADED, (event, data) => {
            if (data.details && data.details.fragments) {
              totalFragments = data.details.fragments.length;
              if (data.details.totalduration && !item.duration) {
                item.duration = data.details.totalduration;
              }
            }
          });

          const sampleFrags = [];
          function onFragLoaded(event, data) {
            const frag = data.frag;
            const stats = frag && frag.stats;
            if (!frag || !stats || !frag.duration) return;
            const bytes = stats.total || stats.loaded || 0;
            const dur = frag.duration || 0;
            if (!bytes || !dur) return;
            sampleFrags.push({ bytes, dur });
            if (sampleFrags.length >= 3) {
              const totBytes = sampleFrags.reduce((a, b) => a + b.bytes, 0);
              const totDur = sampleFrags.reduce((a, b) => a + b.dur, 0);
              const bps = (totBytes * 8) / totDur;
              const mbps = (bps / (1024 * 1024)).toFixed(2) + ' Mbps';
              let estSizeStr = '';
              if (totalFragments > 0) {
                const avgBytes = totBytes / sampleFrags.length;
                const estBytes = avgBytes * totalFragments;
                estSizeStr = ` | 预估大小: ${formatSize(estBytes)}`;
              }
              const resStr = item.resolution ? `[${item.resolution}] ` : '';
              if (statusEl) {
                statusEl.innerHTML = `<span style="color:#22c55e;">● 正常播放中</span> · ${resStr}码率: ${mbps}${estSizeStr}`;
              }
              activeHls.off(Hls.Events.FRAG_LOADED, onFragLoaded);
            }
          }
          activeHls.on(Hls.Events.FRAG_LOADED, onFragLoaded);

          activeHls.on(Hls.Events.ERROR, (event, data) => {
            if (data.fatal) {
              if (statusEl) {
                statusEl.innerHTML = '<span style="color:#ef4444;">预览受阻，请点击下方「在网页内播放」或改用原链直连</span>';
              }
            }
          });
        } else {
          previewVideo.src = item.url;
          if (item.audioUrl) {
            previewAudio.src = item.audioUrl;
            previewAudio.currentTime = 0;
            previewAudio.play().catch(() => {});
            previewVideo.onplay = () => previewAudio.play().catch(() => {});
            previewVideo.onpause = () => previewAudio.pause();
            previewVideo.onseeking = () => { previewAudio.currentTime = previewVideo.currentTime; };
          }
          previewVideo.play().catch(() => {});
          if (statusEl) statusEl.textContent = item.audioUrl ? '▶ 音画双轨同步播放中' : '▶ 视频播放中';
        }
      }
    });
  }

  function closePreviewModal() {
    previewModal.classList.add('hidden');
    currentPreviewItem = null;
    clearPreviewHeaders();
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
    const statusEl = document.getElementById('previewStatus');
    if (statusEl) statusEl.textContent = '正在准备播放…';
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

    const t = typeof ExtI18n !== 'undefined' ? ExtI18n.t : (k => k);
    const browserProxyLabel = detectedProxy.proxyUrl
      ? `${t('cfg_proxy_browser', '跟随浏览器代理')} (推荐: ${detectedProxy.proxyUrl})`
      : (detectedProxy.mode === 'direct' ? `${t('cfg_proxy_browser', '跟随浏览器代理')} (直连)` : `${t('cfg_proxy_browser', '跟随浏览器代理')} (推荐)`);
    document.querySelectorAll('.cfg-proxy option[value="auto"]').forEach((opt) => {
      opt.textContent = browserProxyLabel;
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

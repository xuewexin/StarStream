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
  let clientHasStreamProxy = false;
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
  const previewStatus = document.getElementById('previewStatus');
  const previewInlineBtn = document.getElementById('previewInlineBtn');
  const previewRawBtn = document.getElementById('previewRawBtn');
  let currentPreviewItem = null;
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

    if (el('settingsTitle')) el('settingsTitle').textContent = t('settings_title');
    if (el('lblSettingLang')) el('lblSettingLang').textContent = t('setting_lang');
    if (el('lblSettingPort')) el('lblSettingPort').textContent = t('setting_port');
    const f1 = document.querySelector('#lblSettingFilterFrags span');
    if (f1) f1.textContent = t('setting_filter_frags');
    const f2 = document.querySelector('#lblSettingAutoPurge span');
    if (f2) f2.textContent = t('setting_auto_purge');
    const f3 = document.querySelector('#lblSettingAutoPush span');
    if (f3) f3.textContent = t('setting_auto_push');
    if (el('lblSettingMinSize')) el('lblSettingMinSize').textContent = t('setting_min_size');
    if (el('helpTitle')) el('helpTitle').textContent = t('setting_help_title');
    if (el('helpDesc')) el('helpDesc').textContent = t('setting_help_desc');
    if (el('saveSettingsBtn')) el('saveSettingsBtn').textContent = t('btn_save_settings');
  }

  function initLanguageUI() {
    if (typeof ExtI18n === 'undefined') return;
    const langSelect = document.getElementById('settingLang');
    const langMenu = document.getElementById('langMenu');
    const btnLang = document.getElementById('btnLang');

    if (langSelect) {
      langSelect.innerHTML = '';
      ExtI18n.SUPPORTED_LANGS.forEach(l => {
        const opt = document.createElement('option');
        opt.value = l.code;
        opt.textContent = l.name;
        if (l.code === ExtI18n.getLang()) opt.selected = true;
        langSelect.appendChild(opt);
      });
      langSelect.onchange = () => switchLanguage(langSelect.value);
    }

    if (langMenu) {
      langMenu.innerHTML = '';
      ExtI18n.SUPPORTED_LANGS.forEach(l => {
        const item = document.createElement('div');
        item.style.cssText = 'padding:6px 14px;font-size:12px;color:#cbd5e1;cursor:pointer;white-space:nowrap;transition:background 0.2s;';
        if (l.code === ExtI18n.getLang()) {
          item.style.color = '#38bdf8';
          item.style.fontWeight = 'bold';
        }
        item.textContent = l.name;
        item.onmouseenter = () => item.style.backgroundColor = '#1e293b';
        item.onmouseleave = () => item.style.backgroundColor = 'transparent';
        item.onclick = (e) => {
          e.stopPropagation();
          langMenu.classList.add('hidden');
          switchLanguage(l.code);
        };
        langMenu.appendChild(item);
      });
    }

    if (btnLang && langMenu) {
      btnLang.onclick = (e) => {
        e.stopPropagation();
        langMenu.classList.toggle('hidden');
      };
      document.addEventListener('click', () => {
        langMenu.classList.add('hidden');
      });
    }
  }

  function switchLanguage(langCode) {
    if (typeof ExtI18n === 'undefined') return;
    localStorage.setItem('user_manual_lang', '1');
    ExtI18n.setLang(langCode);
    const langSelect = document.getElementById('settingLang');
    if (langSelect) langSelect.value = langCode;
    initLanguageUI();
    applyI18nUI();
    renderList();
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
    // 1. 获取当前活动窗口的标签页 ID 与所有仍存活的标签页集合
    await initTabTracking();

    // 2. 清除当前标签页未读角标提示
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

    // 核心清理：自动核对并抹除所有已关闭网页残留的爬取视频
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
      chrome.tabs.query({}, (tabs) => {
        liveTabIds = new Set((tabs || []).map((t) => t.id));
        chrome.tabs.query({ active: true, currentWindow: true }, (actTabs) => {
          if (actTabs && actTabs[0]) {
            currentActiveTabId = actTabs[0].id;
          }
          resolve();
        });
      });
    });
  }

  // 监听标签页生命周期：页面关闭或刷新导航时，自动实时清除其爬取视频
  function bindTabLifecycleListeners() {
    try {
      chrome.tabs.onRemoved.addListener((closedTabId) => {
        liveTabIds.delete(closedTabId);
        mediaList = mediaList.filter((it) => it.tabId !== closedTabId);
        renderList();
        updateCategoryCounts();
      });

      chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
        if (changeInfo.status === 'loading') {
          mediaList = mediaList.filter((it) => it.tabId !== tabId);
          renderList();
          updateCategoryCounts();
        }
      });
    } catch (e) {}
  }

  function updateProxyTips() {
    const tipText = detectedProxy.proxyUrl
      ? `浏览器代理: ${detectedProxy.proxyUrl}`
      : (clientEffectiveProxy ? `客户端代理: ${clientEffectiveProxy}` : (detectedProxy.label ? `网络环境: ${detectedProxy.label}` : '代理: 直连/跟随系统'));

    document.querySelectorAll('.cfg-proxy-tip').forEach((el) => {
      el.textContent = tipText;
    });
  }

  function bindEvents() {
    // 页面范围切换 (当前网页 / 所有存活网页)
    const btnScopeCurrent = document.getElementById('scopeCurrentTab');
    const btnScopeAll = document.getElementById('scopeAllTabs');

    if (btnScopeCurrent && btnScopeAll) {
      btnScopeCurrent.addEventListener('click', () => {
        btnScopeCurrent.classList.add('active');
        btnScopeAll.classList.remove('active');
        currentScope = 'current';
        renderList();
        updateCategoryCounts();
      });

      btnScopeAll.addEventListener('click', () => {
        btnScopeAll.classList.add('active');
        btnScopeCurrent.classList.remove('active');
        currentScope = 'all';
        renderList();
        updateCategoryCounts();
      });
    }

    // 分类筛选
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

    const filterAdsCheckbox = document.getElementById('filterAdsCheckbox');
    if (filterAdsCheckbox) {
      filterAdsCheckbox.addEventListener('change', () => {
        renderList();
      });
    }

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
      if (confirm('确定要清空已嗅探的媒体记录吗？')) {
        await chrome.storage.local.set({ mediaList: [] });
        selectedIds.clear();
        mediaList = [];
        renderList();
        updateCategoryCounts();
        chrome.action.setBadgeText({ text: '' });
      }
    });

    // 分片文件夹管理弹窗
    const btnFrag = document.getElementById('btnFragments');
    if (btnFrag && fragmentsModal) {
      btnFrag.addEventListener('click', () => {
        openFragmentsModal();
      });
      document.getElementById('closeFragmentsBtn').addEventListener('click', () => {
        fragmentsModal.classList.add('hidden');
      });
      document.getElementById('btnRefreshFrags').addEventListener('click', loadFragmentsStatus);
      document.getElementById('btnCleanAllFrags').addEventListener('click', cleanAllFragments);
    }

    document.getElementById('btnBatchPush').addEventListener('click', async () => {
      const selectedItems = mediaList.filter((it) => selectedIds.has(it.id));
      if (!selectedItems.length) return;

      const btn = document.getElementById('btnBatchPush');
      btn.textContent = '推送中...';
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
        const data = await resp.json();
        clientOnline = true;
        // 旧版客户端没有 /api/stream，需自动降级到网页内播放器
        clientHasStreamProxy = !!data.stream_proxy;
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

    clientOnline = false;
    clientHasStreamProxy = false;
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
      if (res.ok) {
        const data = await res.json();
        const folders = data.folders || [];
        statsEl.textContent = `${folders.length} (total: ${data.count || 0})`;

        if (!folders.length) {
          container.innerHTML = `<div style="color:#4ade80; text-align:center; padding:10px;">${t('frag_clean')}</div>`;
          return;
        }

        container.innerHTML = '';
        folders.forEach((f) => {
          const itemDiv = document.createElement('div');
          itemDiv.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:6px 4px; border-bottom:1px solid #27272a; font-size:12px;';
          itemDiv.innerHTML = `
            <div style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; padding-right:8px;" title="${f.path}">
              ${f.name}
            </div>
            <div style="color:#38bdf8; font-size:11px; white-space:nowrap;">
              ${f.ts_count} | ${formatSize(f.size)}
            </div>
          `;
          container.appendChild(itemDiv);
        });
        return;
      }
    } catch (e) {}

    statsEl.textContent = t('status_offline');
    container.innerHTML = `<div style="color:#f87171; text-align:center; padding:10px;">${t('cap_client_offline')} (127.0.0.1:18910)</div>`;
  }

  async function cleanAllFragments() {
    if (!confirm('Clear all segments?')) return;
    try {
      const res = await fetch(`http://127.0.0.1:${clientPort}/api/fragments`, { method: 'DELETE' });
      if (res.ok) {
        loadFragmentsStatus();
        return;
      }
    } catch (e) {}
  }

  async function loadSettings() {
    const { settings = {} } = await chrome.storage.local.get('settings');
    clientPort = settings.serverPort || 18910;
    document.getElementById('settingPort').value = clientPort;
    document.getElementById('settingAutoPush').checked = !!settings.autoPush;
    document.getElementById('settingMinSize').value = settings.minSizeKB || 0;
    if (typeof ExtI18n !== 'undefined') {
      const sel = document.getElementById('settingLang');
      if (sel) sel.value = ExtI18n.getLang();
    }
  }

  async function saveSettings() {
    const port = parseInt(document.getElementById('settingPort').value, 10) || 18910;
    const autoPush = document.getElementById('settingAutoPush').checked;
    const minSizeKB = parseInt(document.getElementById('settingMinSize').value, 10) || 0;

    clientPort = port;
    await chrome.storage.local.set({
      settings: { serverPort: port, autoPush, minSizeKB, filterFragments: true, onlyLiveTabs: true }
    });

    if (typeof ExtI18n !== 'undefined') {
      const sel = document.getElementById('settingLang');
      if (sel && sel.value !== ExtI18n.getLang()) {
        switchLanguage(sel.value);
      }
    }

    settingsPanel.classList.add('hidden');
    await checkClientStatus();
  }

  async function loadAndRenderMedia() {
    const res = await chrome.storage.local.get('mediaList');
    // 加载时过滤掉所有切片分片
    mediaList = (res.mediaList || []).filter((item) => !isFragmentUrl(item.url));
    renderList();
    updateCategoryCounts();
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
    const m = s.match(/(\d{3,4})[xX*](\d{3,4})/);
    if (m) {
      return Math.min(parseInt(m[1]), parseInt(m[2]));
    }
    return 0;
  }

  function compareMediaItems(a, b) {
    // 1. 过滤广告/非正片
    if (a.isFeature && !b.isFeature) return -1;
    if (!a.isFeature && b.isFeature) return 1;
    if (!a.isAd && b.isAd) return -1;
    if (a.isAd && !b.isAd) return 1;

    // 2. 时长降序 (时长越长越排在前面)
    const durA = Number(a.duration || 0);
    const durB = Number(b.duration || 0);
    if (Math.abs(durA - durB) > 3) {
      return durB - durA;
    }

    // 3. 画质/分辨率降序
    const resA = getResolutionScore(a.resolution);
    const resB = getResolutionScore(b.resolution);
    if (resA !== resB) {
      return resB - resA;
    }

    // 4. M3U8 格式优先
    if (a.mediaType === 'm3u8' && b.mediaType !== 'm3u8') return -1;
    if (a.mediaType !== 'm3u8' && b.mediaType === 'm3u8') return 1;

    // 5. 大小降序
    const sizeA = Number(a.contentLength || a.size || 0);
    const sizeB = Number(b.contentLength || b.size || 0);
    if (sizeA !== sizeB) return sizeB - sizeA;

    return (b.timestamp || 0) - (a.timestamp || 0);
  }

  // 核心过滤与排序算法：
  // 1. 仅展示当前页面抓取的视频
  // 2. 严格按 时长-画质 降序排列展示
  // 3. 过滤已知切片分片
  function getFilteredItems() {
    const list = mediaList.filter((item) => {
      // 坚决丢弃切片
      if (isFragmentUrl(item.url)) {
        return false;
      }

      // 仅展示当前页面抓取的视频
      if (currentActiveTabId >= 0 && item.tabId !== currentActiveTabId) {
        return false;
      }

      // 仅显示页面还存在的网站上爬取的视频：若标签页已被关闭，立即过滤消除
      if (item.tabId !== undefined && item.tabId !== null && item.tabId >= 0) {
        if (!liveTabIds.has(item.tabId)) {
          return false;
        }
      }

      // 媒体类型分类
      if (currentCategory !== 'all' && item.mediaType !== currentCategory) {
        return false;
      }

      // 智能广告切片过滤
      const filterAdsEl = document.getElementById('filterAdsCheckbox');
      if (filterAdsEl && filterAdsEl.checked && item.isAd) {
        return false;
      }

      // 关键词搜索
      if (searchKeyword) {
        const title = (item.pageTitle || '').toLowerCase();
        const url = (item.url || '').toLowerCase();
        if (!title.includes(searchKeyword) && !url.includes(searchKeyword)) {
          return false;
        }
      }

      return true;
    });

    // 按照 时长-画质 降序排列
    list.sort(compareMediaItems);
    return list;
  }

  function updateCategoryCounts() {
    // 当前页面下有效的视频项
    const scopedItems = mediaList.filter((item) => {
      if (isFragmentUrl(item.url)) return false;
      if (currentActiveTabId >= 0 && item.tabId !== currentActiveTabId) {
        return false;
      }
      if (item.tabId !== undefined && item.tabId !== null && item.tabId >= 0) {
        if (!liveTabIds.has(item.tabId)) return false;
      }
      return true;
    });

    document.getElementById('countAll').textContent = scopedItems.length;
    document.getElementById('countM3u8').textContent = scopedItems.filter((i) => i.mediaType === 'm3u8').length;
    document.getElementById('countVideo').textContent = scopedItems.filter((i) => i.mediaType === 'video').length;
    document.getElementById('countAudio').textContent = scopedItems.filter((i) => i.mediaType === 'audio').length;
    document.getElementById('countOther').textContent = scopedItems.filter((i) => i.mediaType === 'other').length;
  }

  function updateBatchBar() {
    const count = selectedIds.size;
    if (count > 0) {
      batchBar.classList.remove('hidden');
      batchCountText.textContent = typeof ExtI18n !== 'undefined' ? ExtI18n.t('batch_selected', count) : `已选 ${count} 项`;
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

    const t = typeof ExtI18n !== 'undefined' ? ExtI18n.t : (k => k);
    const isChecked = selectedIds.has(item.id);
    const domain = getDomain(item.url);
    const title = item.pageTitle || t('unknown_site', '未命名媒体');

    let tagsHtml = `<span class="tag-badge tag-type">${(item.mediaType || 'other').toUpperCase()}</span>`;
    if (item.isMaster) {
      tagsHtml += `<span class="tag-badge" style="background:#6366f1;color:#fff;" title="主清单，已自动展开全部清晰度子流">多清晰度${item.variantCount ? ' ×' + item.variantCount : ''}</span>`;
    }
    if (item.isVariant) {
      tagsHtml += `<span class="tag-badge" style="background:#8b5cf6;color:#fff;" title="由 master playlist 自动展开，可直接下载该画质">${escapeHtml(item.variantLabel || '清晰度子流')}</span>`;
    }
    if (item.isAd) {
      tagsHtml += `<span class="tag-badge" style="background:#ef4444;color:#fff;" title="${item.adReason || t('tag_ad', '疑似切片')}">${t('tag_ad')}${item.duration ? ' (' + item.duration + 's)' : ''}</span>`;
    } else if (item.isFeature) {
      tagsHtml += `<span class="tag-badge" style="background:#10b981;color:#fff;" title="${t('tip_feature_video', '当前页面时长最长的主视频')}">${t('tag_feature')}</span>`;
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

    // 动态生成代理下拉列表（优先展示当前存活的本地代理客户端，避免死端口连接拒绝）
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

      try {
        const resp = await fetch(`http://127.0.0.1:${clientPort}/api/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(taskData)
        });
        if (resp.ok) {
          pushBtn.textContent = t('cap_pushed', '已加入队列');
          pushBtn.style.backgroundColor = '#166534';
          pushBtn.style.color = '#ffffff';
          return;
        }
      } catch (err) {}

      chrome.runtime.sendMessage({ action: 'PUSH_TO_CLIENT', data: taskData }, (res) => {
        if (res && res.success) {
          pushBtn.textContent = t('cap_pushed', '已加入队列');
          pushBtn.style.backgroundColor = '#166534';
          pushBtn.style.color = '#ffffff';
        } else {
          pushBtn.textContent = t('status_offline', '客户端离线');
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

  function buildPreviewProxyUrl(item) {
    const params = new URLSearchParams();
    params.set('url', item.url);
    const ref = item.referer || item.pageUrl || '';
    if (ref) params.set('referer', ref);
    if (item.userAgent) params.set('ua', item.userAgent);
    if (item.cookie) params.set('cookie', item.cookie);
    if (item.authorization) params.set('auth', item.authorization);
    try {
      if (ref) params.set('origin', new URL(ref).origin);
    } catch (e) {}
    return `http://127.0.0.1:${clientPort}/api/stream?${params.toString()}`;
  }

  function setPreviewStatus(msg, isError) {
    if (!previewStatus) return;
    previewStatus.textContent = msg;
    previewStatus.style.color = isError ? '#f87171' : '#a1a1aa';
  }

  function destroyHls() {
    if (activeHls) {
      try { activeHls.destroy(); } catch (e) {}
      activeHls = null;
    }
  }

  function attachPreviewErrorHandlers() {
    previewVideo.onerror = () => {
      const code = previewVideo.error ? previewVideo.error.code : 0;
      if (code) {
        setPreviewStatus(`媒体加载失败 (错误码 ${code})：通常是防盗链或网络不可达，可点「在网页内播放」，或启动桌面客户端后重试。`, true);
      }
    };
    previewAudio.onerror = () => {
      const code = previewAudio.error ? previewAudio.error.code : 0;
      if (code) setPreviewStatus(`音频加载失败 (错误码 ${code})，可尝试「在网页内播放」。`, true);
    };
  }

  function playPreviewUrl(item, playUrl, label) {
    destroyHls();
    try { previewVideo.pause(); previewAudio.pause(); } catch (e) {}
    setPreviewStatus(label, false);

    if (item.mediaType === 'mpd') {
      setPreviewStatus('DASH (MPD) 流暂不支持在线预览，请推送到客户端下载后观看。', true);
      return;
    }

    if (item.mediaType === 'audio') {
      previewVideo.classList.add('hidden');
      previewAudio.classList.remove('hidden');
      previewAudio.src = playUrl;
      previewAudio.play().catch(() => {});
      return;
    }

    previewAudio.classList.add('hidden');
    previewVideo.classList.remove('hidden');

    if (item.mediaType === 'm3u8' && window.Hls && Hls.isSupported()) {
      activeHls = new Hls({ enableWorker: true, lowLatencyMode: false, maxBufferLength: 30 });
      activeHls.loadSource(playUrl);
      activeHls.attachMedia(previewVideo);
      activeHls.on(Hls.Events.MANIFEST_PARSED, () => {
        setPreviewStatus('清单解析成功，正在起播…', false);
        previewVideo.play().catch(() => {});
      });
      activeHls.on(Hls.Events.ERROR, (evt, data) => {
        if (!data || !data.fatal) return;
        setPreviewStatus(`播放失败：${data.type || ''} / ${data.details || ''}。请确认桌面客户端已启动且代理可用，或点「在网页内播放」。`, true);
      });
    } else {
      previewVideo.src = playUrl;
      previewVideo.play().catch(() => {});
    }
  }

  function openInlinePreview(item) {
    return new Promise((resolve) => {
      const data = Object.assign({}, item, { tabId: item.tabId });
      chrome.runtime.sendMessage({ action: 'INJECT_HLS_PLAYER', data }, (res) => {
        if (res && res.success) {
          setPreviewStatus('已在目标网页内打开播放器（页面上下文自带站点 Referer / Cookie）。若未出现播放层，请刷新网页后重试。', false);
        } else {
          setPreviewStatus('网页内播放失败：' + ((res && res.error) || '目标页面已关闭或不允许注入'), true);
        }
        resolve(res);
      });
    });
  }

  async function openPreviewModal(item) {
    currentPreviewItem = item;
    previewTitle.textContent = item.pageTitle || '媒体预览';
    previewModal.classList.remove('hidden');
    attachPreviewErrorHandlers();

    if (previewInlineBtn) previewInlineBtn.onclick = () => openInlinePreview(item);
    if (previewRawBtn) {
      previewRawBtn.onclick = () => playPreviewUrl(item, item.url, '正在用原链直连（可能受 CORS / 防盗链限制）…');
    }

    // 主动刷新一次连接状态，避免 popup 刚打开时状态尚未就绪
    await checkClientStatus();

    if (clientOnline && clientHasStreamProxy) {
      playPreviewUrl(
        item,
        buildPreviewProxyUrl(item),
        '正在通过星流本地代理加载（自动携带站点 Referer / Cookie，绕过 CORS 与防盗链）…'
      );
    } else {
      const reason = clientOnline
        ? '当前桌面客户端版本较旧（缺少本地媒体代理）：自动改用网页内播放器…'
        : '桌面客户端未连接：自动改用网页内播放器（页面上下文自带站点身份）…';
      setPreviewStatus(reason, false);
      await openInlinePreview(item);
    }
  }

  function closePreviewModal() {
    previewModal.classList.add('hidden');
    destroyHls();
    try { previewVideo.pause(); } catch (e) {}
    previewVideo.removeAttribute('src');
    previewVideo.load();
    try { previewAudio.pause(); } catch (e) {}
    previewAudio.removeAttribute('src');
    previewAudio.load();
    setPreviewStatus('正在准备播放…', false);
    currentPreviewItem = null;
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

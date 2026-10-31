// popup.js - CatCatch Pro Modern Minimalist Controller
// 支持：仅抓取整个完整视频、页面消失自动刷新清除、本地活跃代理自动对齐、分片文件夹管理
(function () {
  'use strict';

  // 严格过滤已知切片分片特征
  const FRAGMENT_REGEX = /(\.ts|\.m4s|\.m4v|\.vtt|\.srt|\.key|\.mp2t)(\?|#|$)|([-_/](seg|segment|chunk|frag|slice|part)[-_/\d]+)|(\b(init\.mp4|range=|\/stream\/segment))/i;

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

  document.addEventListener('DOMContentLoaded', async () => {
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
        mediaList = (changes.mediaList.newValue || []).filter((it) => !FRAGMENT_REGEX.test(it.url));
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
      ? `⚡ 检测到当前浏览器代理: ${detectedProxy.proxyUrl}`
      : (clientEffectiveProxy ? `⚡ 当前客户端生效代理: ${clientEffectiveProxy}` : (detectedProxy.label ? `⚡ 网络环境: ${detectedProxy.label}` : '⚡ 代理: 直连/跟随系统'));

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
        const data = await resp.json();
        clientOnline = true;
        clientStatusBadge.className = 'status-pill online';
        clientStatusText.textContent = '客户端已连接';
        if (data.detected_proxies) clientDetectedProxies = data.detected_proxies;
        if (data.effective_proxy) clientEffectiveProxy = data.effective_proxy;
        if (data.temp_segments_dir) clientTempDir = data.temp_segments_dir;
        updateProxyTips();
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

  async function openFragmentsModal() {
    fragmentsModal.classList.remove('hidden');
    document.getElementById('fragDirPath').textContent = clientTempDir || 'Temp_Segments';
    loadFragmentsStatus();
  }

  async function loadFragmentsStatus() {
    const statsEl = document.getElementById('fragStats');
    const container = document.getElementById('fragListContainer');
    statsEl.textContent = '正在获取本地分片状态...';
    container.innerHTML = '<div style="color:#71717a; text-align:center; padding:10px;">加载中...</div>';

    try {
      const res = await fetch(`http://127.0.0.1:${clientPort}/api/fragments`, { method: 'GET' });
      if (res.ok) {
        const data = await res.json();
        const folders = data.folders || [];
        statsEl.textContent = `找到 ${folders.length} 个残留分片文件夹 (共 ${data.count || 0} 个)`;

        if (!folders.length) {
          container.innerHTML = '<div style="color:#4ade80; text-align:center; padding:10px;">✔ 当前分片目录干净，无残留切片文件</div>';
          return;
        }

        container.innerHTML = '';
        folders.forEach((f) => {
          const itemDiv = document.createElement('div');
          itemDiv.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:6px 4px; border-bottom:1px solid #27272a; font-size:12px;';
          itemDiv.innerHTML = `
            <div style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; padding-right:8px;" title="${f.path}">
              📁 ${f.name}
            </div>
            <div style="color:#38bdf8; font-size:11px; white-space:nowrap;">
              ${f.ts_count} 切片 | ${formatSize(f.size)}
            </div>
          `;
          container.appendChild(itemDiv);
        });
        return;
      }
    } catch (e) {}

    statsEl.textContent = '请先启动本地桌面客户端以读取分片文件夹';
    container.innerHTML = '<div style="color:#f87171; text-align:center; padding:10px;">客户端未连接 (127.0.0.1:18910)</div>';
  }

  async function cleanAllFragments() {
    if (!confirm('确定要清空全部未完成的分片临时切片吗？')) return;
    try {
      const res = await fetch(`http://127.0.0.1:${clientPort}/api/fragments`, { method: 'DELETE' });
      if (res.ok) {
        alert('分片文件夹已清空！');
        loadFragmentsStatus();
        return;
      }
    } catch (e) {}
    alert('操作失败，请确认客户端已在后台启动。');
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
      settings: { serverPort: port, autoPush, minSizeKB, filterFragments: true, onlyLiveTabs: true }
    });

    settingsPanel.classList.add('hidden');
    await checkClientStatus();
  }

  async function loadAndRenderMedia() {
    const res = await chrome.storage.local.get('mediaList');
    // 加载时过滤掉所有切片分片
    mediaList = (res.mediaList || []).filter((item) => !FRAGMENT_REGEX.test(item.url));
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
      if (FRAGMENT_REGEX.test(item.url)) {
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
      if (FRAGMENT_REGEX.test(item.url)) return false;
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
    if (item.isAd) {
      tagsHtml += `<span class="tag-badge" style="background:#ef4444;color:#fff;" title="${item.adReason || '疑似前贴片广告切片'}">⚠️ 疑似广告${item.duration ? ' (' + item.duration + 's)' : ''}</span>`;
    } else if (item.isFeature) {
      tagsHtml += `<span class="tag-badge" style="background:#10b981;color:#fff;" title="当前页面时长最长的主视频">⭐ 正片</span>`;
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
      tagsHtml += `<span class="tag-badge tag-key">加密 (AES-128)</span>`;
    }
    tagsHtml += `<span class="tag-badge tag-domain">${domain}</span>`;

    const proxyTipText = detectedProxy.proxyUrl
      ? `⚡ 浏览器代理: ${detectedProxy.proxyUrl}`
      : (clientEffectiveProxy ? `⚡ 本地生效代理: ${clientEffectiveProxy}` : '⚡ 代理: 直连/跟随系统');

    // 动态生成代理下拉列表（优先展示当前存活的本地代理客户端，避免死端口连接拒绝）
    let proxyOptionsHtml = `
      <option value="auto" selected>🎯 自动匹配可用代理 (推荐${clientEffectiveProxy ? ': ' + clientEffectiveProxy : ''})</option>
      <option value="direct">⚡ 直连 (不走任何代理)</option>
      <option value="default">💻 跟随客户端全局设置</option>
    `;
    if (clientDetectedProxies && clientDetectedProxies.length > 0) {
      clientDetectedProxies.forEach((p) => {
        proxyOptionsHtml += `<option value="${p.url}">🟢 ${p.name}</option>`;
      });
    } else {
      proxyOptionsHtml += `
        <option value="http://127.0.0.1:1080">sing-box / SOCKS5 (1080)</option>
        <option value="http://127.0.0.1:7890">Clash / Verge (7890)</option>
        <option value="socks5://127.0.0.1:10808">v2rayN SOCKS5 (10808)</option>
        <option value="http://127.0.0.1:10809">v2rayN HTTP (10809)</option>
      `;
    }
    proxyOptionsHtml += `<option value="custom">✏️ 手动输入代理地址...</option>`;

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
          <input type="text" class="config-input cfg-savedir" placeholder="留空使用客户端配置 (如 Downloads)">
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
            ${proxyOptionsHtml}
          </select>
        </div>
        <div class="config-row cfg-custom-proxy-row hidden">
          <span class="config-label">代理地址:</span>
          <input type="text" class="config-input cfg-custom-proxy" placeholder="例如 http://127.0.0.1:1080 或 http://127.0.0.1:7890">
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

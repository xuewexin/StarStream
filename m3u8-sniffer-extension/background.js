// background.js - CatCatch Pro Sniffer Engine & IPC Bridge
const MAX_ITEMS = 100;
const LOCAL_SERVER_URL = "http://127.0.0.1:18910";

// 支持的视音频与流媒体扩展名正则
const MEDIA_EXT_REGEX = /\.(m3u8|mpd|mp4|webm|flv|f4v|mkv|avi|mov|wmv|ts|mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)/i;

// 黑名单过滤（过滤广告、统计追踪、微小分片请求风暴）
const BLACKLIST_REGEX = /(google-analytics|cnzz|stat|beacon|doubleclick|clarity\.ms|hm\.baidu\.com|sentry\.io|segment\.ts\?)/i;

// 初始化存储
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(["mediaList", "settings"], (res) => {
    if (!res.mediaList) {
      chrome.storage.local.set({ mediaList: [] });
    }
    if (!res.settings) {
      chrome.storage.local.set({
        settings: {
          serverPort: 18910,
          autoPush: false,
          minSizeKB: 0,
          customRegex: ""
        }
      });
    }
  });
});

// 串行队列保证存储读写原子性
let storageQueue = Promise.resolve();

// 1. 监听请求发起 (捕获 Referer, UA, Cookie, Authorization)
chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    const url = details.url;
    if (BLACKLIST_REGEX.test(url)) return;
    if (!MEDIA_EXT_REGEX.test(url)) return;

    captureMediaRequest(details, null);
  },
  { urls: ["*://*/*"] },
  ["requestHeaders"]
);

// 2. 监听响应头部 (通过 Content-Type 捕获无后缀视频流及文件大小)
chrome.webRequest.onHeadersReceived.addListener(
  (details) => {
    const url = details.url;
    if (BLACKLIST_REGEX.test(url)) return;

    let contentType = "";
    let contentLength = 0;
    let contentDisposition = "";

    if (details.responseHeaders) {
      for (const h of details.responseHeaders) {
        const key = h.name.toLowerCase();
        if (key === "content-type") contentType = h.value.toLowerCase();
        if (key === "content-length") contentLength = parseInt(h.value, 10) || 0;
        if (key === "content-disposition") contentDisposition = h.value;
      }
    }

    const isMediaContent =
      contentType.startsWith("video/") ||
      contentType.startsWith("audio/") ||
      contentType.includes("vnd.apple.mpegurl") ||
      contentType.includes("x-mpegurl") ||
      contentType.includes("dash+xml") ||
      (contentType.includes("octet-stream") && MEDIA_EXT_REGEX.test(url));

    if (isMediaContent || MEDIA_EXT_REGEX.test(url)) {
      captureMediaRequest(details, {
        contentType,
        contentLength,
        contentDisposition
      });
    }
  },
  { urls: ["*://*/*"] },
  ["responseHeaders"]
);

// 3. 核心嗅探记录处理
async function captureMediaRequest(details, respInfo) {
  const url = details.url;
  if (!url || url.startsWith("blob:") || url.startsWith("data:") || url.startsWith("chrome:")) {
    return; // 忽略内存对象与非网络资源
  }
  const tabId = details.tabId;

  // 获取页面标题与网页 URL
  let pageTitle = "";
  let pageUrl = "";
  if (tabId >= 0) {
    try {
      const tab = await chrome.tabs.get(tabId);
      pageTitle = tab.title || "";
      pageUrl = tab.url || "";
    } catch (e) {}
  }

  // 提取请求头
  let referer = "";
  let userAgent = "";
  let cookie = "";
  let authorization = "";
  if (details.requestHeaders) {
    for (const h of details.requestHeaders) {
      const key = h.name.toLowerCase();
      if (key === "referer") referer = h.value || "";
      if (key === "user-agent") userAgent = h.value || "";
      if (key === "cookie") cookie = h.value || "";
      if (key === "authorization") authorization = h.value || "";
    }
  }

  // 识别媒体类型
  const mediaType = detectMediaType(url, respInfo ? respInfo.contentType : "");

  // 构造 BaseURL (主要用于 M3U8 相对切片地址拼接)
  let baseUrl = "";
  try {
    const u = new URL(url);
    const pathParts = u.pathname.split("/");
    pathParts.pop();
    baseUrl = u.origin + pathParts.join("/") + "/";
  } catch (e) {
    baseUrl = url.substring(0, url.lastIndexOf("/") + 1);
  }

  const entry = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    url: url,
    tabId: tabId,
    pageTitle: pageTitle,
    pageUrl: pageUrl,
    mediaType: mediaType,
    referer: referer,
    userAgent: userAgent,
    cookie: cookie,
    authorization: authorization,
    baseUrl: baseUrl,
    contentType: respInfo ? respInfo.contentType : "",
    contentLength: respInfo ? respInfo.contentLength : 0,
    timestamp: Date.now(),
    duration: 0,
    resolution: "",
    hasKey: false,
    keyUrl: ""
  };

  storageQueue = storageQueue.then(() => insertIntoStorage(entry)).catch(() => {});
  await storageQueue;

  // 异步深入解析 M3U8/MPD 流清单详细属性
  if (mediaType === "m3u8") {
    parseM3u8Metadata(entry).catch(() => {});
  }
}

function detectMediaType(url, contentType) {
  const u = url.toLowerCase().split("?")[0];
  if (u.endsWith(".m3u8") || contentType.includes("mpegurl")) return "m3u8";
  if (u.endsWith(".mpd") || contentType.includes("dash+xml")) return "mpd";
  if (
    anyEndsWith(u, [".mp4", ".flv", ".f4v", ".webm", ".mkv", ".avi", ".mov", ".wmv", ".ts"]) ||
    contentType.startsWith("video/")
  ) {
    return "video";
  }
  if (
    anyEndsWith(u, [".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".opus"]) ||
    contentType.startsWith("audio/")
  ) {
    return "audio";
  }
  return "other";
}

function anyEndsWith(str, exts) {
  return exts.some((ext) => str.endsWith(ext));
}

// 插入存储并去重
async function insertIntoStorage(entry) {
  let { mediaList = [] } = await chrome.storage.local.get("mediaList");
  // 清除可能遗留的 blob 伪协议地址
  mediaList = mediaList.filter((item) => !item.url.startsWith("blob:"));

  // 去重检测
  const existIdx = mediaList.findIndex((item) => item.url === entry.url);
  if (existIdx >= 0) {
    // 合并有效信息
    const old = mediaList[existIdx];
    old.referer = entry.referer || old.referer;
    old.userAgent = entry.userAgent || old.userAgent;
    old.cookie = entry.cookie || old.cookie;
    if (entry.contentLength) old.contentLength = entry.contentLength;
    if (entry.contentType) old.contentType = entry.contentType;
    await chrome.storage.local.set({ mediaList });
    return;
  }

  mediaList.unshift(entry);
  if (mediaList.length > MAX_ITEMS) {
    mediaList.length = MAX_ITEMS;
  }

  await chrome.storage.local.set({ mediaList });
  if (entry.tabId >= 0) {
    const tabCount = mediaList.filter((it) => it.tabId === entry.tabId).length;
    updateBadgeForTab(entry.tabId, tabCount);
  }
}

// 标签页专属角标更新（仅在对应标签页显示数字，避免全局常驻残留）
function updateBadgeForTab(tabId, count) {
  const text = count > 0 ? (count > 99 ? "99+" : String(count)) : "";
  if (tabId !== undefined && tabId !== null && tabId >= 0) {
    chrome.action.setBadgeText({ tabId, text });
    chrome.action.setBadgeBackgroundColor({ tabId, color: "#2563eb" });
  } else {
    chrome.action.setBadgeText({ text });
    chrome.action.setBadgeBackgroundColor({ color: "#2563eb" });
  }
}

// 标签页刷新或导航至新页面时：立即清除该标签页的旧角标，并清理旧网址嗅探数据
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === "loading") {
    chrome.action.setBadgeText({ tabId, text: "" });
    if (changeInfo.url) {
      const { mediaList = [] } = await chrome.storage.local.get("mediaList");
      const filtered = mediaList.filter((it) => it.tabId !== tabId);
      if (filtered.length !== mediaList.length) {
        await chrome.storage.local.set({ mediaList: filtered });
      }
    }
  }
});

// 标签页关闭时，释放其关联记录与角标
chrome.tabs.onRemoved.addListener(async (tabId) => {
  try {
    chrome.action.setBadgeText({ tabId, text: "" });
  } catch (e) {}
  const { mediaList = [] } = await chrome.storage.local.get("mediaList");
  const filtered = mediaList.filter((it) => it.tabId !== tabId);
  if (filtered.length !== mediaList.length) {
    await chrome.storage.local.set({ mediaList: filtered });
  }
});

// 存储列表全部清空时，同步清除全局残留角标
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.mediaList) {
    const list = changes.mediaList.newValue || [];
    if (list.length === 0) {
      chrome.action.setBadgeText({ text: "" });
    }
  }
});

// 深入解析 M3U8 清单内容 (提取分辨率、AES-128 密钥、总时长)
async function parseM3u8Metadata(entry) {
  const headers = {};
  if (entry.referer) headers["Referer"] = entry.referer;
  if (entry.userAgent) headers["User-Agent"] = entry.userAgent;

  let text = "";
  try {
    const res = await fetch(entry.url, { headers, credentials: "omit" });
    if (!res.ok) return;
    text = await res.text();
  } catch (e) {
    return;
  }

  let resolution = "";
  let duration = 0;
  let hasKey = false;
  let keyUrl = "";

  // 1. 匹配清晰度 RESOLUTION=1920x1080
  const resMatch = text.match(/RESOLUTION=(\d+x\d+)/i);
  if (resMatch) {
    resolution = resMatch[1];
  }

  // 2. 匹配加密密钥 #EXT-X-KEY:METHOD=AES-128,URI="https://..."
  const keyMatch = text.match(/#EXT-X-KEY:[^\r\n]*URI=["']?([^"'\r\n]+)["']?/i);
  if (keyMatch) {
    hasKey = true;
    try {
      keyUrl = new URL(keyMatch[1], entry.baseUrl || entry.url).href;
    } catch (e) {
      keyUrl = keyMatch[1];
    }
  }

  // 3. 计算切片总时长
  const durMatches = text.matchAll(/#EXTINF:([\d.]+)/g);
  for (const m of durMatches) {
    duration += parseFloat(m[1]) || 0;
  }

  if (resolution || duration > 0 || hasKey) {
    const { mediaList = [] } = await chrome.storage.local.get("mediaList");
    const item = mediaList.find((it) => it.id === entry.id);
    if (item) {
      if (resolution) item.resolution = resolution;
      if (duration > 0) item.duration = Math.round(duration);
      if (hasKey) {
        item.hasKey = true;
        item.keyUrl = keyUrl;
      }
      await chrome.storage.local.set({ mediaList });
    }
  }
}

// 4. 与本地桌面客户端通信
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req.action === "GET_MEDIA_FOR_TAB") {
    chrome.storage.local.get("mediaList", ({ mediaList = [] }) => {
      const tabId = sender.tab ? sender.tab.id : -1;
      const targetUrl = req.pageUrl || (sender.tab ? sender.tab.url : "");
      const matched = mediaList.filter(
        (it) => !it.url.startsWith("blob:") && (it.tabId === tabId || (targetUrl && it.pageUrl === targetUrl))
      );
      sendResponse({ media: matched });
    });
    return true;
  }

  if (req.action === "CLEAR_TAB_BADGE") {
    const tabId = req.tabId || (sender.tab ? sender.tab.id : -1);
    if (tabId >= 0) {
      chrome.action.setBadgeText({ tabId, text: "" });
    }
    chrome.action.setBadgeText({ text: "" });
    sendResponse({ success: true });
    return true;
  }

  if (req.action === "SNIFFED_MEDIA" && req.data) {
    // 来自 content_script 的注入嗅探
    captureMediaRequest(
      {
        url: req.data.url,
        tabId: sender.tab ? sender.tab.id : -1,
        requestHeaders: []
      },
      null
    );
    sendResponse({ success: true });
    return true;
  }

  if (req.action === "CHECK_CLIENT_STATUS") {
    fetch(`${LOCAL_SERVER_URL}/api/status`, { method: "GET" })
      .then((r) => r.json())
      .then((data) => sendResponse({ online: true, data }))
      .catch(() => sendResponse({ online: false }));
    return true;
  }

  if (req.action === "DETECT_BROWSER_PROXY") {
    detectBrowserProxy()
      .then((info) => sendResponse(info))
      .catch(() => sendResponse({ mode: "system", proxyUrl: "", label: "跟随系统代理" }));
    return true;
  }

  if (req.action === "PUSH_TO_CLIENT" && req.data) {
    // 推送到本地客户端
    pushTaskToLocalClient(req.data)
      .then((res) => sendResponse(res))
      .catch((err) => sendResponse({ success: false, error: String(err) }));
    return true;
  }
});

function detectBrowserProxy() {
  return new Promise((resolve) => {
    try {
      if (chrome.proxy && chrome.proxy.settings) {
        chrome.proxy.settings.get({ incognito: false }, (config) => {
          if (chrome.runtime.lastError || !config || !config.value) {
            resolve({ mode: "system", proxyUrl: "", label: "系统/默认代理" });
            return;
          }
          const val = config.value;
          let mode = val.mode || "system";
          let proxyUrl = "";
          let label = "系统/默认代理";

          if (val.rules) {
            const p = val.rules.singleProxy || val.rules.proxyForHttps || val.rules.proxyForHttp;
            if (p && p.host) {
              const scheme = (p.scheme || "http").toLowerCase();
              proxyUrl = `${scheme}://${p.host}:${p.port}`;
              mode = "fixed_servers";
              label = `浏览器代理 (${proxyUrl})`;
            }
          } else if (val.pacScript && val.pacScript.url) {
            mode = "pac_script";
            label = `PAC 自动配置脚本 (${val.pacScript.url})`;
          } else if (mode === "direct") {
            label = "直连 (不使用代理)";
          } else if (mode === "system") {
            label = "跟随系统代理配置";
          }
          resolve({ mode, proxyUrl, label, raw: val });
        });
      } else {
        resolve({ mode: "system", proxyUrl: "", label: "跟随系统代理" });
      }
    } catch (e) {
      resolve({ mode: "system", proxyUrl: "", label: "跟随系统代理" });
    }
  });
}

async function pushTaskToLocalClient(taskData) {
  try {
    const resp = await fetch(`${LOCAL_SERVER_URL}/api/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(taskData)
    });
    if (resp.ok) {
      return await resp.json();
    }
  } catch (e) {
    // HTTP 服务未响应，退回 Native Messaging 尝试唤醒
    return new Promise((resolve) => {
      chrome.runtime.sendNativeMessage(
        "com.m3u8.sniffer",
        taskData,
        (response) => {
          if (chrome.runtime.lastError) {
            resolve({
              success: false,
              error: chrome.runtime.lastError.message
            });
          } else {
            resolve(response || { success: true });
          }
        }
      );
    });
  }
}

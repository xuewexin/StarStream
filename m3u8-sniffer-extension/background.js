// background.js - CatCatch Pro Sniffer Engine & IPC Bridge
// 专注抓取完整媒体流 (M3U8 / MPD / MP4 / 音频)，严格过滤海量无用切片，页面消失自动实时清理关联爬取视频
const MAX_ITEMS = 300;
const LOCAL_SERVER_URL = "http://127.0.0.1:18910";

// 支持的完整视音频与流媒体扩展名正则
const MEDIA_EXT_REGEX = /\.(m3u8|mpd|mp4|webm|flv|f4v|mkv|avi|mov|wmv|mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)/i;
// 流媒体清单（master / media playlist、DASH MPD）——永远不能被当成"分片"丢弃
const PLAYLIST_EXT_REGEX = /\.(m3u8|mpd)(\?|#|$)/i;
// 明确的切片扩展名
const SEGMENT_EXT_REGEX = /\.(ts|m4s|m4v|mp2t|cmfv|cmfa|vtt|srt|ass|key)(\?|#|$)/i;

// 针对抖音/快手/B站/小红书等短视频无后缀 CDN 流的智能识别正则
const SHORT_VIDEO_CDN_REGEX = /(douyinvod\.com|snssdk\.com|iesdouyin\.com|bilivideo\.(com|cn)|hdslb\.com|kwaicdn\.com|kwai\.net|xhscdn\.com|weibo\.com\/.*\.mp4)/i;

/**
 * 精确判断是否为碎片切片。
 * 旧版用 (part|seg|chunk|frag|slice) 做全路径模糊匹配，会把
 * .../hls/part_1080/master.m3u8、.../segment-list.m3u8 这类真正的清单误杀，
 * 这是"抓不到深层/高画质流"的元凶之一。
 */
function isFragmentUrl(url) {
  if (!url) return true;
  const clean = String(url).split('#')[0];
  if (PLAYLIST_EXT_REGEX.test(clean)) return false; // 清单优先放行
  if (SEGMENT_EXT_REGEX.test(clean)) return true;
  if (/(^|\/)(init\.mp4|init\.m4s)$/i.test(clean.split('?')[0])) return true;
  if (/(^|\/)(segment|chunk|frag|seg|part)[-_.]?\d+\.(ts|m4s|mp4|m4v)/i.test(clean)) return true;
  if (/\/stream\/segment\//i.test(clean)) return true;
  return false;
}

// 常见广告切片流与推广联盟正则识别
const AD_URL_REGEX = /((\/|\b)(ad|ads|adv|advert|union|guanggao|tyad|googleads|doubleclick|popads|vpaid|preroll|midroll|postroll|alicdn.*\/ad\/|gdt.*\/ad\/)(\/|\.|\?|$))|(\b(adjump|ad_video|video_ad|unionad)\b)/i;

// 黑名单过滤（过滤广告、统计追踪）
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
          customRegex: "",
          filterFragments: true,
          onlyLiveTabs: true
        }
      });
    }
  });
  purgeClosedTabsMedia();
});

// 浏览器启动时立即清理已关闭网页的残留爬取记录
chrome.runtime.onStartup.addListener(() => {
  purgeClosedTabsMedia();
});

// 串行队列保证存储读写原子性
let storageQueue = Promise.resolve();

// 1. 监听请求发起 (捕获 Referer, UA, Cookie, Authorization)
chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    const url = details.url;
    // 丢弃无真实活动网页依附的后台/孤立请求
    if (details.tabId === undefined || details.tabId === null || details.tabId < 0) return;
    if (BLACKLIST_REGEX.test(url)) return;
    if (isFragmentUrl(url)) return; // 严格过滤分片
    if (!MEDIA_EXT_REGEX.test(url) && !SHORT_VIDEO_CDN_REGEX.test(url)) return;

    captureMediaRequest(details, null);
  },
  { urls: ["*://*/*"] },
  // MV3 下 Cookie / Referer / User-Agent / Authorization 属于敏感头，
  // 不加 extraHeaders 一律读不到，导致防盗链站点下载与预览全部 403。
  ["requestHeaders", "extraHeaders"]
);

// 2. 监听响应头部 (通过 Content-Type 捕获无后缀视频流及文件大小)
chrome.webRequest.onHeadersReceived.addListener(
  (details) => {
    const url = details.url;
    // 丢弃无真实活动网页依附的后台/孤立请求
    if (details.tabId === undefined || details.tabId === null || details.tabId < 0) return;
    if (BLACKLIST_REGEX.test(url)) return;
    if (isFragmentUrl(url)) return; // 严格过滤分片

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

    // 过滤常见切片 MIME 类型 (video/mp2t 为 TS 切片, video/iso.segment 为 DASH 分片)
    if (contentType.includes("mp2t") || contentType.includes("segment")) {
      return;
    }

    const isMasterStream =
      contentType.includes("vnd.apple.mpegurl") ||
      contentType.includes("x-mpegurl") ||
      contentType.includes("dash+xml");

    const isCompleteMedia =
      (contentType.startsWith("video/") || contentType.startsWith("audio/")) &&
      !isFragmentUrl(url) &&
      (MEDIA_EXT_REGEX.test(url) || SHORT_VIDEO_CDN_REGEX.test(url) || contentLength > 1024 * 1024);

    if (isMasterStream || isCompleteMedia || MEDIA_EXT_REGEX.test(url) || SHORT_VIDEO_CDN_REGEX.test(url)) {
      captureMediaRequest(details, {
        contentType,
        contentLength,
        contentDisposition
      });
    }
  },
  { urls: ["*://*/*"] },
  ["responseHeaders", "extraHeaders"]
);

// 3. 核心嗅探记录处理
async function captureMediaRequest(details, respInfo) {
  const url = details.url;
  if (!url || url.startsWith("blob:") || url.startsWith("data:") || url.startsWith("chrome:")) {
    return; // 忽略内存对象与非网络资源
  }
  if (isFragmentUrl(url)) {
    return; // 坚决丢弃视频切片分片
  }

  const tabId = details.tabId;
  // 核心约束：只记录依附于真实开启页面的媒体
  if (tabId === undefined || tabId === null || tabId < 0) {
    return;
  }

  // 获取页面标题与网页 URL
  let pageTitle = "";
  let pageUrl = "";
  try {
    const tab = await chrome.tabs.get(tabId);
    pageTitle = tab.title || "";
    pageUrl = tab.url || "";
  } catch (e) {
    // 若标签页已不在（瞬间关闭），放弃记录
    return;
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
  // 深度扫描 / 页面注入上报时携带的补充头（优先级低于真实网络请求头）
  if (details.deepHeaders) {
    referer = referer || details.deepHeaders.referer || "";
    userAgent = userAgent || details.deepHeaders.userAgent || "";
    cookie = cookie || details.deepHeaders.cookie || "";
    authorization = authorization || details.deepHeaders.authorization || "";
  }

  // 防盗链兜底：若子请求未显式包含 Referer，自动使用当前标签页 URL 作为 Referer！
  if (!referer && pageUrl) {
    referer = pageUrl;
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

  const isAdByUrl = AD_URL_REGEX.test(url);
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
    frameId: typeof details.frameId === "number" ? details.frameId : 0,
    requestType: details.type || "",
    initiator: details.initiator || "",
    timestamp: Date.now(),
    duration: 0,
    resolution: "",
    hasKey: false,
    keyUrl: "",
    isAd: isAdByUrl,
    adReason: isAdByUrl ? "URL匹配广告特征" : "",
    isFeature: false
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
    anyEndsWith(u, [".mp4", ".flv", ".f4v", ".webm", ".mkv", ".avi", ".mov", ".wmv"]) ||
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
  // 清除可能遗留的 blob 伪协议地址与切片
  mediaList = mediaList.filter((item) => !item.url.startsWith("blob:") && !isFragmentUrl(item.url));

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

// 核心功能：标签页刷新、重新加载或导航离开时：立即清除旧网页爬取的视频并清除角标
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === "loading") {
    try {
      chrome.action.setBadgeText({ tabId, text: "" });
    } catch (e) {}

    // 无论是否带 url，只要网页重新 loading，即代表原页面内容发生刷新或替换
    const { mediaList = [] } = await chrome.storage.local.get("mediaList");
    const filtered = mediaList.filter((it) => it.tabId !== tabId);
    if (filtered.length !== mediaList.length) {
      await chrome.storage.local.set({ mediaList: filtered });
    }
  }
});

// 核心功能：标签页关闭时，立即彻底清除该页面爬取的所有视频记录，释放角标
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

// 定时与按需比对清理：自动核对当前浏览器中所有存活的标签页，彻底刷新抹除已不存在的孤儿页面记录
async function purgeClosedTabsMedia() {
  return new Promise((resolve) => {
    chrome.tabs.query({}, async (tabs) => {
      const openTabIds = new Set((tabs || []).map((t) => t.id));
      const { mediaList = [] } = await chrome.storage.local.get("mediaList");
      const filtered = mediaList.filter((it) => it.tabId && openTabIds.has(it.tabId));
      if (filtered.length !== mediaList.length) {
        await chrome.storage.local.set({ mediaList: filtered });
      }
      resolve(filtered);
    });
  });
}

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
  // 三级抓取：页面上下文(自带 Referer/Cookie 且 CDN 已对本页开放 CORS)
  //          → 桌面客户端本地代理 → service worker 直连
  const text = (await fetchPlaylistText(entry)) || "";
  if (!text.trim().startsWith("#EXTM3U")) return;
  const isMasterPlaylist = /#EXT-X-STREAM-INF/i.test(text);

  let resolution = "";
  let duration = 0;
  let hasKey = false;
  let keyUrl = "";

  // 1. 匹配清晰度 RESOLUTION=1920x1080
  const resMatch = text.match(/RESOLUTION=(\d+x\d+)/i);
  if (resMatch && !isMasterPlaylist) {
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
    const item = mediaList.find((it) => it.id === entry.id || it.url === entry.url);
    if (item) {
      if (resolution) item.resolution = resolution;
      if (duration > 0) item.duration = Math.round(duration);
      if (hasKey) {
        item.hasKey = true;
        item.keyUrl = keyUrl;
      }

      const hasEndlist = text.includes("#EXT-X-ENDLIST");
      // 广告识别 1: 必须有明确结束符且时长极短，或显式命中广告正则，避免误杀动态初始流
      if (hasEndlist && item.duration > 0 && item.duration <= 45 && (AD_URL_REGEX.test(item.url) || item.duration <= 25)) {
        item.isAd = true;
        item.adReason = `疑似片头广告切片 (${item.duration}秒)`;
      } else if (item.duration > 45) {
        item.isAd = false;
        item.adReason = "";
        item.isFeature = true;
      }

      // 广告识别 2: 同标签页动态对比判定 (若存在 >= 5 分钟的主流，短于 60 秒的判定为广告切片)
      const tabStreams = mediaList.filter((it) => it.tabId === item.tabId && it.duration > 0);
      const maxDur = Math.max(...tabStreams.map((it) => it.duration), 0);
      if (maxDur >= 300) {
        tabStreams.forEach((it) => {
          if (it.duration <= 60 && it.duration < maxDur / 4) {
            it.isAd = true;
            it.adReason = `同页面对比判定为广告切片 (${it.duration}秒 vs 正片 ${Math.round(maxDur / 60)}分钟)`;
            it.isFeature = false;
          } else if (it.duration === maxDur) {
            it.isFeature = true;
            it.isAd = false;
          }
        });
      }

      await chrome.storage.local.set({ mediaList });
    }
  }

  // 关键修复：master.m3u8 里列出的 1080p/720p 等所有子流，
  // 播放器只会请求其中一路，光靠 webRequest 永远抓不到其余画质。
  // 这里主动展开全部变体为独立可下载条目（并继承同一套防盗链头）。
  if (isMasterPlaylist) {
    await expandMasterVariants(entry, text);
  }
}

// ============ 深层清单抓取与全清晰度变体展开 ============

const PLAYLIST_TIMEOUT_MS = 12000;

function withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((resolve) => setTimeout(() => resolve(null), ms))
  ]);
}

/** 通道 1：在发起请求的页面帧(MAIN world)里 fetch，天然带页面 Referer / Cookie / UA */
async function fetchPlaylistViaPage(entry) {
  if (!chrome.scripting || !(entry.tabId >= 0)) return null;
  try {
    const target = { tabId: entry.tabId };
    if (typeof entry.frameId === "number") target.frameIds = [entry.frameId];
    const results = await withTimeout(
      chrome.scripting.executeScript({
        target,
        world: "MAIN",
        func: async (url) => {
          try {
            const r = await fetch(url, { credentials: "include", cache: "no-store" });
            if (!r.ok) return { ok: false, status: r.status };
            return { ok: true, text: (await r.text()).slice(0, 2000000) };
          } catch (e) {
            return { ok: false, error: String(e) };
          }
        },
        args: [entry.url]
      }),
      PLAYLIST_TIMEOUT_MS
    );
    const first = results && results[0] && results[0].result;
    if (first && first.ok && first.text && first.text.trim().startsWith("#EXTM3U")) {
      return first.text;
    }
  } catch (e) {}
  return null;
}

/** 通道 2：桌面客户端本地代理（无 CORS 限制，自动复用软件里的网络代理设置） */
async function fetchPlaylistViaClient(entry) {
  try {
    const qs = new URLSearchParams({ url: entry.url, raw: "1" });
    if (entry.referer) qs.set("referer", entry.referer);
    if (entry.userAgent) qs.set("ua", entry.userAgent);
    if (entry.cookie) qs.set("cookie", entry.cookie);
    const res = await withTimeout(
      fetch(`${LOCAL_SERVER_URL}/api/stream?${qs.toString()}`),
      PLAYLIST_TIMEOUT_MS
    );
    if (!res || !res.ok) return null;
    const text = await res.text();
    return text.trim().startsWith("#EXTM3U") ? text : null;
  } catch (e) {
    return null;
  }
}

/** 通道 3：service worker 直连（旧逻辑，仅作最后兜底） */
async function fetchPlaylistViaWorker(entry) {
  try {
    const headers = {};
    if (entry.referer) headers["Referer"] = entry.referer;
    if (entry.userAgent) headers["User-Agent"] = entry.userAgent;
    if (entry.cookie) headers["Cookie"] = entry.cookie;
    const res = await withTimeout(
      fetch(entry.url, { headers, credentials: "omit" }),
      PLAYLIST_TIMEOUT_MS
    );
    if (!res || !res.ok) return null;
    return await res.text();
  } catch (e) {
    return null;
  }
}

async function fetchPlaylistText(entry) {
  return (
    (await fetchPlaylistViaPage(entry)) ||
    (await fetchPlaylistViaClient(entry)) ||
    (await fetchPlaylistViaWorker(entry))
  );
}

function makeBaseUrl(url) {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/");
    parts.pop();
    return u.origin + parts.join("/") + "/";
  } catch (e) {
    return url.substring(0, url.lastIndexOf("/") + 1);
  }
}

/**
 * 把 master playlist 内所有 #EXT-X-STREAM-INF 变体展开成独立条目。
 * 例如播放器只加载了 720p，这里仍能列出 1080p / 480p 供直接下载。
 */
async function expandMasterVariants(master, text) {
  const lines = text.split(/\r?\n/);
  const variants = [];
  let pending = null;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (/^#EXT-X-STREAM-INF:/i.test(line)) {
      pending = line;
      continue;
    }
    if (line.startsWith("#")) {
      // 独立音轨 / 字幕轨: #EXT-X-MEDIA:TYPE=AUDIO,...,URI="..."
      if (/^#EXT-X-MEDIA:/i.test(line)) {
        const m = line.match(/URI="([^"]+)"/i);
        if (m) variants.push({ uri: m[1], info: line, audioOnly: /TYPE=AUDIO/i.test(line) });
      }
      continue;
    }
    if (pending) {
      variants.push({ uri: line, info: pending, audioOnly: false });
      pending = null;
    }
  }
  if (!variants.length) return 0;

  const { mediaList = [] } = await chrome.storage.local.get("mediaList");
  const newEntries = [];
  const resolutionLabels = [];

  for (const v of variants) {
    let abs;
    try {
      abs = new URL(v.uri, master.url).href;
    } catch (e) {
      continue;
    }
    if (isFragmentUrl(abs) || mediaList.some((it) => it.url === abs)) continue;

    const rm = v.info.match(/RESOLUTION=(\d+)x(\d+)/i);
    const bm = v.info.match(/BANDWIDTH=(\d+)/i);
    const nm = v.info.match(/NAME="([^"]+)"/i);
    const height = rm ? parseInt(rm[2], 10) : 0;
    const label = height ? `${height}P` : (nm ? nm[1] : (bm ? `${Math.round(parseInt(bm[1], 10) / 1000)}kbps` : ""));
    if (height) resolutionLabels.push(`${height}P`);

    const e = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
      url: abs,
      tabId: master.tabId,
      frameId: master.frameId || 0,
      pageTitle: master.pageTitle,
      pageUrl: master.pageUrl,
      mediaType: v.audioOnly ? "audio" : "m3u8",
      referer: master.referer || master.pageUrl || "",
      userAgent: master.userAgent || "",
      cookie: master.cookie || "",
      authorization: master.authorization || "",
      baseUrl: makeBaseUrl(abs),
      contentType: "",
      contentLength: 0,
      timestamp: Date.now(),
      duration: 0,
      resolution: rm ? `${rm[1]}x${rm[2]}` : "",
      bandwidth: bm ? parseInt(bm[1], 10) : 0,
      variantLabel: label,
      isVariant: true,
      masterUrl: master.url,
      hasKey: false,
      keyUrl: "",
      isAd: false,
      adReason: "",
      isFeature: false,
      sourceType: "master_variant"
    };
    mediaList.unshift(e);
    newEntries.push(e);
  }

  const masterItem = mediaList.find((it) => it.url === master.url && it.tabId === master.tabId);
  if (masterItem) {
    masterItem.isMaster = true;
    masterItem.variantCount = variants.length;
    masterItem.variantResolutions = [...new Set(resolutionLabels)].sort((a, b) => parseInt(b) - parseInt(a));
    masterItem.resolution = masterItem.variantResolutions[0] || masterItem.resolution || "";
  }

  if (mediaList.length > MAX_ITEMS) mediaList.length = MAX_ITEMS;
  await chrome.storage.local.set({ mediaList });
  if (master.tabId >= 0) {
    updateBadgeForTab(master.tabId, mediaList.filter((it) => it.tabId === master.tabId).length);
  }

  // 异步补齐每个变体的时长 / 加密信息；media playlist 不含 STREAM-INF，不会递归展开
  newEntries.forEach((e) => {
    if (e.mediaType === "m3u8") parseM3u8Metadata(e).catch(() => {});
  });
  return newEntries.length;
}

// 4. 与本地桌面客户端通信
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req.action === "PURGE_CLOSED_TABS") {
    purgeClosedTabsMedia().then((cleanedList) => sendResponse({ success: true, count: cleanedList.length }));
    return true;
  }

  if (req.action === "GET_MEDIA_FOR_TAB") {
    purgeClosedTabsMedia().then(async (mediaList) => {
      const tabId = sender.tab ? sender.tab.id : -1;
      let topTab = null;
      if (tabId >= 0) {
        try {
          topTab = await chrome.tabs.get(tabId);
        } catch (e) {}
      }
      const targetUrl = req.pageUrl || (topTab ? topTab.url : (sender.tab ? sender.tab.url : ""));
      const matched = mediaList.filter(
        (it) => !it.url.startsWith("blob:") && (it.tabId === tabId || (targetUrl && it.pageUrl === targetUrl))
      );
      sendResponse({
        media: matched,
        tabTitle: topTab ? topTab.title : (sender.tab ? sender.tab.title : ""),
        tabUrl: topTab ? topTab.url : (sender.tab ? sender.tab.url : "")
      });
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

  if (req.action === "UPDATE_MEDIA_METADATA" && req.data) {
    const dur = Number(req.data.duration) || 0;
    const res = req.data.resolution || "";
    const tabId = sender.tab ? sender.tab.id : -1;
    if (tabId >= 0 && (dur > 0 || res)) {
      chrome.storage.local.get("mediaList").then(async ({ mediaList = [] }) => {
        let changed = false;
        mediaList.forEach((it) => {
          if (it.tabId === tabId && (it.mediaType === "m3u8" || it.url === req.data.videoSrc)) {
            if (dur > 0 && dur > (it.duration || 0)) {
              it.duration = dur;
              changed = true;
              if (dur > 45) {
                it.isAd = false;
                it.adReason = "";
                it.isFeature = true;
              }
            }
            if (res && (!it.resolution || it.resolution === "高清流" || it.resolution === "高清")) {
              it.resolution = res;
              changed = true;
            }
          }
        });
        if (changed) {
          await chrome.storage.local.set({ mediaList });
        }
      });
    }
    sendResponse({ success: true });
    return true;
  }

  if (req.action === "SNIFFED_MEDIA" && req.data) {
    // 来自 content_script / inject.js 的注入嗅探
    if (!isFragmentUrl(req.data.url)) {
      captureMediaRequest(
        {
          url: req.data.url,
          tabId: sender.tab ? sender.tab.id : -1,
          frameId: typeof sender.frameId === "number" ? sender.frameId : 0,
          requestHeaders: [],
          deepHeaders: {
            referer: req.data.referer || req.data.pageUrl || "",
            userAgent: req.data.userAgent || "",
            cookie: req.data.cookie || ""
          }
        },
        null
      );
    }
    sendResponse({ success: true });
    return true;
  }

  if (req.action === "ENSURE_MAIN_INJECT") {
    const tabId = sender.tab ? sender.tab.id : -1;
    const frameId = typeof sender.frameId === "number" ? sender.frameId : 0;
    if (tabId >= 0 && chrome.scripting) {
      chrome.scripting.executeScript({
        target: { tabId, frameIds: [frameId] },
        world: "MAIN",
        files: ["inject.js"]
      }).then(() => sendResponse({ success: true }))
        .catch((e) => sendResponse({ success: false, error: String(e) }));
      return true;
    }
    sendResponse({ success: false, error: "tab 不可用" });
    return true;
  }

  if (req.action === "DEEP_FOUND_MEDIA" && req.data && Array.isArray(req.data.urls)) {
    // 页面源码 / JS 变量 / API 响应 / iframe 的深度扫描结果
    const tabId = sender.tab ? sender.tab.id : -1;
    const deepHeaders = {
      referer: req.data.pageUrl || "",
      userAgent: req.data.userAgent || "",
      cookie: req.data.cookie || ""
    };
    req.data.urls.slice(0, 80).forEach((u) => {
      if (!u || isFragmentUrl(u)) return;
      captureMediaRequest(
        {
          url: u,
          tabId,
          frameId: typeof sender.frameId === "number" ? sender.frameId : 0,
          requestHeaders: [],
          deepHeaders
        },
        null
      );
    });
    sendResponse({ success: true, count: req.data.urls.length });
    return true;
  }

  if (req.action === "INJECT_HLS_PLAYER" && req.data) {
    injectInlineHlsPlayer(req.data.tabId ?? (sender.tab ? sender.tab.id : -1), req.data)
      .then((res) => sendResponse(res))
      .catch((e) => sendResponse({ success: false, error: String(e) }));
    return true;
  }

  if (req.action === "GET_TAB_INFO") {
    const tabId = sender.tab ? sender.tab.id : -1;
    if (tabId >= 0) {
      chrome.tabs.get(tabId).then((tab) => {
        sendResponse({ title: tab?.title || "", url: tab?.url || "" });
      }).catch(() => {
        sendResponse({ title: sender.tab?.title || "", url: sender.tab?.url || "" });
      });
    } else {
      sendResponse({ title: sender.tab?.title || "", url: sender.tab?.url || "" });
    }
    return true;
  }

  if (req.action === "CHECK_CLIENT_STATUS") {
    fetch(`${LOCAL_SERVER_URL}/api/status`, { method: "GET" })
      .then((r) => r.json())
      .then((data) => {
        if (data && data.language) {
          chrome.storage.local.set({ extension_language: data.language });
        }
        sendResponse({ online: true, data });
      })
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
    const browserProxy = await detectBrowserProxy();
    const fillProxy = (item) => {
      if (!item.proxy || item.proxy === 'auto') {
        if (browserProxy && browserProxy.proxyUrl) {
          item.proxy = browserProxy.proxyUrl;
        } else if (browserProxy && browserProxy.mode === 'direct') {
          item.proxy = 'direct';
        } else {
          item.proxy = 'auto';
        }
      }
      if (!item.headers) item.headers = {};
      if (!item.headers.Referer && (item.referer || item.pageUrl)) {
        item.headers.Referer = item.referer || item.pageUrl;
      }
      if (item.headers.Referer && !item.headers.Origin) {
        try {
          const u = new URL(item.headers.Referer);
          item.headers.Origin = u.origin;
        } catch (e) {}
      }
    };
    if (Array.isArray(taskData)) {
      taskData.forEach(fillProxy);
    } else if (taskData && typeof taskData === 'object') {
      fillProxy(taskData);
    }
  } catch (e) {}

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

// 自动检测客户端语言变化并向扩展内所有页面分发同步
function syncClientLanguage() {
  fetch(`${LOCAL_SERVER_URL}/api/status`, { method: "GET" })
    .then((r) => r.json())
    .then((data) => {
      if (data && data.language) {
        chrome.storage.local.get(["extension_language"], (res) => {
          if (!res || res.extension_language !== data.language) {
            chrome.storage.local.set({ extension_language: data.language });
          }
        });
      }
    })
    .catch(() => {});
}
setInterval(syncClientLanguage, 15000);
syncClientLanguage();

/**
 * 客户端离线时的在线预览兜底：把 hls.js 播放器直接注入目标网页。
 * 页面上下文发起的请求自带页面 Referer / Cookie，且 CDN 本来就对该 origin 开放，
 * 比从 chrome-extension:// 的 popup 里跨域直连可靠得多。
 */
async function injectInlineHlsPlayer(tabId, item) {
  if (!(tabId >= 0)) return { success: false, error: "目标页面已关闭" };
  const isM3u8 = item.mediaType === "m3u8" || /\.m3u8(\?|$)/i.test(item.url);

  try {
    if (isM3u8) {
      await chrome.scripting.executeScript({
        target: { tabId },
        world: "MAIN",
        files: ["popup/hls.min.js"]
      });
    }

    await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: (cfg) => {
        const OLD_ID = "__starstream_inline_preview__";
        const old = document.getElementById(OLD_ID);
        if (old) old.remove();

        const box = document.createElement("div");
        box.id = OLD_ID;
        box.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.93);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;box-sizing:border-box;";

        const bar = document.createElement("div");
        bar.style.cssText = "width:min(960px,96vw);display:flex;justify-content:space-between;align-items:center;gap:12px;color:#e4e4e7;font:14px/1.4 system-ui,sans-serif;margin-bottom:10px;";

        const title = document.createElement("span");
        title.style.cssText = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
        title.textContent = "星流在线预览 · " + (cfg.title || "视频流");

        const close = document.createElement("button");
        close.textContent = "✕ 关闭";
        close.style.cssText = "flex:none;background:#27272a;color:#f4f4f5;border:1px solid #3f3f46;border-radius:6px;padding:6px 12px;cursor:pointer;font-size:13px;";

        bar.appendChild(title);
        bar.appendChild(close);

        const video = document.createElement("video");
        video.controls = true;
        video.autoplay = true;
        video.style.cssText = "width:min(960px,96vw);max-height:76vh;background:#000;border-radius:8px;";

        const status = document.createElement("div");
        status.style.cssText = "width:min(960px,96vw);color:#a1a1aa;font:12px/1.5 system-ui,sans-serif;margin-top:8px;word-break:break-all;";
        status.textContent = cfg.isM3u8
          ? "正在通过网页上下文加载 HLS 流（自动携带本站 Referer / Cookie）…"
          : "正在加载媒体直链…";

        box.appendChild(bar);
        box.appendChild(video);
        box.appendChild(status);
        (document.body || document.documentElement).appendChild(box);

        let hls = null;
        if (cfg.isM3u8 && window.Hls && window.Hls.isSupported()) {
          hls = new window.Hls({ enableWorker: true, lowLatencyMode: false });
          hls.loadSource(cfg.url);
          hls.attachMedia(video);
          hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
            status.textContent = "清单解析成功，正在起播…";
            video.play().catch(() => {});
          });
          hls.on(window.Hls.Events.ERROR, (evt, data) => {
            if (data && data.fatal) {
              status.textContent = "播放失败：" + (data.type || "") + " / " + (data.details || "") +
                "（若仍失败，请启动星流桌面客户端后使用代理预览）";
            }
          });
        } else if (cfg.isM3u8 && video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = cfg.url;
          video.play().catch(() => {});
        } else if (cfg.isM3u8) {
          status.textContent = "当前页面无法加载 hls.js，请启动星流桌面客户端后重试代理预览。";
        } else {
          video.src = cfg.url;
          video.play().catch(() => {});
        }

        close.onclick = () => {
          try { if (hls) hls.destroy(); } catch (e) {}
          try { video.pause(); } catch (e) {}
          box.remove();
        };
      },
      args: [{
        url: item.url,
        title: item.pageTitle || item.title || "",
        isM3u8
      }]
    });

    return { success: true };
  } catch (e) {
    return { success: false, error: String(e) };
  }
}

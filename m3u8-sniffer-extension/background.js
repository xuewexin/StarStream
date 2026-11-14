// background.js - CatCatch Pro Sniffer Engine & IPC Bridge
// 专注抓取完整媒体流 (M3U8 / MPD / MP4 / 音频)，严格过滤海量无用切片，页面消失自动实时清理关联爬取视频
const MAX_ITEMS = 150;
const LOCAL_SERVER_URL = "http://127.0.0.1:18910";

/**
 * 访问本地客户端：在 127.0.0.1 / localhost 之间快速尝试，带超时保护
 */
async function localFetch(path, options = {}, timeoutMs = 3500) {
  const targets = [LOCAL_SERVER_URL, LOCAL_SERVER_URL.replace("127.0.0.1", "localhost")];
  let lastErr = null;
  for (const base of targets) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(`${base}${path}`, { cache: "no-store", ...options, signal: controller.signal });
      clearTimeout(timer);
      return res;
    } catch (e) {
      clearTimeout(timer);
      lastErr = e;
    }
  }
  throw lastErr || new Error("local server unreachable");
}

// 支持的完整视音频与流媒体扩展名正则
const MEDIA_EXT_REGEX = /\.(m3u8|mpd|mp4|webm|flv|f4v|mkv|avi|mov|wmv|mp3|m4a|aac|wav|ogg|flac|opus)(\?|#|$)/i;
// 流媒体清单（master / media playlist、DASH MPD）——永远放行
const PLAYLIST_EXT_REGEX = /\.(m3u8|mpd)(\?|#|$)/i;
// 明确的分片扩展名
const SEGMENT_EXT_REGEX = /\.(ts|m4s|m4v|mp2t|cmfv|cmfa|vtt|srt|ass|key)(\?|#|$)/i;

// 针对抖音/快手/B站/小红书等短视频无后缀 CDN 流的智能识别正则
const SHORT_VIDEO_CDN_REGEX = /(douyinvod\.com|snssdk\.com|iesdouyin\.com|bilivideo\.(com|cn)|hdslb\.com|kwaicdn\.com|kwai\.net|xhscdn\.com|weibo\.com\/.*\.mp4)/i;

/**
 * 精确判断是否为碎片切片
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
    if (details.tabId === undefined || details.tabId === null || details.tabId < 0) return;
    if (BLACKLIST_REGEX.test(url)) return;
    if (isFragmentUrl(url)) return; // 严格过滤分片
    if (!MEDIA_EXT_REGEX.test(url) && !SHORT_VIDEO_CDN_REGEX.test(url)) return;

    captureMediaRequest(details, null);
  },
  { urls: ["*://*/*"] },
  ["requestHeaders", "extraHeaders"]
);

// 2. 监听响应头部 (通过 Content-Type 捕获无后缀视频流及文件大小)
chrome.webRequest.onHeadersReceived.addListener(
  (details) => {
    const url = details.url;
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
      contentType.includes("mpegurl") ||
      contentType.includes("dash+xml");

    const isCompleteMedia =
      (contentType.startsWith("video/") || contentType.startsWith("audio/")) &&
      !isFragmentUrl(url);

    const isOctetStreamMedia =
      (contentType.includes("octet-stream") || contentType.includes("binary")) &&
      (PLAYLIST_EXT_REGEX.test(url) || MEDIA_EXT_REGEX.test(url));

    if (isMasterStream || isCompleteMedia || isOctetStreamMedia || MEDIA_EXT_REGEX.test(url) || SHORT_VIDEO_CDN_REGEX.test(url)) {
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
    return;
  }
  if (isFragmentUrl(url)) {
    return;
  }

  let tabId = details.tabId;
  let pageTitle = details.pageTitle || "";
  let pageUrl = details.pageUrl || "";

  if (tabId === undefined || tabId === null || tabId < 0) {
    try {
      const activeTabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (activeTabs && activeTabs[0]) {
        tabId = activeTabs[0].id;
        pageTitle = pageTitle || activeTabs[0].title || "";
        pageUrl = pageUrl || activeTabs[0].url || "";
      }
    } catch (e) {}
  } else {
    try {
      const tab = await chrome.tabs.get(tabId);
      if (tab) {
        pageTitle = pageTitle || tab.title || "";
        pageUrl = pageUrl || tab.url || "";
      }
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
  if (details.deepHeaders) {
    if (!referer) referer = details.deepHeaders.referer || "";
    if (!userAgent) userAgent = details.deepHeaders.userAgent || "";
    if (!cookie) cookie = details.deepHeaders.cookie || "";
  }

  // 防盗链兜底：若子请求未显式包含 Referer，自动使用当前标签页 URL 作为 Referer！
  if (!referer && pageUrl) {
    referer = pageUrl;
  }

  const mediaType = detectMediaType(url, respInfo ? respInfo.contentType : "");

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
    resolution: extractQualityFromUrl(url),
    hasKey: false,
    keyUrl: "",
    isAd: isAdByUrl,
    adReason: isAdByUrl ? "URL匹配广告特征" : "",
    isFeature: false,
    isMaster: false
  };

  storageQueue = storageQueue.then(() => insertIntoStorage(entry)).catch(() => {});
  await storageQueue;

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
    contentType.startsWith("video/") ||
    SHORT_VIDEO_CDN_REGEX.test(url)
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

/**
 * 从地址里提取真实画质（/720p/video.m3u8、xxx_1080p.m3u8、4k 等）。
 * 地址里的画质标签比播放器渲染尺寸可靠得多——播放器窗口小的时候
 * videoHeight 只有 360，会把 720P/1080P 的流错误标成 360P。
 */
function extractQualityFromUrl(url) {
  const u = String(url || "");
  const m = u.match(/(?:^|[\/_.-])(\d{3,4})p(?:[\/_.-]|$)/i);
  if (m) {
    const h = parseInt(m[1], 10);
    if (h >= 144 && h <= 4320) return `${h}P`;
  }
  if (/(?:^|[\/_.-])(4k|2160p?)(?:[\/_.-]|$)/i.test(u)) return "2160P";
  if (/(?:^|[\/_.-])2k(?:[\/_.-]|$)/i.test(u)) return "1440P";
  return "";
}

// 插入存储并去重
async function insertIntoStorage(entry) {
  let { mediaList = [] } = await chrome.storage.local.get("mediaList");
  mediaList = mediaList.filter((item) => !item.url.startsWith("blob:") && !isFragmentUrl(item.url));

  const existIdx = mediaList.findIndex((item) => item.url === entry.url);
  if (existIdx >= 0) {
    const old = mediaList[existIdx];
    old.referer = entry.referer || old.referer;
    old.userAgent = entry.userAgent || old.userAgent;
    old.cookie = entry.cookie || old.cookie;
    if (entry.contentLength) old.contentLength = entry.contentLength;
    if (entry.contentType) {
      old.contentType = entry.contentType;
      if (old.mediaType === "other" || !old.mediaType) {
        old.mediaType = detectMediaType(old.url, entry.contentType);
      }
    }
    if (entry.mediaType && entry.mediaType !== "other") {
      old.mediaType = entry.mediaType;
    }
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

// 标签页真正导航离开当前网站时才清理旧记录（绝不因 status: loading、广告加载或局部刷新而误删视频）
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
  if (changeInfo.url) {
    try {
      const newUrl = new URL(changeInfo.url);
      const { mediaList = [] } = await chrome.storage.local.get("mediaList");
      const tabItems = mediaList.filter((it) => it.tabId === tabId);
      if (tabItems.length > 0) {
        const prevPage = tabItems[0].pageUrl;
        if (prevPage) {
          try {
            const oldUrl = new URL(prevPage);
            // 只有顶级域名完全改变时，才清理该标签页的历史记录
            if (oldUrl.host !== newUrl.host) {
              const filtered = mediaList.filter((it) => it.tabId !== tabId);
              await chrome.storage.local.set({ mediaList: filtered });
              chrome.action.setBadgeText({ tabId, text: "" });
            }
          } catch (e) {}
        }
      }
    } catch (e) {}
  }
});

// 标签页关闭时清除记录
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

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.mediaList) {
    const list = changes.mediaList.newValue || [];
    if (list.length === 0) {
      chrome.action.setBadgeText({ text: "" });
    }
  }
});

// 深入解析 M3U8 清单内容 (精确提取分辨率、AES-128 密钥、总时长及主清单特征)
async function parseM3u8Metadata(entry) {
  let text = "";
  try {
    const headers = {};
    if (entry.referer) headers["Referer"] = entry.referer;
    if (entry.userAgent) headers["User-Agent"] = entry.userAgent;
    if (entry.cookie) headers["Cookie"] = entry.cookie;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(entry.url, { headers, credentials: "omit", signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) return;
    text = await res.text();
  } catch (e) {
    return;
  }
  if (!text || !text.trim().startsWith("#EXTM3U")) return;

  const isMasterPlaylist = /#EXT-X-STREAM-INF/i.test(text);
  let resolution = "";
  let duration = 0;
  let hasKey = false;
  let keyUrl = "";
  let direct1080Url = "";

  if (isMasterPlaylist) {
    // 主清单 (Master Playlist)：解析内部各画质变体，提取最高画质
    const resMatches = [...text.matchAll(/RESOLUTION=(\d+x\d+)/gi)];
    if (resMatches.length > 0) {
      let maxHeight = 0;
      let bestRes = "";
      for (const m of resMatches) {
        const parts = m[1].split('x');
        const h = parseInt(parts[1], 10) || 0;
        if (h > maxHeight) {
          maxHeight = h;
          bestRes = m[1];
        }
      }
      resolution = bestRes || resMatches[0][1];
    } else {
      resolution = "最高画质";
    }

    // 检查是否存在 1080p 子清单相对地址
    const lines = text.split(/\r?\n/);
    let pendingInf = "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("#EXT-X-STREAM-INF")) {
        pendingInf = trimmed;
      } else if (pendingInf && trimmed && !trimmed.startsWith("#")) {
        if (/1920x1080|1080/i.test(pendingInf) || /1080p/i.test(trimmed)) {
          try {
            direct1080Url = new URL(trimmed, entry.url).href;
          } catch (e) {}
        }
        pendingInf = "";
      }
    }
  } else {
    // 媒体子清单：提取分辨率
    const resMatch = text.match(/RESOLUTION=(\d+x\d+)/i);
    if (resMatch) {
      resolution = resMatch[1];
    }
  }

  // 匹配加密密钥 #EXT-X-KEY:METHOD=AES-128,URI="https://..."
  const keyMatch = text.match(/#EXT-X-KEY:[^\r\n]*URI=["']?([^"'\r\n]+)["']?/i);
  if (keyMatch) {
    hasKey = true;
    try {
      keyUrl = new URL(keyMatch[1], entry.baseUrl || entry.url).href;
    } catch (e) {
      keyUrl = keyMatch[1];
    }
  }

  // 计算切片总时长
  const durMatches = text.matchAll(/#EXTINF:([\d.]+)/g);
  for (const m of durMatches) {
    duration += parseFloat(m[1]) || 0;
  }

  const { mediaList = [] } = await chrome.storage.local.get("mediaList");
  const item = mediaList.find((it) => it.id === entry.id || it.url === entry.url);
  const hasEndlist = text.includes("#EXT-X-ENDLIST");
  if (item) {
    if (resolution) item.resolution = resolution;
    if (isMasterPlaylist) {
      item.isMaster = true;
      item.isFeature = true;
      item.isAd = false;
      if (direct1080Url) item.direct1080Url = direct1080Url;
      // 不再从同标签页随便找一个有 duration 的条目来"继承"：
      // 同一页面可能同时存在 6 秒预告片和 3 小时正片，继承会把短片段撑成数小时。
      // 真实时长交给播放器的 UPDATE_MEDIA_METADATA（按 streamUrl 精确绑定）补齐。
    } else if (duration > 0) {
      const playlistDur = Math.round(duration);
      if (!hasEndlist) {
        // 直播式清单（无 ENDLIST）这里只是当前滑动窗口的时长，
        // 绝不能拿它覆盖播放器报出的真实总时长，否则会出现「1:57:22 变成 0:06」
        if (!item.duration) item.duration = playlistDur;
        item.isLive = true;
      } else if (playlistDur > (item.duration || 0)) {
        // 点播清单：仅用更长的清单总时长补齐，绝不缩短已有真实时长
        item.duration = playlistDur;
      }
      // 只回写"自己所属"的 master（通过 masterUrl 精确匹配），
      // 不再随便挑同标签页的 master，避免把某条流的时长写到别的视频上
      if (item.masterUrl) {
        const ownMaster = mediaList.find((it) => it.tabId === item.tabId && it.url === item.masterUrl);
        if (ownMaster && playlistDur > (ownMaster.duration || 0)) {
          ownMaster.duration = playlistDur;
        }
      }
    }

    if (hasKey) {
      item.hasKey = true;
      item.keyUrl = keyUrl;
    }

    if (hasEndlist && item.duration > 0 && item.duration <= 45 && (AD_URL_REGEX.test(item.url) || item.duration <= 25)) {
      item.isAd = true;
      item.adReason = `疑似片头广告切片 (${item.duration}秒)`;
    } else if (item.duration > 45 || item.isMaster) {
      item.isAd = false;
      item.adReason = "";
      item.isFeature = true;
    }

    // 同标签页动态对比判定
    const tabStreams = mediaList.filter((it) => it.tabId === item.tabId && it.duration > 0);
    const maxDur = Math.max(...tabStreams.map((it) => it.duration), 0);
    if (maxDur >= 300) {
      tabStreams.forEach((it) => {
        if (!it.isMaster && it.duration <= 60 && it.duration < maxDur / 4) {
          it.isAd = true;
          it.adReason = `同页面对比判定为广告切片 (${it.duration}秒 vs 正片 ${Math.round(maxDur / 60)}分钟)`;
          it.isFeature = false;
        } else if (it.duration === maxDur || it.isMaster) {
          it.isFeature = true;
          it.isAd = false;
        }
      });
    }

    await chrome.storage.local.set({ mediaList });
  }
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
    // 直播播放器的 duration 可能是 Infinity，直接入库会变成 null 或污染排序
    const rawDur = Number(req.data.duration);
    const dur = Number.isFinite(rawDur) && rawDur > 0 ? Math.floor(rawDur) : 0;
    const res = req.data.resolution || "";
    const streamUrl = req.data.streamUrl || "";
    const tabId = sender.tab ? sender.tab.id : -1;
    if (tabId >= 0 && (dur > 0 || res)) {
      chrome.storage.local.get("mediaList").then(async ({ mediaList = [] }) => {
        let changed = false;
        mediaList.forEach((it) => {
          if (it.tabId !== tabId) return;

          // 有精确的流地址时只更新这一条（以及它的 master 展开项），
          // 绝不能把播放器时长/尺寸写给它旁边的 6 秒广告切片
          let targeted = false;
          if (streamUrl) {
            targeted = it.url === streamUrl || it.masterUrl === streamUrl || it.url === req.data.videoSrc;
            if (!targeted) return;
          } else if (it.mediaType !== "m3u8" && it.url !== req.data.videoSrc) {
            return;
          }

          const known = Number(it.duration) || 0;
          if (dur > 0) {
            if (targeted) {
              // 已精确绑定到该视频，播放器时长是权威值，允许双向校正
              if (Math.abs(known - dur) > 2) {
                it.duration = dur;
                changed = true;
              }
            } else if (known === 0 || dur <= known * 1.2 + 5) {
              // 未精确绑定时只允许补空或小幅刷新，避免把短切片拉长成整片时长
              if (dur > known) {
                it.duration = dur;
                changed = true;
              }
            }
            if (Number(it.duration) > 45) {
              it.isAd = false;
              it.adReason = "";
              it.isFeature = true;
            }
          }

          // 画质：地址里带 /720p/ 这类标签时以地址为准，
          // 播放器渲染尺寸只用于完全无法判断画质的流
          if (res && !extractQualityFromUrl(it.url) &&
              (!it.resolution || it.resolution === "高清流" || it.resolution === "高清")) {
            it.resolution = res;
            changed = true;
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
    sendResponse({ success: false, error: "tab unavailable" });
    return true;
  }

  if (req.action === "SET_PREVIEW_HEADERS" && req.data) {
    const referer = req.data.referer || req.data.pageUrl || "";
    let origin = "";
    if (referer) {
      try { origin = new URL(referer).origin; } catch (e) {}
    }
    const headers = [
      { header: "Referer", operation: "set", value: referer },
      { header: "User-Agent", operation: "set", value: req.data.userAgent || navigator.userAgent }
    ];
    if (origin) {
      headers.push({ header: "Origin", operation: "set", value: origin });
    }
    if (req.data.cookie) {
      headers.push({ header: "Cookie", operation: "set", value: req.data.cookie });
    }
    if (chrome.declarativeNetRequest && chrome.declarativeNetRequest.updateSessionRules) {
      chrome.declarativeNetRequest.updateSessionRules({
        removeRuleIds: [20001],
        addRules: [{
          id: 20001,
          priority: 100,
          action: {
            type: "modifyHeaders",
            requestHeaders: headers
          },
          condition: {
            resourceTypes: ["xmlhttprequest", "media", "image", "other"],
            initiatorDomains: [chrome.runtime.id]
          }
        }]
      }).then(() => sendResponse({ success: true }))
        .catch((e) => sendResponse({ success: false, error: String(e) }));
      return true;
    }
    sendResponse({ success: false, error: "declarativeNetRequest unavailable" });
    return true;
  }

  if (req.action === "CLEAR_PREVIEW_HEADERS") {
    if (chrome.declarativeNetRequest && chrome.declarativeNetRequest.updateSessionRules) {
      chrome.declarativeNetRequest.updateSessionRules({
        removeRuleIds: [20001]
      }).then(() => sendResponse({ success: true }))
        .catch((e) => sendResponse({ success: false, error: String(e) }));
      return true;
    }
    sendResponse({ success: true });
    return true;
  }

  if (req.action === "CHECK_CLIENT_STATUS") {
    localFetch("/api/status", { method: "GET" }, 2500)
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
            resolve({ mode: "system", proxyUrl: "", label: "跟随系统代理" });
            return;
          }
          const val = config.value;
          let mode = val.mode || "system";
          let proxyUrl = "";
          let label = "跟随系统代理";

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
      if (!item.proxy || item.proxy === 'auto' || item.proxy === 'browser') {
        if (browserProxy && browserProxy.proxyUrl) {
          item.proxy = browserProxy.proxyUrl;
        } else if (browserProxy && browserProxy.mode === 'direct') {
          item.proxy = 'direct';
        } else {
          item.proxy = 'direct';
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
      Object.keys(item.headers).forEach((k) => {
        if (!item.headers[k] || !String(item.headers[k]).trim()) {
          delete item.headers[k];
        }
      });
    };
    if (Array.isArray(taskData)) {
      taskData.forEach(fillProxy);
    } else if (taskData && typeof taskData === 'object') {
      fillProxy(taskData);
    }
  } catch (e) {}

  for (const host of ['127.0.0.1', 'localhost']) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3500);
      const resp = await fetch(`http://${host}:18910/api/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(taskData),
        signal: controller.signal
      });
      clearTimeout(timer);
      if (resp.ok) {
        return await resp.json();
      }
    } catch (e) {}
  }

  return new Promise((resolve) => {
    try {
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
    } catch (e) {
      resolve({ success: false, error: String(e) });
    }
  });
}

function syncClientLanguage() {
  localFetch("/api/status", { method: "GET" }, 2500)
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
              status.textContent = "播放失败：" + (data.type || "") + " / " + (data.details || "");
            }
          });
        } else if (cfg.isM3u8 && video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = cfg.url;
          video.play().catch(() => {});
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

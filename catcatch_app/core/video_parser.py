"""
CatCatch Downloader - Universal Web Video Parser Engine (全网视频一键提取引擎)
支持直接输入/粘贴网页分享链接 (Bilibili, 抖音无水印, 快手, 小红书, 微博, 通用HTML5视频网页)
无需打开浏览器，自动逆向解析并提取真实高清音视频直链与 M3U8 清单
"""
import os
import re
import json
import urllib.parse
import requests

from .config import config


def parse_video_url(url: str, proxy: str = "") -> dict:
    """
    通用视频解析主入口
    输入: 任意平台视频链接或分享文本
    返回: {
        "success": bool,
        "title": str,
        "url": str,              # 提取出的直链或 m3u8
        "media_type": str,        # "m3u8" or "video"
        "duration": int,          # 秒
        "resolution": str,
        "cover": str,
        "headers": dict,
        "error": str
    }
    """
    url = url.strip()
    # 从粘贴的混合文本中提取第一条 http/https 链接
    m_url = re.search(r'https?://[^\s<>"]+', url)
    if m_url:
        target_url = m_url.group(0)
    else:
        target_url = url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    proxies = {}
    if proxy and proxy not in ["none", "direct"]:
        proxies = {"http": proxy, "https": proxy}

    session = requests.Session()
    session.trust_env = False  # 禁用环境变量中可能损坏的 SOCKS 代理，保证国内域名直连通畅
    session.headers.update(headers)
    if proxies:
        session.proxies.update(proxies)

    domain = urllib.parse.urlparse(target_url).netloc.lower()
    lower_path = target_url.lower().split("?")[0]

    # 0. 若输入本身即为 m3u8 / mpd / mp4 直链，直接规范化返回
    if ".m3u8" in lower_path or ".mpd" in lower_path:
        base_name = os.path.splitext(os.path.basename(lower_path))[0] or "m3u8_stream"
        return {
            "success": True,
            "title": base_name,
            "url": target_url,
            "media_type": "m3u8",
            "duration": 0,
            "resolution": "自适应",
            "headers": {},
            "error": ""
        }
    elif any(lower_path.endswith(ext) for ext in [".mp4", ".flv", ".webm", ".mkv", ".ts", ".avi", ".mov"]):
        base_name = os.path.splitext(os.path.basename(lower_path))[0] or "video_file"
        return {
            "success": True,
            "title": base_name,
            "url": target_url,
            "media_type": "video",
            "duration": 0,
            "resolution": "原画",
            "headers": {},
            "error": ""
        }

    # 1. 抖音 / TikTok 无水印解析
    if "douyin.com" in domain or "iesdouyin.com" in domain:
        return _parse_douyin(target_url, session)

    # 2. 哔哩哔哩 Bilibili 解析
    elif "bilibili.com" in domain or "b23.tv" in domain:
        return _parse_bilibili(target_url, session)

    # 3. 快手 Kuaishou 解析
    elif "kuaishou.com" in domain or "chenzhongtech.com" in domain:
        return _parse_kuaishou(target_url, session)

    # 4. 小红书 Xiaohongshu 解析
    elif "xiaohongshu.com" in domain or "xhslink.com" in domain:
        return _parse_xiaohongshu(target_url, session)

    # 5. 通用网页媒体探测 (检测 og:video, HTML5 <video>, 或内嵌 m3u8)
    else:
        return _parse_generic_web(target_url, session)


def _parse_douyin(url, session):
    """解析抖音无水印视频直链 (多引擎协同: 静态提取 -> 移动端接口 -> yt-dlp -> 浏览器嗅探直达)"""
    try:
        # 跟随短链重定向
        resp = session.get(url, allow_redirects=True, timeout=8)
        final_url = resp.url

        # 匹配视频 ID
        m_vid = re.search(r'/video/(\d+)', final_url)
        if not m_vid:
            m_vid = re.search(r'item_ids=(\d+)', final_url)

        html = resp.text
        m_title = re.search(r'<title>([^<]+)</title>', html)
        title = m_title.group(1).replace(" - 抖音", "").strip() if m_title else "抖音视频"
        title = re.sub(r'[\r\n\t]+', ' ', title).strip()

        # 引擎 1: 从网页源码直接正则匹配视频直链
        m_play = re.search(r'"play_addr":\{"uri":"[^"]*","url_list":\["([^"]+)"', html)
        if not m_play:
            m_play = re.search(r'playAddr":\[\{"src":"([^"]+)"', html)
        if not m_play:
            m_play = re.search(r'"(https://[^\s"\'<>]+\.douyinvod\.com/[^\s"\'<>]+)"', html)

        if m_play:
            raw_video_url = m_play.group(1).replace("\\u0026", "&").replace("playwm", "play")
            return {
                "success": True,
                "title": title,
                "url": raw_video_url,
                "media_type": "video",
                "duration": 0,
                "resolution": "1080P",
                "headers": {"Referer": "https://www.douyin.com/"},
                "error": ""
            }

        # 引擎 2: 尝试移动端官方分享接口
        if m_vid:
            vid = m_vid.group(1)
            api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={vid}"
            headers_mob = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
            }
            try:
                api_resp = session.get(api_url, headers=headers_mob, timeout=6)
                if api_resp.status_code == 200 and api_resp.text.strip():
                    data = api_resp.json()
                    item_list = data.get("item_list", [])
                    if item_list:
                        item = item_list[0]
                        desc = item.get("desc") or title
                        play_addr = item.get("video", {}).get("play_addr", {}).get("url_list", [])
                        if play_addr:
                            clean_url = play_addr[0].replace("playwm", "play")
                            return {
                                "success": True,
                                "title": desc,
                                "url": clean_url,
                                "media_type": "video",
                                "duration": int(item.get("duration", 0) / 1000),
                                "resolution": "高清",
                                "headers": {"User-Agent": headers_mob["User-Agent"]},
                                "error": ""
                            }
            except Exception:
                pass

        # 引擎 3: 尝试调用本地 yt-dlp 解析引擎
        try:
            import yt_dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
                'socket_timeout': 6
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(final_url, download=False)
                if info and info.get('url'):
                    return {
                        "success": True,
                        "title": info.get("title") or title,
                        "url": info.get("url"),
                        "media_type": "video",
                        "duration": int(info.get("duration") or 0),
                        "resolution": "1080P",
                        "headers": info.get("http_headers", {}),
                        "error": ""
                    }
        except Exception:
            pass

        # 引擎 4: 针对强风控平台的市面大厂最佳解决方案 (指引浏览器自动嗅探)
        return {
            "success": False,
            "title": title,
            "url": final_url,
            "target_browser_url": final_url,
            "need_browser": True,
            "error": "该视频触发了抖音动态JS安全防护(Argus/VMP)。请点击右侧【在浏览器中打开并嗅探】，星流浏览器插件将全自动无水印捕获并极速下载！"
        }

    except Exception as e:
        return {
            "success": False,
            "title": "",
            "url": url,
            "target_browser_url": url,
            "need_browser": True,
            "error": f"抖音解析异常: {e}。建议直接点击【在浏览器中打开并嗅探】"
        }


def _parse_bilibili(url, session):
    """解析 B站 视频 (自动获取 BV 号、标题与高质量视频流)"""
    try:
        resp = session.get(url, allow_redirects=True, timeout=8)
        final_url = resp.url

        m_bv = re.search(r'(BV[a-zA-Z0-9]+)', final_url)
        if not m_bv:
            return _parse_generic_web(final_url, session)

        bvid = m_bv.group(1)
        # 调用 B站公共 Web 接口获取基本信息与 cid
        view_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        headers_bili = {
            "Referer": "https://www.bilibili.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        view_resp = session.get(view_api, headers=headers_bili, timeout=8).json()
        if view_resp.get("code") != 0:
            return {"success": False, "title": "", "url": "", "error": f"B站接口错误: {view_resp.get('message')}"}

        v_data = view_resp["data"]
        title = v_data.get("title", f"bilibili_{bvid}")
        cid = v_data.get("cid", 0)
        duration = v_data.get("duration", 0)
        cover = v_data.get("pic", "")

        # 调取 playurl 接口获取高画质 mp4 / flv 播放地址 (fnval=0 请求 mp4 直链流)
        play_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=0&fnver=0&fourk=1"
        play_resp = session.get(play_api, headers=headers_bili, timeout=8).json()

        if play_resp.get("code") == 0:
            durl_list = play_resp.get("data", {}).get("durl", [])
            if durl_list:
                stream_url = durl_list[0].get("url")
                return {
                    "success": True,
                    "title": title,
                    "url": stream_url,
                    "media_type": "video",
                    "duration": duration,
                    "resolution": "1080P",
                    "cover": cover,
                    "headers": {
                        "Referer": "https://www.bilibili.com",
                        "User-Agent": headers_bili["User-Agent"]
                    },
                    "error": ""
                }

        return _parse_generic_web(final_url, session)

    except Exception as e:
        return {"success": False, "title": "", "url": "", "error": f"B站解析异常: {e}"}


def _parse_kuaishou(url, session):
    """快手短视频解析"""
    try:
        resp = session.get(url, allow_redirects=True, timeout=8)
        html = resp.text

        m_title = re.search(r'<title>([^<]+)</title>', html)
        title = m_title.group(1).split("-")[0].strip() if m_title else "快手视频"

        m_video = re.search(r'"url":"(https?://[^"]+\.mp4[^"]*)"', html)
        if not m_video:
            m_video = re.search(r'src="(https?://[^"]+\.mp4[^"]*)"', html)

        if m_video:
            video_url = m_video.group(1).replace("\\u0026", "&")
            return {
                "success": True,
                "title": title,
                "url": video_url,
                "media_type": "video",
                "duration": 0,
                "resolution": "高清",
                "headers": {"Referer": "https://www.kuaishou.com/"},
                "error": ""
            }

        return _parse_generic_web(resp.url, session)
    except Exception as e:
        return {"success": False, "title": "", "url": "", "error": f"快手解析失败: {e}"}


def _parse_xiaohongshu(url, session):
    """小红书视频笔记解析"""
    try:
        resp = session.get(url, allow_redirects=True, timeout=8)
        html = resp.text

        m_title = re.search(r'<meta name="description" content="([^"]+)"', html)
        title = m_title.group(1)[:50].strip() if m_title else "小红书视频"

        m_video = re.search(r'originVideoKey":"([^"]+)"', html)
        if m_video:
            video_url = f"https://sns-video-bd.xhscdn.com/{m_video.group(1)}"
            return {
                "success": True,
                "title": title,
                "url": video_url,
                "media_type": "video",
                "duration": 0,
                "resolution": "高清",
                "headers": {"Referer": "https://www.xiaohongshu.com/"},
                "error": ""
            }

        return _parse_generic_web(resp.url, session)
    except Exception as e:
        return {"success": False, "title": "", "url": "", "error": f"小红书解析异常: {e}"}


def _parse_generic_web(url, session):
    """通用网页 HTML5 视频与内嵌 M3U8 清单嗅探"""
    try:
        resp = session.get(url, timeout=10)
        html = resp.text

        m_title = re.search(r'<title>([^<]+)</title>', html, re.I)
        title = m_title.group(1).strip() if m_title else "在线网络视频"
        title = re.sub(r'[\r\n\t]+', ' ', title).strip()

        # 1. 优先检索 M3U8 清单地址
        m_m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8(?:\?[^"\']*)?)["\']', html, re.I)
        if m_m3u8:
            return {
                "success": True,
                "title": title,
                "url": m_m3u8.group(1),
                "media_type": "m3u8",
                "duration": 0,
                "resolution": "自适应",
                "headers": {"Referer": url},
                "error": ""
            }

        # 2. 检索 HTML5 <video src="..."> 或 <source src="...">
        m_video = re.search(r'<video[^>]+src=["\'](https?://[^"\']+\.(?:mp4|webm|mkv)[^"\']*)["\']', html, re.I)
        if not m_video:
            m_video = re.search(r'<source[^>]+src=["\'](https?://[^"\']+\.(?:mp4|webm|mkv)[^"\']*)["\']', html, re.I)
        if not m_video:
            m_video = re.search(r'property="og:video"[^>]+content=["\'](https?://[^"\']+)["\']', html, re.I)

        if m_video:
            return {
                "success": True,
                "title": title,
                "url": m_video.group(1),
                "media_type": "video",
                "duration": 0,
                "resolution": "高清",
                "headers": {"Referer": url},
                "error": ""
            }

        return {
            "success": False,
            "title": title,
            "url": "",
            "error": "未能在该网页中直接嗅探到公开媒体直链，请在浏览器中播放并使用配套扩展嗅探！"
        }

    except Exception as e:
        return {"success": False, "title": "", "url": "", "error": f"网页请求失败: {e}"}

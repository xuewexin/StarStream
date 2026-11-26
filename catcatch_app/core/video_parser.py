"""
CatCatch Downloader - Universal Web Video Parser Engine (全网视频一键提取引擎)
支持直接输入/粘贴网页分享链接 (Bilibili, 抖音无水印, 快手, 小红书, 微博, 通用HTML5视频网页)
支持同系列视频/音频合集探测与批量入队爬取 (B站多P/UP合集/番剧/音频歌单, YouTube列表, 通用剧集/网课网页)
无需打开浏览器，自动逆向解析并提取真实高清音视频直链与 M3U8 清单
"""
import os
import re
import json
import time
import threading
import urllib.parse
import requests

from .config import config, should_bypass_proxy


def _build_session(target_url: str = "", proxy: str = "", extra_headers: dict = None) -> requests.Session:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    if extra_headers:
        for k, v in extra_headers.items():
            if v:
                headers[k] = v

    session = requests.Session()
    session.trust_env = False  # 禁用环境变量中可能损坏的 SOCKS 代理，保证国内域名直连通畅
    session.headers.update(headers)

    if proxy and proxy not in ["none", "direct"]:
        session.proxies.update({"http": proxy, "https": proxy})

    if target_url and should_bypass_proxy(target_url):
        session.proxies.clear()
        session.trust_env = False

    return session


def parse_video_url(url: str, proxy: str = "", extra_headers: dict = None) -> dict:
    """
    通用视频解析主入口
    输入: 任意平台视频链接或分享文本
    返回: {
        "success": bool,
        "title": str,
        "url": str,              # 提取出的直链或 m3u8
        "audio_url": str,        # 可选独立音频流
        "media_type": str,        # "m3u8" or "video" or "audio" or "bili_dash"
        "duration": int,          # 秒
        "resolution": str,
        "cover": str,
        "headers": dict,
        "series": dict,           # 可选同系列合集信息 {has_series, series_title, series_type, total, current_index, episodes}
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

    session = _build_session(target_url, proxy=proxy, extra_headers=extra_headers)

    domain = urllib.parse.urlparse(target_url).netloc.lower()
    lower_path = target_url.lower().split("?")[0]

    # 0. 若输入本身即为 m3u8 / mpd / mp4 / mp3 直链，直接规范化返回
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
    elif any(lower_path.endswith(ext) for ext in [".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"]):
        base_name = os.path.splitext(os.path.basename(lower_path))[0] or "audio_file"
        return {
            "success": True,
            "title": base_name,
            "url": target_url,
            "media_type": "audio",
            "duration": 0,
            "resolution": "无损/高音质",
            "headers": {},
            "error": ""
        }

    # 1. 抖音 / TikTok 无水印解析
    if "douyin.com" in domain or "iesdouyin.com" in domain:
        return _parse_douyin(target_url, session)

    # 2. 哔哩哔哩 Bilibili 解析 (支持分P / 合集 / 番剧 / 音频歌单)
    elif "bilibili.com" in domain or "b23.tv" in domain:
        return _parse_bilibili(target_url, session)

    # 3. 快手 Kuaishou 解析
    elif "kuaishou.com" in domain or "chenzhongtech.com" in domain:
        return _parse_kuaishou(target_url, session)

    # 4. 小红书 Xiaohongshu 解析
    elif "xiaohongshu.com" in domain or "xhslink.com" in domain:
        return _parse_xiaohongshu(target_url, session)

    # 5. YouTube / Playlist 检测
    elif "youtube.com" in domain or "youtu.be" in domain:
        return _parse_youtube_or_ytdlp(target_url, session)

    # 6. 通用网页媒体与同系列剧集探测
    else:
        return _parse_generic_web(target_url, session)


def _extract_json_object(text, marker):
    idx = text.find(marker)
    if idx == -1:
        return None
    brace = text.find("{", idx)
    if brace == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(brace, min(len(text), brace + 400000)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace:i + 1])
                    except Exception:
                        return None
    return None


def _find_douyin_item(obj):
    if isinstance(obj, dict):
        if "video" in obj and isinstance(obj["video"], dict) and "play_addr" in obj["video"]:
            return obj
        for v in obj.values():
            found = _find_douyin_item(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_douyin_item(v)
            if found:
                return found
    return None


def _parse_douyin(url, session):
    """解析抖音无水印视频直链 (手机分享页 _ROUTER_DATA -> 静态源码 -> 移动端接口 -> yt-dlp -> 浏览器嗅探)"""
    mob_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
    try:
        # 优先使用移动端 UA 跟进短链，避免桌面端触发 JS 人机挑战页
        resp = session.get(url, headers={"User-Agent": mob_ua}, allow_redirects=True, timeout=8)
        final_url = resp.url

        m_vid = re.search(r'/(?:video|note)/(\d+)', final_url) or re.search(r'(?:item_ids|modal_id)=(\d+)', final_url)
        html = resp.text
        m_title = re.search(r'<title>([^<]+)</title>', html)
        title = m_title.group(1).replace(" - 抖音", "").strip() if m_title else "抖音视频"
        title = re.sub(r'[\r\n\t]+', ' ', title).strip()

        # 引擎 0: 移动端 iesdouyin /share/video/{id}/ 内嵌 _ROUTER_DATA (绕过桌面 JS 校验)
        if m_vid:
            vid = m_vid.group(1)
            try:
                share_resp = session.get(f"https://www.iesdouyin.com/share/video/{vid}/", headers={"User-Agent": mob_ua}, timeout=8)
                router_data = _extract_json_object(share_resp.text, "_ROUTER_DATA")
                item = _find_douyin_item(router_data) if router_data else None
                if item:
                    desc = (item.get("desc") or title or f"douyin_{vid}").strip()
                    url_list = ((item.get("video") or {}).get("play_addr") or {}).get("url_list") or []
                    if url_list:
                        clean_url = str(url_list[0]).replace("playwm", "play")
                        # 跟进 iesdouyin/aweme/v1/play 重定向取得最终直链
                        try:
                            r_cdn = session.get(clean_url, headers={"User-Agent": mob_ua}, allow_redirects=True, stream=True, timeout=6)
                            if r_cdn.url and r_cdn.url.startswith("http"):
                                clean_url = r_cdn.url
                            r_cdn.close()
                        except Exception:
                            pass
                        return {
                            "success": True,
                            "title": re.sub(r'[\r\n\t]+', ' ', desc)[:80],
                            "url": clean_url,
                            "media_type": "video",
                            "duration": int((item.get("duration") or 0) / 1000) if (item.get("duration") or 0) > 1000 else int(item.get("duration") or 0),
                            "resolution": "1080P",
                            "headers": {"User-Agent": mob_ua, "Referer": "https://www.douyin.com/"},
                            "error": ""
                        }
            except Exception:
                pass

        # 引擎 1: 从网页源码直接正则匹配视频直链 (支持 URL-Decode 深入解析 RENDER_DATA / _ROUTER_DATA)
        m_play = re.search(r'"play_addr":\{"uri":"[^"]*","url_list":\["([^"]+)"', html)
        if not m_play:
            m_play = re.search(r'playAddr":\[\{"src":"([^"]+)"', html)
        if not m_play:
            m_play = re.search(r'"(https://[^\s"\'<>]+\.douyinvod\.com/[^\s"\'<>]+)"', html)
        if not m_play:
            unquoted_html = urllib.parse.unquote(html)
            m_play = re.search(r'"play_addr":\{"uri":"[^"]*","url_list":\["([^"]+)"', unquoted_html)
            if not m_play:
                m_play = re.search(r'playAddr":\[\{"src":"([^"]+)"', unquoted_html)
            if not m_play:
                m_play = re.search(r'"(https://[^\s"\'<>]+\.douyinvod\.com/[^\s"\'<>]+)"', unquoted_html)

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


def _fetch_bili_playurl(session, bvid, cid, headers_bili, is_pgc=False, ep_id=0):
    """获取 B站 指定 bvid+cid (或番剧 ep_id+cid) 的最高画质视频与独立音频流"""
    # 1. 优先请求 DASH 格式 (fnval=16)，获取最高画质视频流与独立音频流
    if is_pgc and ep_id:
        dash_api = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&cid={cid}&qn=80&fnval=16&fourk=1"
    else:
        dash_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=16&fnver=0&fourk=1"

    try:
        dash_resp = session.get(dash_api, headers=headers_bili, timeout=8).json()
        if dash_resp.get("code") == 0:
            raw_data = dash_resp.get("result") if is_pgc else dash_resp.get("data")
            dash_data = (raw_data or {}).get("dash", {})
            videos = dash_data.get("video", [])
            audios = dash_data.get("audio", [])
            if videos:
                best_video = max(videos, key=lambda v: v.get("id", 0))
                v_url = best_video.get("baseUrl") or best_video.get("base_url")
                a_url = ""
                if audios:
                    best_audio = max(audios, key=lambda a: a.get("id", 0))
                    a_url = best_audio.get("baseUrl") or best_audio.get("base_url")

                q_id = best_video.get("id", 80)
                q_name = "1080P" if q_id >= 80 else ("720P" if q_id >= 64 else "480P")
                if q_id >= 120:
                    q_name = "4K"
                elif q_id == 116:
                    q_name = "1080P60"
                elif q_id == 112:
                    q_name = "1080P+"

                return {
                    "success": True,
                    "url": v_url,
                    "audio_url": a_url,
                    "media_type": "bili_dash" if a_url else "video",
                    "resolution": q_name,
                }
    except Exception:
        pass

    # 2. 兜底 mp4/flv durl 接口
    if is_pgc and ep_id:
        play_api = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&cid={cid}&qn=80&fnval=0&fourk=1"
    else:
        play_api = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=0&fnver=0&fourk=1"

    try:
        play_resp = session.get(play_api, headers=headers_bili, timeout=8).json()
        if play_resp.get("code") == 0:
            raw_data = play_resp.get("result") if is_pgc else play_resp.get("data")
            durl_list = (raw_data or {}).get("durl", [])
            if durl_list:
                return {
                    "success": True,
                    "url": durl_list[0].get("url"),
                    "audio_url": "",
                    "media_type": "video",
                    "resolution": "1080P",
                }
    except Exception:
        pass

    return {"success": False}


def _extract_bili_series(v_data, bvid, cur_page_num=1):
    """从 B站 view API 数据中提取多P分集或 UP主合集 (ugc_season)"""
    pages = v_data.get("pages") or []
    ugc_season = v_data.get("ugc_season")
    base_title = v_data.get("title", f"bilibili_{bvid}")
    cover = v_data.get("pic", "")

    # 1. 多P分集
    if len(pages) > 1:
        episodes = []
        for idx, p in enumerate(pages):
            p_num = p.get("page", idx + 1)
            part_title = p.get("part") or f"P{p_num}"
            episodes.append({
                "index": idx + 1,
                "title": part_title,
                "page_url": f"https://www.bilibili.com/video/{bvid}?p={p_num}",
                "duration": int(p.get("duration") or 0),
                "bvid": bvid,
                "cid": int(p.get("cid") or 0),
                "cover": cover,
                "media_type": "bili_dash",
            })
        return {
            "has_series": True,
            "series_title": base_title,
            "series_type": "bili_pages",
            "total": len(episodes),
            "current_index": max(0, min(len(episodes) - 1, cur_page_num - 1)),
            "episodes": episodes,
        }

    # 2. UP主视频合集 / 播单 (ugc_season)
    if ugc_season and ugc_season.get("sections"):
        episodes = []
        cur_idx = 0
        counter = 0
        for sec in ugc_season.get("sections", []):
            for ep in sec.get("episodes", []):
                counter += 1
                ep_bvid = ep.get("bvid") or ""
                ep_cid = int(ep.get("cid") or 0)
                ep_title = ep.get("title") or (ep.get("arc") or {}).get("title") or f"第{counter}集"
                arc = ep.get("arc") or {}
                if ep_bvid == bvid:
                    cur_idx = len(episodes)
                episodes.append({
                    "index": counter,
                    "title": ep_title,
                    "page_url": f"https://www.bilibili.com/video/{ep_bvid}",
                    "duration": int(arc.get("duration") or 0),
                    "bvid": ep_bvid,
                    "cid": ep_cid,
                    "cover": arc.get("pic") or ugc_season.get("cover") or cover,
                    "media_type": "bili_dash",
                })
        if len(episodes) > 1:
            return {
                "has_series": True,
                "series_title": ugc_season.get("title") or base_title,
                "series_type": "bili_season",
                "total": len(episodes),
                "current_index": cur_idx,
                "episodes": episodes,
            }

    return None


def _parse_bili_bangumi(final_url, session):
    """解析 B站 番剧 / 纪录片 / 剧集单集与全集列表"""
    m_ep = re.search(r'/ep(\d+)', final_url)
    m_ss = re.search(r'/ss(\d+)', final_url)
    if not m_ep and not m_ss:
        return None

    headers_bili = {
        "Referer": "https://www.bilibili.com",
        "User-Agent": session.headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36")
    }
    param = f"ep_id={m_ep.group(1)}" if m_ep else f"season_id={m_ss.group(1)}"
    api_url = f"https://api.bilibili.com/pgc/view/web/season?{param}"
    try:
        res = session.get(api_url, headers=headers_bili, timeout=8).json()
        if res.get("code") != 0 or not res.get("result"):
            return None

        result = res["result"]
        season_title = result.get("season_title") or result.get("title") or "B站番剧合集"
        eps_raw = result.get("episodes") or []
        if not eps_raw:
            return None

        target_ep_id = int(m_ep.group(1)) if m_ep else 0
        cur_ep = eps_raw[0]
        cur_idx = 0
        episodes = []
        for idx, ep in enumerate(eps_raw):
            ep_id = int(ep.get("id") or 0)
            ep_cid = int(ep.get("cid") or 0)
            ep_bvid = ep.get("bvid") or ""
            ep_name = ep.get("share_copy") or ep.get("long_title") or ep.get("title") or f"第{idx + 1}话"
            if target_ep_id and ep_id == target_ep_id:
                cur_ep = ep
                cur_idx = idx
            episodes.append({
                "index": idx + 1,
                "title": ep_name,
                "page_url": ep.get("link") or f"https://www.bilibili.com/bangumi/play/ep{ep_id}",
                "duration": int((ep.get("duration") or 0) / 1000) if (ep.get("duration") or 0) > 10000 else int(ep.get("duration") or 0),
                "bvid": ep_bvid,
                "cid": ep_cid,
                "ep_id": ep_id,
                "is_pgc": True,
                "cover": ep.get("cover") or result.get("cover") or "",
                "media_type": "bili_dash",
            })

        stream_info = _fetch_bili_playurl(
            session, cur_ep.get("bvid", ""), int(cur_ep.get("cid") or 0),
            headers_bili, is_pgc=True, ep_id=int(cur_ep.get("id") or 0)
        )
        series_obj = None
        if len(episodes) > 1:
            series_obj = {
                "has_series": True,
                "series_title": season_title,
                "series_type": "bili_bangumi",
                "total": len(episodes),
                "current_index": cur_idx,
                "episodes": episodes,
            }

        if stream_info.get("success"):
            return {
                "success": True,
                "title": cur_ep.get("share_copy") or f"{season_title} - {cur_ep.get('title', '')}".strip(" -"),
                "url": stream_info["url"],
                "audio_url": stream_info.get("audio_url", ""),
                "media_type": stream_info.get("media_type", "bili_dash"),
                "duration": episodes[cur_idx]["duration"],
                "resolution": stream_info.get("resolution", "1080P"),
                "cover": cur_ep.get("cover") or result.get("cover", ""),
                "headers": {"Referer": "https://www.bilibili.com", "User-Agent": headers_bili["User-Agent"]},
                "series": series_obj,
                "error": ""
            }
        elif series_obj:
            return {
                "success": False,
                "title": season_title,
                "url": final_url,
                "cover": result.get("cover", ""),
                "series": series_obj,
                "need_browser": True,
                "error": "该番剧需大会员或登录凭证，已识别全部剧集列表！可在浏览登录后用插件同步 Cookie 一键全套抓取。"
            }
    except Exception:
        pass
    return None


def _parse_bili_audio(final_url, session):
    """解析 B站 音频单曲 (au...) 与音频专辑/歌单 (am...)"""
    headers_bili = {
        "Referer": "https://www.bilibili.com",
        "User-Agent": session.headers.get("User-Agent", "Mozilla/5.0")
    }
    m_am = re.search(r'/audio/am(\d+)', final_url)
    m_au = re.search(r'/audio/au(\d+)', final_url)

    try:
        if m_am:
            menu_id = m_am.group(1)
            info_res = session.get(
                f"https://www.bilibili.com/audio/music-service-c/web/menu/info?sid={menu_id}",
                headers=headers_bili, timeout=8
            ).json()
            songs_res = session.get(
                f"https://www.bilibili.com/audio/music-service-c/web/song/of-menu?sid={menu_id}&pn=1&ps=100",
                headers=headers_bili, timeout=8
            ).json()
            menu_title = ((info_res.get("data") or {}).get("title")) or f"B站音频合集_{menu_id}"
            cover = ((info_res.get("data") or {}).get("cover")) or ""
            songs = ((songs_res.get("data") or {}).get("data")) or []
            if not songs:
                return None

            episodes = []
            for idx, s in enumerate(songs):
                sid = s.get("id")
                episodes.append({
                    "index": idx + 1,
                    "title": s.get("title") or f"音频_{sid}",
                    "page_url": f"https://www.bilibili.com/audio/au{sid}",
                    "duration": int(s.get("duration") or 0),
                    "audio_sid": sid,
                    "cover": s.get("cover") or cover,
                    "media_type": "audio",
                })

            first_sid = songs[0].get("id")
            first_url = _fetch_bili_audio_stream(session, first_sid, headers_bili)
            return {
                "success": bool(first_url),
                "title": songs[0].get("title") or menu_title,
                "url": first_url or episodes[0]["page_url"],
                "media_type": "audio",
                "duration": episodes[0]["duration"],
                "resolution": "高品质音频",
                "cover": cover,
                "headers": {"Referer": "https://www.bilibili.com", "User-Agent": headers_bili["User-Agent"]},
                "series": {
                    "has_series": len(episodes) > 1,
                    "series_title": menu_title,
                    "series_type": "bili_audio",
                    "total": len(episodes),
                    "current_index": 0,
                    "episodes": episodes,
                },
                "error": "" if first_url else "已提取音频歌单，部分曲目可能需要登录后获取播放链接"
            }

        elif m_au:
            sid = m_au.group(1)
            info_res = session.get(
                f"https://www.bilibili.com/audio/music-service-c/web/song/info?sid={sid}",
                headers=headers_bili, timeout=8
            ).json()
            s_data = info_res.get("data") or {}
            title = s_data.get("title") or f"au{sid}"
            stream_url = _fetch_bili_audio_stream(session, sid, headers_bili)
            if stream_url:
                return {
                    "success": True,
                    "title": title,
                    "url": stream_url,
                    "media_type": "audio",
                    "duration": int(s_data.get("duration") or 0),
                    "resolution": "高品质音频",
                    "cover": s_data.get("cover") or "",
                    "headers": {"Referer": "https://www.bilibili.com", "User-Agent": headers_bili["User-Agent"]},
                    "error": ""
                }
    except Exception:
        pass
    return None


def _fetch_bili_audio_stream(session, sid, headers_bili):
    try:
        u_res = session.get(
            f"https://www.bilibili.com/audio/music-service-c/web/url?sid={sid}&privilege=2&quality=2",
            headers=headers_bili, timeout=8
        ).json()
        cdns = ((u_res.get("data") or {}).get("cdns")) or []
        return cdns[0] if cdns else ""
    except Exception:
        return ""


def _parse_bilibili(url, session):
    """解析 B站 视频/番剧/音频合集 (自动获取 BV 号、分P cid、同系列合集与高质量音视频流)"""
    try:
        resp = session.get(url, allow_redirects=True, timeout=8)
        final_url = resp.url

        # 1. 番剧 / 纪录片
        if "/bangumi/play/" in final_url:
            pgm_res = _parse_bili_bangumi(final_url, session)
            if pgm_res:
                return pgm_res

        # 2. 音频单曲 / 歌单合集
        if "/audio/" in final_url:
            au_res = _parse_bili_audio(final_url, session)
            if au_res:
                return au_res

        m_bv = re.search(r'(BV[a-zA-Z0-9]+)', final_url)
        if not m_bv:
            return _parse_generic_web(final_url, session)

        bvid = m_bv.group(1)
        # 提取 ?p=N 分集号
        parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(final_url).query)
        try:
            target_p = max(1, int((parsed_q.get("p") or ["1"])[0]))
        except Exception:
            target_p = 1

        # 调用 B站公共 Web 接口获取基本信息、pages 分P 与 ugc_season 合集
        view_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        headers_bili = {
            "Referer": "https://www.bilibili.com",
            "User-Agent": session.headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36")
        }
        view_resp = session.get(view_api, headers=headers_bili, timeout=8).json()
        if view_resp.get("code") != 0:
            return {"success": False, "title": "", "url": "", "error": f"B站接口错误: {view_resp.get('message')}"}

        v_data = view_resp["data"]
        title = v_data.get("title", f"bilibili_{bvid}")
        pages = v_data.get("pages") or []
        cid = v_data.get("cid", 0)
        duration = v_data.get("duration", 0)

        if pages and 1 <= target_p <= len(pages):
            p_info = pages[target_p - 1]
            cid = p_info.get("cid") or cid
            duration = p_info.get("duration") or duration
            if len(pages) > 1 and p_info.get("part"):
                title = f"{title} - P{target_p} {p_info.get('part')}"

        cover = v_data.get("pic", "")
        series_info = _extract_bili_series(v_data, bvid, cur_page_num=target_p)

        stream_info = _fetch_bili_playurl(session, bvid, cid, headers_bili)
        if stream_info.get("success"):
            return {
                "success": True,
                "title": title,
                "url": stream_info["url"],
                "audio_url": stream_info.get("audio_url", ""),
                "media_type": stream_info.get("media_type", "video"),
                "duration": duration,
                "resolution": stream_info.get("resolution", "1080P"),
                "cover": cover,
                "headers": {
                    "Referer": "https://www.bilibili.com",
                    "User-Agent": headers_bili["User-Agent"]
                },
                "series": series_info,
                "error": ""
            }

        res_fallback = _parse_generic_web(final_url, session)
        if series_info and not res_fallback.get("series"):
            res_fallback["series"] = series_info
        return res_fallback

    except Exception as e:
        return {"success": False, "title": "", "url": "", "error": f"B站解析异常: {e}"}


def _parse_youtube_or_ytdlp(url, session):
    """解析 YouTube 单视频 / 播放列表 (Playlist) 或 yt-dlp 支持的其他站点"""
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "socket_timeout": 8,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return _parse_generic_web(url, session)

            # 若为播放列表/合集
            if info.get("_type") == "playlist" or info.get("entries"):
                entries = [e for e in (info.get("entries") or []) if e]
                episodes = []
                for idx, e in enumerate(entries[:200]):
                    ep_url = e.get("url") or e.get("webpage_url") or ""
                    if ep_url and not ep_url.startswith("http") and e.get("id"):
                        ep_url = f"https://www.youtube.com/watch?v={e['id']}"
                    episodes.append({
                        "index": idx + 1,
                        "title": e.get("title") or f"Video {idx + 1}",
                        "page_url": ep_url,
                        "duration": int(e.get("duration") or 0),
                        "cover": e.get("thumbnail") or "",
                        "media_type": "video",
                    })
                first_res = _parse_youtube_single(episodes[0]["page_url"]) if episodes else {}
                return {
                    "success": bool(first_res.get("url")),
                    "title": info.get("title") or (episodes[0]["title"] if episodes else "Playlist"),
                    "url": first_res.get("url") or (episodes[0]["page_url"] if episodes else url),
                    "media_type": first_res.get("media_type", "video"),
                    "duration": first_res.get("duration", 0),
                    "resolution": first_res.get("resolution", "1080P"),
                    "cover": first_res.get("cover", ""),
                    "headers": first_res.get("headers", {}),
                    "series": {
                        "has_series": len(episodes) > 1,
                        "series_title": info.get("title") or "YouTube 播放列表",
                        "series_type": "yt_playlist",
                        "total": len(episodes),
                        "current_index": 0,
                        "episodes": episodes,
                    } if len(episodes) > 1 else None,
                    "error": "" if first_res.get("url") else "已读取列表，若单集解析受阻可配合浏览器扩展嗅探",
                }
            else:
                return _parse_youtube_single(url, pre_info=info)
    except Exception:
        return _parse_generic_web(url, session)


def _parse_youtube_single(url, pre_info=None):
    try:
        import yt_dlp
        if pre_info and pre_info.get("url"):
            info = pre_info
        else:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 8}) as ydl:
                info = ydl.extract_info(url, download=False)
        if info and info.get("url"):
            return {
                "success": True,
                "title": info.get("title") or "YouTube Video",
                "url": info.get("url"),
                "media_type": "video",
                "duration": int(info.get("duration") or 0),
                "resolution": f"{info.get('height')}P" if info.get("height") else "高清",
                "cover": info.get("thumbnail") or "",
                "headers": info.get("http_headers", {}),
                "error": "",
            }
    except Exception:
        pass
    return {"success": False, "url": ""}


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


def _extract_generic_series(html: str, base_url: str, page_title: str = ""):
    """
    通用网页 HTML 同系列剧集/课程/播客列表智能探测
    在连续剧网站、网课平台、播客专辑页中识别 "第N集/第N讲/P1/01" 或路径同构的选集链接群
    """
    if not html or not base_url:
        return None

    try:
        parsed_base = urllib.parse.urlparse(base_url)
        base_host = parsed_base.netloc.lower()
        base_path = parsed_base.path.rstrip("/")

        # 抓取所有 <a href="...">文本</a> (兼容双引号、单引号及无引号属性值)
        anchor_pattern = re.compile(r'<a\b[^>]*?href=(?:["\']([^"\'#]+)["\']|([^\s>"\'#]+))[^>]*>(.*?)</a>', re.I | re.S)
        ep_label_re = re.compile(
            r'(第\s*\d+\s*[集话期章讲节课部回]|EP?\s*\d+|P\d+|^\d{1,3}$|^(?:集|话|期|课)\s*\d+|番外|先导|预告|全集)',
            re.I
        )

        # 提取当前页面路径前缀模式用于同构匹配（如 /play/12345-1-1.html -> /play/12345-1-）
        path_prefix_re = re.sub(r'\d+(?=(?:\.[a-z]+)?$)', '', base_path)

        candidates = []
        seen_idx_map = {}
        noise_re = re.compile(r'(次觀看|次观看|views|已完結|已完结|全\s*\d+\s*集)', re.I)
        action_prefix_re = re.compile(
            r'^(?:從|从|立即|开始|開始|观看|觀看|正在).*?(?:開始|开始|播放|观看|觀看)$|^(?:上一集|下一集|播放|正在播放)$',
            re.I
        )

        for m in anchor_pattern.finditer(html):
            raw_href = (m.group(1) or m.group(2) or "").strip()
            if not raw_href or raw_href.startswith(("javascript:", "mailto:", "tel:")):
                continue
            raw_text = re.sub(r'<[^>]+>', ' ', m.group(3))
            raw_text = re.sub(r'\s+', ' ', raw_text).strip()
            if not raw_text or len(raw_text) > 50 or noise_re.search(raw_text):
                continue

            abs_url = urllib.parse.urljoin(base_url, raw_href)
            p_abs = urllib.parse.urlparse(abs_url)
            if p_abs.netloc.lower() != base_host:
                continue

            abs_path = p_abs.path.rstrip("/")
            is_ep_text = bool(ep_label_re.search(raw_text))
            is_same_pattern = bool(
                path_prefix_re and len(path_prefix_re) > 3 and
                abs_path.startswith(path_prefix_re) and abs_path != path_prefix_re
            )

            if is_ep_text or is_same_pattern:
                if abs_url in seen_idx_map:
                    old_item = candidates[seen_idx_map[abs_url]]
                    if action_prefix_re.match(old_item["title"]) and not action_prefix_re.match(raw_text):
                        old_item["title"] = raw_text
                    continue
                seen_idx_map[abs_url] = len(candidates)
                candidates.append({
                    "title": raw_text,
                    "page_url": abs_url,
                    "is_ep_text": is_ep_text,
                    "is_same_pattern": is_same_pattern,
                })

        # 优先取同构路径或至少 2 条以上有效选集
        same_pat = [c for c in candidates if c["is_same_pattern"]]
        pool = same_pat if len(same_pat) >= 2 else [c for c in candidates if c["is_ep_text"]]

        if len(pool) < 2:
            return None

        episodes = []
        cur_idx = 0
        # 优先从 "系列 · 剧名" 或剧集共同前缀提取真实剧集名，避免只取到站点品牌名（如“黄果短剧”）
        clean_series_title = ""
        m_ser_name = re.search(r'(?:系列|合集|剧集)\s*[·:：]\s*([^|—\-]+)', page_title)
        if m_ser_name:
            clean_series_title = m_ser_name.group(1).strip()
        if not clean_series_title and pool:
            ep0_base = re.sub(r'\s*[·\-—]\s*第?\s*\d+\s*[集话期章节].*$', '', pool[0]["title"]).strip()
            if ep0_base and len(ep0_base) >= 2 and all(ep0_base in p["title"] for p in pool[:min(3, len(pool))]):
                clean_series_title = ep0_base
        if not clean_series_title:
            clean_series_title = re.sub(r'\s*[-_|—].*$', '', page_title).strip() or "网页同系列合集"

        # 若剧集标题包含明确的 "第N集/话" 编号，按集数升序排列
        def _ep_sort_key(item_tuple):
            i, it = item_tuple
            m_num = re.search(r'第\s*(\d+)\s*[集话期章节]', it["title"])
            return (0, int(m_num.group(1)), i) if m_num else (1, i, i)

        ordered_pool = [it for _, it in sorted(enumerate(pool[:150]), key=_ep_sort_key)]
        for idx, item in enumerate(ordered_pool):
            if item["page_url"] == base_url:
                cur_idx = idx
            episodes.append({
                "index": idx + 1,
                "title": item["title"],
                "page_url": item["page_url"],
                "duration": 0,
                "cover": "",
                "media_type": "video",
            })

        return {
            "has_series": True,
            "series_title": clean_series_title,
            "series_type": "web_series",
            "total": len(episodes),
            "current_index": cur_idx,
            "episodes": episodes,
        }
    except Exception:
        return None


def _decode_embedded_ev_payload(html: str, page_url: str):
    """提取并解码网页中嵌入的 ev:{d:"...", k:N} (Base64 + 字符偏移) 加密媒体配置"""
    m_ev = re.search(r'ev:.*?\{d:\s*["\']([^"\']+)["\']\s*,\s*k:\s*(\d+)\}', html)
    if not m_ev:
        return None
    try:
        import base64
        raw_d = m_ev.group(1)
        shift_k = int(m_ev.group(2))
        decoded_raw = base64.b64decode(raw_d).decode("latin1")
        json_str = "".join(chr(ord(ch) - shift_k) for ch in decoded_raw)
        obj = json.loads(json_str)
        v_url = (obj.get("videoUrl") or obj.get("url") or "").strip()
        if v_url:
            abs_v_url = urllib.parse.urljoin(page_url, v_url)
            parsed = urllib.parse.urlparse(page_url)
            origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
            return {
                "url": abs_v_url,
                "media_type": "m3u8" if ("hls" in abs_v_url.lower() or "m3u8" in abs_v_url.lower()) else "video",
                "headers": {"Referer": page_url, **({"Origin": origin} if origin else {})},
            }
    except Exception:
        pass
    return None


def _unwrap_base64_document_write(html: str) -> str:
    """自动还原整页 Base64 编码 + document.write 混淆的网页 HTML (如泛影视 MacCMS 站)"""
    if not html or "document.write" not in html:
        return html
    m = re.search(r'<script[^>]*>\s*var\s+[a-zA-Z_]\w*\s*=\s*["\']([A-Za-z0-9+/=]{200,})["\']', html)
    if not m:
        return html
    try:
        import base64
        raw = base64.b64decode(m.group(1)).decode("utf-8", errors="replace")
        raw = raw.replace(r"\/", "/").replace(r'\"', '"').replace(r"\\", "\\")
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        raw = re.sub(r"\\u([0-9a-fA-F]{4})", lambda x: chr(int(x.group(1), 16)), raw)
        if "<html" in raw.lower() or "player_aaaa" in raw or "<a " in raw.lower():
            return raw
    except Exception:
        pass
    return html


def _extract_player_aaaa(html: str, page_url: str):
    """提取 MacCMS 播放器配置 player_aaaa={...} 中的直链、标题与封面"""
    idx = html.find("player_aaaa")
    if idx == -1:
        return None
    brace_start = html.find("{", idx)
    if brace_start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    end_idx = -1
    for i in range(brace_start, min(len(html), brace_start + 8000)):
        ch = html[i]
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
    if end_idx == -1:
        return None
    try:
        obj = json.loads(html[brace_start:end_idx])
        v_url = (obj.get("url") or "").strip()
        if v_url and not v_url.startswith("http") and obj.get("encrypt") == 1:
            v_url = urllib.parse.unquote(v_url)
        elif v_url and not v_url.startswith("http") and obj.get("encrypt") == 2:
            import base64
            try:
                v_url = urllib.parse.unquote(base64.b64decode(v_url).decode("utf-8", errors="ignore"))
            except Exception:
                pass
        if v_url and v_url.startswith("http"):
            vod_data = obj.get("vod_data") or {}
            parsed = urllib.parse.urlparse(page_url)
            origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
            return {
                "url": v_url,
                "title": (vod_data.get("vod_name") or "").strip(),
                "cover": (vod_data.get("vod_pic") or "").strip(),
                "media_type": "m3u8" if (".m3u8" in v_url.lower() or "m3u8" in v_url.lower()) else "video",
                "headers": {"Referer": page_url, **({"Origin": origin} if origin else {})},
            }
    except Exception:
        pass
    return None


def _fetch_with_proxy_fallback(session, url: str, timeout: int = 10):
    """优先按当前会话拉取；若直连被重置/阻断，自动嗅探本机活跃代理重试"""
    used_proxy = ""
    try:
        if session.proxies:
            used_proxy = session.proxies.get("https") or session.proxies.get("http") or ""
        resp = session.get(url, timeout=timeout)
        return resp, used_proxy
    except Exception as first_err:
        if session.proxies or should_bypass_proxy(url):
            raise first_err
        try:
            from .config import detect_local_active_proxies
            actives = detect_local_active_proxies()
            for act in actives:
                p_url = act.get("url")
                if not p_url:
                    continue
                try:
                    resp = session.get(url, proxies={"http": p_url, "https": p_url}, timeout=timeout)
                    if resp.status_code == 200:
                        return resp, p_url
                except Exception:
                    continue
        except Exception:
            pass
        raise first_err


def _parse_generic_web(url, session):
    """通用网页 HTML5 视频、Base64脱壳、MacCMS播放器、ev 加密流及同系列选集探测"""
    try:
        resp, used_proxy = _fetch_with_proxy_fallback(session, url, timeout=10)
        html = _unwrap_base64_document_write(resp.text)
        final_page_url = resp.url or url

        m_title = re.search(r'<title>([^<]+)</title>', html, re.I)
        title = m_title.group(1).strip() if m_title else "在线网络视频"
        title = re.sub(r'[\r\n\t]+', ' ', title).strip()

        series_info = _extract_generic_series(html, final_page_url, title)

        # 0. 提取嵌入的 MacCMS player_aaaa={...}
        p4_info = _extract_player_aaaa(html, final_page_url)
        if p4_info and p4_info.get("url"):
            if p4_info.get("title") and series_info:
                series_info["series_title"] = p4_info["title"]
            return {
                "success": True,
                "title": p4_info.get("title") or title.split(" - ")[0].strip() or title,
                "url": p4_info["url"],
                "media_type": p4_info["media_type"],
                "duration": 0,
                "resolution": "高清",
                "cover": p4_info.get("cover", ""),
                "headers": p4_info["headers"],
                "series": series_info,
                "used_proxy": used_proxy,
                "error": ""
            }

        # 1. 提取嵌入的 ev:{d,k} 加密媒体地址 (TanStack/SPA 视频站点)
        ev_info = _decode_embedded_ev_payload(html, final_page_url)
        if ev_info and ev_info.get("url"):
            dur_val = 0
            m_dur = re.search(r'"duration"\s*:\s*"PT(\d+)S"|duration\s*:\s*([\d\.]+)', html)
            if m_dur:
                try:
                    dur_val = int(float(m_dur.group(1) or m_dur.group(2)))
                except Exception:
                    pass
            return {
                "success": True,
                "title": title.split(" - ")[0].strip() or title,
                "url": ev_info["url"],
                "media_type": ev_info["media_type"],
                "duration": dur_val,
                "resolution": "高清",
                "headers": ev_info["headers"],
                "series": series_info,
                "used_proxy": used_proxy,
                "error": ""
            }

        # 2. 优先检索 M3U8 清单地址
        m_m3u8 = re.search(r'["\'](https?://[^"\']+\.m3u8(?:\?[^"\']*)?)["\']', html, re.I)
        if m_m3u8:
            return {
                "success": True,
                "title": title,
                "url": m_m3u8.group(1),
                "media_type": "m3u8",
                "duration": 0,
                "resolution": "自适应",
                "headers": {"Referer": final_page_url},
                "series": series_info,
                "used_proxy": used_proxy,
                "error": ""
            }

        # 3. 检索 HTML5 <video src="..."> 或 <source src="..."> 或音频标签
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
                "headers": {"Referer": final_page_url},
                "series": series_info,
                "used_proxy": used_proxy,
                "error": ""
            }

        m_audio = re.search(r'<audio[^>]+src=["\'](https?://[^"\']+\.(?:mp3|m4a|aac|wav|flac|ogg)[^"\']*)["\']', html, re.I)
        if m_audio:
            return {
                "success": True,
                "title": title,
                "url": m_audio.group(1),
                "media_type": "audio",
                "duration": 0,
                "resolution": "高音质",
                "headers": {"Referer": final_page_url},
                "series": series_info,
                "used_proxy": used_proxy,
                "error": ""
            }

        # StreamitVideoPlyr 异步流接口 (例如 huangguo123.com 等站点: streamApi + videoUid)
        m_sapi = re.search(r'var\s+streamApi\s*=\s*["\']([^"\']+)["\']', html)
        m_vuid = re.search(r'var\s+videoUid\s*=\s*["\']([^"\']+)["\']', html)
        if m_sapi and m_vuid:
            from urllib.parse import urljoin, quote
            ep_uid_m = re.search(r'var\s+currentEpisodeUid\s*=\s*["\']([^"\']*)["\']', html)
            api_base = urljoin(final_page_url, m_sapi.group(1))
            sep = "&" if "?" in api_base else "?"
            api_url = f"{api_base}{sep}video_uid={quote(m_vuid.group(1))}"
            if ep_uid_m and ep_uid_m.group(1):
                api_url += f"&episode_uid={quote(ep_uid_m.group(1))}"
            try:
                api_resp, _ = _fetch_with_proxy_fallback(session, api_url, timeout=12)
                if api_resp.status_code == 200:
                    j = api_resp.json()
                    plist = j.get("playlist") or []
                    if plist and isinstance(plist, list) and plist[0].get("url"):
                        s_url = str(plist[0]["url"]).strip()
                        u_type = str(plist[0].get("urlType") or "").lower()
                        m_type = "m3u8" if (u_type == "m3u8" or ".m3u8" in s_url.lower() or "/api/hls/" in s_url.lower()) else "video"
                        return {
                            "success": True,
                            "title": title,
                            "url": s_url,
                            "media_type": m_type,
                            "duration": 0,
                            "resolution": "高清",
                            "headers": {"Referer": final_page_url},
                            "series": series_info,
                            "used_proxy": used_proxy,
                            "error": "",
                        }
            except Exception:
                pass

        return {
            "success": False,
            "title": title,
            "url": "",
            "series": series_info,
            "used_proxy": used_proxy,
            "error": "未能在该网页中直接嗅探到公开媒体直链，请在浏览器中播放并使用配套扩展嗅探！"
        }

    except Exception as e:
        return {"success": False, "title": "", "url": "", "error": f"网页请求失败: {e}"}


def parse_series_collection(url: str, proxy: str = "", extra_headers: dict = None) -> dict:
    """
    独立探测输入链接关联的同系列 / 合集列表
    返回: {"success": bool, "series": dict or None, "single_result": dict, "error": str}
    """
    res = parse_video_url(url, proxy=proxy, extra_headers=extra_headers)
    series = res.get("series")
    if series and series.get("has_series") and series.get("episodes"):
        return {
            "success": True,
            "series": series,
            "single_result": res,
            "error": ""
        }
    return {
        "success": False,
        "series": None,
        "single_result": res,
        "error": res.get("error") or "未检测到该资源所属的合集或系列列表"
    }


def resolve_episode_media(ep: dict, proxy: str = "", extra_headers: dict = None) -> dict:
    """
    解析合集中的单集条目真实可下载直链
    支持直链、B站 bvid+cid 精确提取、番剧 ep_id、音频 sid 及通用网页二级解析
    """
    direct_url = (ep.get("url") or "").strip()
    if direct_url and any(ext in direct_url.lower() for ext in [".m3u8", ".mpd", ".mp4", ".flv", ".mp3", ".m4a"]):
        return {
            "success": True,
            "title": ep.get("title") or "episode",
            "url": direct_url,
            "audio_url": ep.get("audio_url") or "",
            "media_type": ep.get("media_type") or ("m3u8" if ".m3u8" in direct_url.lower() else "video"),
            "duration": ep.get("duration") or 0,
            "headers": extra_headers or {},
        }

    page_url = (ep.get("page_url") or "").strip()
    session = _build_session(page_url or "https://www.bilibili.com", proxy=proxy, extra_headers=extra_headers)

    # B站精确 bvid + cid 极速直解析（无需重复请求 view 接口）
    if ep.get("bvid") and ep.get("cid"):
        headers_bili = {
            "Referer": "https://www.bilibili.com",
            "User-Agent": session.headers.get("User-Agent", "Mozilla/5.0")
        }
        stream_info = _fetch_bili_playurl(
            session,
            ep["bvid"],
            int(ep["cid"]),
            headers_bili,
            is_pgc=bool(ep.get("is_pgc")),
            ep_id=int(ep.get("ep_id") or 0)
        )
        if stream_info.get("success"):
            return {
                "success": True,
                "title": ep.get("title") or ep["bvid"],
                "url": stream_info["url"],
                "audio_url": stream_info.get("audio_url", ""),
                "media_type": stream_info.get("media_type", "bili_dash"),
                "duration": ep.get("duration") or 0,
                "resolution": stream_info.get("resolution", "1080P"),
                "headers": headers_bili,
            }

    # B站音频专辑单曲 sid 精确提取
    if ep.get("audio_sid"):
        headers_bili = {
            "Referer": "https://www.bilibili.com",
            "User-Agent": session.headers.get("User-Agent", "Mozilla/5.0")
        }
        a_url = _fetch_bili_audio_stream(session, ep["audio_sid"], headers_bili)
        if a_url:
            return {
                "success": True,
                "title": ep.get("title") or f"au{ep['audio_sid']}",
                "url": a_url,
                "audio_url": "",
                "media_type": "audio",
                "duration": ep.get("duration") or 0,
                "resolution": "高品质音频",
                "headers": headers_bili,
            }

    if page_url:
        return parse_video_url(page_url, proxy=proxy, extra_headers=extra_headers)

    return {"success": False, "error": "缺少有效的单集链接信息"}


def submit_series_downloads(
    episodes: list,
    series_title: str = "合集系列",
    save_dir: str = "",
    create_subdir: bool = True,
    add_index_prefix: bool = True,
    proxy: str = "",
    extra_headers: dict = None,
    on_progress=None,
    on_done=None
):
    """
    后台异步批量解析合集内选定剧集并依次推入 task_manager 下载队列
    带温和请求节流，防止短时间高并发触发站点 412 风控拦截
    """
    from .task_manager import task_manager

    base_dir = (save_dir or "").strip() or config.get("save_dir")
    safe_series = re.sub(r'[\\/*?:"<>|]', '_', (series_title or "合集系列")).strip()[:80] or "合集系列"
    target_dir = os.path.join(base_dir, safe_series) if create_subdir else base_dir
    os.makedirs(target_dir, exist_ok=True)

    total = len(episodes)

    def _worker():
        success_count = 0
        failed_list = []

        series_base = re.sub(r'[\\/*?:"<>|]', '_', (series_title or "").strip()).strip()[:50]
        for idx, ep in enumerate(episodes):
            raw_title = (ep.get("title") or f"第{idx + 1}集").strip()
            ep_idx = int(ep.get("index") or (idx + 1))
            clean_ep = re.sub(r'[\\/*?:"<>|]', '_', raw_title).strip()
            if series_base and series_base.lower() not in clean_ep.lower():
                ep_part = f"{ep_idx:02d}_{clean_ep}" if add_index_prefix else clean_ep
                final_title = f"{series_base} - {ep_part}"
            else:
                prefix = f"{ep_idx:02d}_" if add_index_prefix else ""
                final_title = f"{prefix}{clean_ep}"

            if on_progress:
                try:
                    on_progress(idx + 1, total, final_title)
                except Exception:
                    pass

            try:
                res = resolve_episode_media(ep, proxy=proxy, extra_headers=extra_headers)
                if res.get("success") and res.get("url"):
                    hdrs = dict(extra_headers or {})
                    hdrs.update(res.get("headers") or {})
                    if ep.get("page_url") and "Referer" not in hdrs:
                        hdrs["Referer"] = ep["page_url"]

                    task_info = {
                        "url": res["url"],
                        "audio_url": res.get("audio_url", ""),
                        "title": final_title,
                        "save_name": final_title,
                        "save_dir": target_dir,
                        "media_type": res.get("media_type") or ep.get("media_type") or "video",
                        "resolution": res.get("resolution") or ep.get("resolution") or "",
                        "duration": res.get("duration") or ep.get("duration") or 0,
                        "format": "m4a" if res.get("media_type") == "audio" else "mp4",
                        "headers": hdrs,
                        "pageUrl": ep.get("page_url", ""),
                        "referer": ep.get("page_url", ""),
                        "thread_count": config.get("max_threads_per_task", 16),
                        "proxy": res.get("used_proxy") or proxy or config.get_effective_proxy(),
                    }
                    task_manager.add_task(task_info, auto_start=True)
                    success_count += 1
                else:
                    failed_list.append(f"{final_title}: {res.get('error') or '未能直接提取直链'}")
            except Exception as ex:
                failed_list.append(f"{final_title}: {ex}")

            if idx < total - 1:
                time.sleep(0.25)

        if on_done:
            try:
                on_done(success_count, failed_list, target_dir)
            except Exception:
                pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return target_dir

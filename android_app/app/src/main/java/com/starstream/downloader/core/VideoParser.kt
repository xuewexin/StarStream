package com.starstream.downloader.core

import android.content.Context
import android.util.Base64
import android.webkit.CookieManager
import kotlinx.coroutines.*
import okhttp3.Request
import org.json.JSONObject
import java.net.URL
import java.net.URLDecoder
import java.util.UUID

/**
 * 星流安卓全网解析与同系列/合集提取引擎 (完整移植并增强 PC 端 video_parser.py)
 * 修复要点：
 * 1. 自动维护并合并会话 Cookie（含 WebView 登录 Cookie 与 B站 buvid3 SPI 凭证），彻底解决 HTTP 412 / -352 风控解析失败
 * 2. B站支持 window.__INITIAL_STATE__ / window.__playinfo__ HTML 内嵌直提兜底 + av号/b23短链/移动端链接归一化 + 音频单曲/歌单
 * 3. 支持直链、抖音/TikTok、快手、小红书、MacCMS player_aaaa、ev加密、StreamitVideoPlyr、通用 HTML5 与转义 M3U8/MP4
 */
object VideoParser {

    private const val UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    private const val MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"

    private fun mergeCookieStrings(vararg cookieStrings: String?): String {
        val jar = linkedMapOf<String, String>()
        for (raw in cookieStrings) {
            if (raw.isNullOrBlank()) continue
            raw.split(";").forEach { part ->
                val idx = part.indexOf('=')
                if (idx > 0) {
                    val k = part.substring(0, idx).trim()
                    val v = part.substring(idx + 1).trim()
                    if (k.isNotEmpty() && v.isNotEmpty()) jar[k] = v
                }
            }
        }
        return jar.entries.joinToString("; ") { "${it.key}=${it.value}" }
    }

    private fun readWebViewCookie(url: String): String {
        return try {
            CookieManager.getInstance().getCookie(url) ?: ""
        } catch (_: Throwable) {
            ""
        }
    }

    private data class HttpFetchResult(
        val code: Int,
        val finalUrl: String,
        val body: String,
        val mergedCookies: String
    )

    private fun httpGetWithCookies(
        url: String,
        headers: MutableMap<String, String>,
        extraHeaders: Map<String, String> = emptyMap()
    ): HttpFetchResult {
        val client = HttpClientProvider.getClient()
        var currentUrl = url
        var cookieStr = mergeCookieStrings(headers["Cookie"], readWebViewCookie(url))

        // 最多手动跟踪 5 跳重定向并收集每跳 Set-Cookie（规避无状态请求丢 Cookie 导致 412）
        for (hop in 0..5) {
            val reqCookie = mergeCookieStrings(cookieStr, readWebViewCookie(currentUrl))
            val builder = Request.Builder()
                .url(currentUrl)
                .header("User-Agent", headers["User-Agent"] ?: UA)
                .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8")
                .header("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
            extraHeaders.forEach { (k, v) -> if (v.isNotBlank() && !k.equals("Cookie", true)) builder.header(k, v) }
            headers.forEach { (k, v) -> if (v.isNotBlank() && !k.equals("Cookie", true) && !k.equals("User-Agent", true)) builder.header(k, v) }
            if (reqCookie.isNotBlank()) builder.header("Cookie", reqCookie)

            var nextRedirectUrl: String? = null
            var result: HttpFetchResult? = null
            client.newBuilder().followRedirects(false).followSslRedirects(false).build()
                .newCall(builder.build()).execute().use { resp ->
                    val setCookies = resp.headers("Set-Cookie")
                        .mapNotNull { it.substringBefore(";").takeIf { kv -> kv.contains("=") } }
                        .joinToString("; ")
                    cookieStr = mergeCookieStrings(cookieStr, setCookies)
                    if (cookieStr.isNotBlank()) headers["Cookie"] = cookieStr

                    val loc = resp.header("Location")
                    if (resp.code in 300..399 && !loc.isNullOrBlank()) {
                        nextRedirectUrl = URL(URL(currentUrl), loc).toString()
                    } else {
                        val body = resp.body?.string() ?: ""
                        result = HttpFetchResult(resp.code, currentUrl, body, cookieStr)
                    }
                }
            if (result != null) return result!!
            if (nextRedirectUrl != null) {
                currentUrl = nextRedirectUrl!!
            } else {
                break
            }
        }
        return HttpFetchResult(0, currentUrl, "", cookieStr)
    }

    private fun ensureBiliSessionCookies(biliHeaders: MutableMap<String, String>) {
        val cur = biliHeaders["Cookie"] ?: ""
        if (cur.contains("buvid3=")) return
        // 通过 B站官方指纹 SPI 接口或首页种入 buvid3/buvid4 防止 412
        try {
            val res = httpGetWithCookies("https://api.bilibili.com/x/frontend/finger/spi", biliHeaders)
            val data = JSONObject(res.body).optJSONObject("data")
            val b3 = data?.optString("b_3", "") ?: ""
            val b4 = data?.optString("b_4", "") ?: ""
            if (b3.isNotBlank()) {
                biliHeaders["Cookie"] = mergeCookieStrings(biliHeaders["Cookie"], "buvid3=$b3; buvid4=$b4; b_nut=${System.currentTimeMillis() / 1000}")
                return
            }
        } catch (_: Exception) {}
        try {
            httpGetWithCookies("https://www.bilibili.com/", biliHeaders)
        } catch (_: Exception) {}
    }

    fun parseVideoUrl(rawInput: String, extraHeaders: Map<String, String> = emptyMap()): ParseResult {
        val trimmed = rawInput.trim()
        val mUrl = Regex("https?://[^\\s<>\"'\\]\\）】]+").find(trimmed)
        val targetUrl = mUrl?.value ?: trimmed
        if (!targetUrl.startsWith("http")) {
            return ParseResult(false, error = "未检测到有效的 http/https 链接")
        }

        val lowerPath = targetUrl.lowercase().substringBefore("?")
        if (lowerPath.contains(".m3u8") || lowerPath.contains(".mpd")) {
            return ParseResult(true, title = "流媒体视频", url = targetUrl, mediaType = "m3u8", resolution = "自适应", headers = extraHeaders.toMutableMap())
        }
        if (listOf(".mp4", ".flv", ".webm", ".mkv", ".ts", ".mov").any { lowerPath.endsWith(it) }) {
            return ParseResult(true, title = "直链视频", url = targetUrl, mediaType = "video", resolution = "原画", headers = extraHeaders.toMutableMap())
        }
        if (listOf(".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus").any { lowerPath.endsWith(it) }) {
            return ParseResult(true, title = "直链音频", url = targetUrl, mediaType = "audio", resolution = "高音质", headers = extraHeaders.toMutableMap())
        }

        val host = try { URL(targetUrl).host.lowercase() } catch (_: Exception) { "" }
        return when {
            host.contains("bilibili.com") || host.contains("b23.tv") -> parseBilibili(targetUrl, extraHeaders)
            host.contains("douyin.com") || host.contains("iesdouyin.com") -> parseDouyin(targetUrl)
            host.contains("kuaishou.com") || host.contains("chenzhongtech.com") -> parseKuaishou(targetUrl)
            host.contains("xiaohongshu.com") || host.contains("xhslink.com") -> parseXiaohongshu(targetUrl)
            else -> parseGenericWeb(targetUrl, extraHeaders)
        }
    }

    private fun parseBilibili(url: String, extraHeaders: Map<String, String>): ParseResult {
        return try {
            val biliHeaders = mutableMapOf(
                "User-Agent" to (extraHeaders["User-Agent"] ?: UA),
                "Referer" to "https://www.bilibili.com/",
                "Origin" to "https://www.bilibili.com"
            )
            val initCookie = mergeCookieStrings(
                extraHeaders["Cookie"],
                readWebViewCookie("https://www.bilibili.com"),
                readWebViewCookie(url)
            )
            if (initCookie.isNotBlank()) biliHeaders["Cookie"] = initCookie
            ensureBiliSessionCookies(biliHeaders)

            // 将移动端 m.bilibili.com 规范化为桌面域名，同时跟进 b23.tv 短链并保留 Cookie
            var reqUrl = url.replace("://m.bilibili.com/", "://www.bilibili.com/")
            val pageRes = httpGetWithCookies(reqUrl, biliHeaders)
            var finalUrl = pageRes.finalUrl.replace("://m.bilibili.com/", "://www.bilibili.com/")
            var pageHtml = pageRes.body
            if (finalUrl != pageRes.finalUrl) {
                val desktopRes = httpGetWithCookies(finalUrl, biliHeaders)
                finalUrl = desktopRes.finalUrl
                if (desktopRes.body.isNotBlank()) pageHtml = desktopRes.body
            }

            if (finalUrl.contains("/bangumi/play/")) {
                parseBiliBangumi(finalUrl, biliHeaders)?.let { return it }
            }
            if (finalUrl.contains("/audio/")) {
                parseBiliAudio(finalUrl, biliHeaders)?.let { return it }
            }

            // 支持 BV 号或 av 号
            var bvid = Regex("(BV[a-zA-Z0-9]+)").find(finalUrl)?.groupValues?.get(1) ?: ""
            val aidMatch = Regex("/video/av(\\d+)").find(finalUrl)
            if (bvid.isBlank() && aidMatch == null) {
                return parseGenericWeb(finalUrl, biliHeaders)
            }

            val pMatch = Regex("[?&]p=(\\d+)").find(finalUrl)
            val targetP = (pMatch?.groupValues?.get(1)?.toIntOrNull() ?: 1).coerceAtLeast(1)

            // 1. 尝试调用官方 view API（带上已收集的 buvid3/登录 Cookie）
            var vData: JSONObject? = null
            var apiErrorMsg = ""
            val viewApi = if (bvid.isNotBlank()) {
                "https://api.bilibili.com/x/web-interface/view?bvid=$bvid"
            } else {
                "https://api.bilibili.com/x/web-interface/view?aid=${aidMatch!!.groupValues[1]}"
            }
            try {
                val viewRes = httpGetWithCookies(viewApi, biliHeaders)
                if (viewRes.body.trimStart().startsWith("{")) {
                    val viewJson = JSONObject(viewRes.body)
                    if (viewJson.optInt("code") == 0) {
                        vData = viewJson.optJSONObject("data")
                        if (bvid.isBlank() && vData != null) bvid = vData.optString("bvid", "")
                    } else {
                        apiErrorMsg = viewJson.optString("message")
                    }
                }
            } catch (_: Exception) {}

            // 2. HTML 内嵌 window.__INITIAL_STATE__ 兜底（当 API 412/限流时直接从网页源码取）
            if (vData == null && pageHtml.contains("videoData")) {
                extractJsonVar(pageHtml, "window.__INITIAL_STATE__")?.optJSONObject("videoData")?.let {
                    vData = it
                    if (bvid.isBlank()) bvid = it.optString("bvid", "")
                }
            }

            var title = vData?.optString("title", "")?.ifBlank { "bilibili_$bvid" }
                ?: Regex("<title>([^<]+)</title>").find(pageHtml)?.groupValues?.get(1)?.replace("_哔哩哔哩_bilibili", "")?.trim()
                ?: "bilibili_$bvid"
            var cid = vData?.optLong("cid", 0L) ?: 0L
            var duration = vData?.optInt("duration", 0) ?: 0
            val cover = vData?.optString("pic", "") ?: ""

            val pages = vData?.optJSONArray("pages")
            if (pages != null && targetP <= pages.length()) {
                val pObj = pages.getJSONObject(targetP - 1)
                cid = pObj.optLong("cid", cid)
                duration = pObj.optInt("duration", duration)
                if (pages.length() > 1) {
                    val partName = pObj.optString("part", "")
                    if (partName.isNotBlank()) title = "$title - P$targetP $partName"
                }
            }

            val seriesInfo = vData?.let { extractBiliSeries(it, bvid, targetP) }

            // 3. 获取音视频流：优先 playurl API，其次 HTML window.__playinfo__ 内嵌直提
            var stream: Triple<String, String, String>? = if (bvid.isNotBlank() && cid > 0L) {
                fetchBiliPlayUrl(bvid, cid, biliHeaders)
            } else null

            if (stream == null && pageHtml.contains("__playinfo__")) {
                val playInfo = extractJsonVar(pageHtml, "window.__playinfo__")
                val dashObj = playInfo?.optJSONObject("data")?.optJSONObject("dash")
                    ?: playInfo?.optJSONObject("result")?.optJSONObject("dash")
                if (dashObj != null) {
                    stream = pickBestDashPair(dashObj)
                } else {
                    val durlArr = playInfo?.optJSONObject("data")?.optJSONArray("durl")
                    if (durlArr != null && durlArr.length() > 0) {
                        val u0 = durlArr.getJSONObject(0).optString("url")
                        if (u0.startsWith("http")) stream = Triple(u0, "", "720P")
                    }
                }
            }

            if (stream != null) {
                return ParseResult(
                    success = true,
                    title = title,
                    url = stream.first,
                    audioUrl = stream.second,
                    mediaType = if (stream.second.isNotBlank()) "bili_dash" else "video",
                    durationSec = duration,
                    resolution = stream.third,
                    coverUrl = cover,
                    headers = biliHeaders,
                    series = seriesInfo
                )
            }
            val errDetail = if (apiErrorMsg.isNotBlank()) "B站接口($apiErrorMsg)" else "未能提取到 B站视频流"
            ParseResult(false, title = title, series = seriesInfo, error = "$errDetail，请尝试使用右上角「浏览器」打开该页播放即可自动嗅探！")
        } catch (e: Exception) {
            ParseResult(false, error = "B站解析异常: ${e.message}")
        }
    }

    private fun extractJsonVar(html: String, varName: String): JSONObject? {
        val idx = html.indexOf(varName)
        if (idx == -1) return null
        val start = html.indexOf('{', idx)
        if (start == -1) return null
        var depth = 0
        var inStr = false
        var esc = false
        val limit = minOf(html.length, start + 350_000)
        for (i in start until limit) {
            val ch = html[i]
            if (esc) { esc = false; continue }
            if (ch == '\\' && inStr) { esc = true; continue }
            if (ch == '"') { inStr = !inStr; continue }
            if (!inStr) {
                if (ch == '{') depth++
                else if (ch == '}') {
                    depth--
                    if (depth == 0) {
                        return try { JSONObject(html.substring(start, i + 1)) } catch (_: Exception) { null }
                    }
                }
            }
        }
        return null
    }

    private fun pickBestDashPair(dash: JSONObject): Triple<String, String, String>? {
        val videos = dash.optJSONArray("video") ?: return null
        if (videos.length() == 0) return null
        val vList = (0 until videos.length()).map { videos.getJSONObject(it) }
        // 优先挑选 H.264(avc1) 或 HEVC(hev1) 兼容度最高的最高清晰度轨，避免部分设备硬解异常无画面
        val avcOrHevc = vList.filter {
            val c = it.optString("codecs").lowercase()
            c.startsWith("avc") || c.startsWith("hev") || c.startsWith("hvc")
        }
        val poolV = if (avcOrHevc.isNotEmpty()) avcOrHevc else vList
        val bestV = poolV.maxByOrNull { it.optInt("id") } ?: vList[0]
        val vUrl = bestV.optString("baseUrl").ifBlank { bestV.optString("base_url") }
        if (vUrl.isBlank()) return null

        var aUrl = ""
        val audios = dash.optJSONArray("audio")
        if (audios != null && audios.length() > 0) {
            val candidates = (0 until audios.length()).map { audios.getJSONObject(it) }
            val aacOnly = candidates.filter { obj ->
                val c = obj.optString("codecs").lowercase()
                val cidA = obj.optInt("id")
                c.startsWith("mp4a") || cidA in setOf(30216, 30232, 30280)
            }
            val bestA = (if (aacOnly.isNotEmpty()) aacOnly else candidates).maxByOrNull { it.optInt("id") }
            if (bestA != null) {
                aUrl = bestA.optString("baseUrl").ifBlank { bestA.optString("base_url") }
            }
        }
        val qId = bestV.optInt("id", 80)
        val qName = when {
            qId >= 120 -> "4K"
            qId == 116 -> "1080P60"
            qId == 112 -> "1080P+"
            qId >= 80 -> "1080P"
            qId >= 64 -> "720P"
            else -> "480P"
        }
        return Triple(vUrl, aUrl, qName)
    }

    private fun fetchBiliPlayUrl(bvid: String, cid: Long, headers: MutableMap<String, String>, isPgc: Boolean = false, epId: Long = 0L): Triple<String, String, String>? {
        val dashApi = if (isPgc && epId > 0) {
            "https://api.bilibili.com/pgc/player/web/playurl?ep_id=$epId&cid=$cid&qn=80&fnval=16&fourk=1"
        } else {
            "https://api.bilibili.com/x/player/playurl?bvid=$bvid&cid=$cid&qn=80&fnval=16&fnver=0&fourk=1"
        }
        try {
            val res = httpGetWithCookies(dashApi, headers)
            if (res.body.trimStart().startsWith("{")) {
                val json = JSONObject(res.body)
                if (json.optInt("code") == 0) {
                    val dataObj = if (isPgc) json.optJSONObject("result") else json.optJSONObject("data")
                    val dash = dataObj?.optJSONObject("dash")
                    if (dash != null) {
                        pickBestDashPair(dash)?.let { return it }
                    }
                    val durl = dataObj?.optJSONArray("durl")
                    if (durl != null && durl.length() > 0) {
                        val u0 = durl.getJSONObject(0).optString("url")
                        if (u0.startsWith("http")) return Triple(u0, "", "720P")
                    }
                }
            }
        } catch (_: Exception) {}

        // 兜底 HTML5 MP4 单流接口 (high_quality=1&platform=html5)
        val h5Api = if (isPgc && epId > 0) {
            "https://api.bilibili.com/pgc/player/web/playurl?ep_id=$epId&cid=$cid&qn=80&fnval=1&platform=html5&high_quality=1"
        } else {
            "https://api.bilibili.com/x/player/playurl?bvid=$bvid&cid=$cid&qn=80&fnval=1&platform=html5&high_quality=1"
        }
        try {
            val res = httpGetWithCookies(h5Api, headers)
            if (res.body.trimStart().startsWith("{")) {
                val json = JSONObject(res.body)
                if (json.optInt("code") == 0) {
                    val dataObj = if (isPgc) json.optJSONObject("result") else json.optJSONObject("data")
                    val durl = dataObj?.optJSONArray("durl")
                    if (durl != null && durl.length() > 0) {
                        val u0 = durl.getJSONObject(0).optString("url")
                        if (u0.startsWith("http")) return Triple(u0, "", "720P+")
                    }
                }
            }
        } catch (_: Exception) {}

        return null
    }

    private fun extractBiliSeries(vData: JSONObject, bvid: String, curP: Int): SeriesInfo? {
        val baseTitle = vData.optString("title", "B站合集")
        val pages = vData.optJSONArray("pages")
        if (pages != null && pages.length() > 1) {
            val eps = mutableListOf<SeriesEpisode>()
            for (i in 0 until pages.length()) {
                val p = pages.getJSONObject(i)
                val pNum = p.optInt("page", i + 1)
                eps.add(
                    SeriesEpisode(
                        index = i + 1,
                        title = p.optString("part", "P$pNum"),
                        pageUrl = "https://www.bilibili.com/video/$bvid?p=$pNum",
                        durationSec = p.optInt("duration", 0),
                        bvid = bvid,
                        cid = p.optLong("cid", 0L),
                        mediaType = "bili_dash"
                    )
                )
            }
            return SeriesInfo(baseTitle, "bili_pages", eps.size, (curP - 1).coerceIn(0, eps.size - 1), "https://www.bilibili.com/video/$bvid", eps)
        }

        val ugc = vData.optJSONObject("ugc_season")
        val sections = ugc?.optJSONArray("sections")
        if (sections != null && sections.length() > 0) {
            val eps = mutableListOf<SeriesEpisode>()
            var curIdx = 0
            var counter = 0
            for (s in 0 until sections.length()) {
                val epArr = sections.getJSONObject(s).optJSONArray("episodes") ?: continue
                for (i in 0 until epArr.length()) {
                    counter++
                    val ep = epArr.getJSONObject(i)
                    val epBvid = ep.optString("bvid", "")
                    val arc = ep.optJSONObject("arc")
                    if (epBvid == bvid) curIdx = eps.size
                    eps.add(
                        SeriesEpisode(
                            index = counter,
                            title = ep.optString("title").ifBlank { arc?.optString("title") ?: "第${counter}集" },
                            pageUrl = "https://www.bilibili.com/video/$epBvid",
                            durationSec = arc?.optInt("duration", 0) ?: 0,
                            bvid = epBvid,
                            cid = ep.optLong("cid", 0L),
                            mediaType = "bili_dash"
                        )
                    )
                }
            }
            if (eps.size > 1) {
                return SeriesInfo(ugc.optString("title", baseTitle), "bili_season", eps.size, curIdx, "https://www.bilibili.com/video/$bvid", eps)
            }
        }
        return null
    }

    private fun parseBiliBangumi(finalUrl: String, headers: MutableMap<String, String>): ParseResult? {
        val mEp = Regex("/ep(\\d+)").find(finalUrl)
        val mSs = Regex("/ss(\\d+)").find(finalUrl)
        if (mEp == null && mSs == null) return null
        val param = if (mEp != null) "ep_id=${mEp.groupValues[1]}" else "season_id=${mSs!!.groupValues[1]}"
        return try {
            val txt = httpGetWithCookies("https://api.bilibili.com/pgc/view/web/season?$param", headers).body
            val json = JSONObject(txt)
            if (json.optInt("code") != 0) return null
            val res = json.getJSONObject("result")
            val seasonTitle = res.optString("season_title").ifBlank { res.optString("title", "B站番剧") }
            val epsRaw = res.optJSONArray("episodes") ?: return null
            if (epsRaw.length() == 0) return null

            val targetEpId = mEp?.groupValues?.get(1)?.toLongOrNull() ?: 0L
            var curIdx = 0
            val eps = mutableListOf<SeriesEpisode>()
            for (i in 0 until epsRaw.length()) {
                val ep = epsRaw.getJSONObject(i)
                val epId = ep.optLong("id", 0L)
                if (targetEpId > 0 && epId == targetEpId) curIdx = i
                val rawDur = ep.optInt("duration", 0)
                val durSec = if (rawDur > 10000) rawDur / 1000 else rawDur
                eps.add(
                    SeriesEpisode(
                        index = i + 1,
                        title = ep.optString("share_copy").ifBlank { ep.optString("long_title").ifBlank { "第${i + 1}话" } },
                        pageUrl = ep.optString("link").ifBlank { "https://www.bilibili.com/bangumi/play/ep$epId" },
                        durationSec = durSec,
                        bvid = ep.optString("bvid", ""),
                        cid = ep.optLong("cid", 0L),
                        epId = epId,
                        isPgc = true,
                        mediaType = "bili_dash"
                    )
                )
            }
            val curEp = eps[curIdx]
            val stream = fetchBiliPlayUrl(curEp.bvid, curEp.cid, headers, isPgc = true, epId = curEp.epId)
            val series = if (eps.size > 1) SeriesInfo(seasonTitle, "bili_bangumi", eps.size, curIdx, finalUrl, eps) else null
            if (stream != null) {
                ParseResult(true, curEp.title, stream.first, stream.second, "bili_dash", curEp.durationSec, stream.third, res.optString("cover", ""), HashMap(headers), series)
            } else {
                ParseResult(false, title = seasonTitle, series = series, error = "该番剧需大会员或登录凭证，已识别全集清单，可在内置浏览器登录后嗅探")
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun parseBiliAudio(finalUrl: String, headers: MutableMap<String, String>): ParseResult? {
        val mAm = Regex("/audio/am(\\d+)").find(finalUrl)
        val mAu = Regex("/audio/au(\\d+)").find(finalUrl)
        return try {
            if (mAm != null) {
                val menuId = mAm.groupValues[1]
                val infoRes = JSONObject(httpGetWithCookies("https://www.bilibili.com/audio/music-service-c/web/menu/info?sid=$menuId", headers).body)
                val songsRes = JSONObject(httpGetWithCookies("https://www.bilibili.com/audio/music-service-c/web/song/of-menu?sid=$menuId&pn=1&ps=100", headers).body)
                val menuTitle = infoRes.optJSONObject("data")?.optString("title")?.ifBlank { "B站音频歌单_$menuId" } ?: "B站音频歌单"
                val songs = songsRes.optJSONObject("data")?.optJSONArray("data") ?: return null
                if (songs.length() == 0) return null
                val eps = mutableListOf<SeriesEpisode>()
                for (i in 0 until songs.length()) {
                    val s = songs.getJSONObject(i)
                    val sid = s.optLong("id", 0L)
                    eps.add(
                        SeriesEpisode(
                            index = i + 1,
                            title = s.optString("title", "音频_$sid"),
                            pageUrl = "https://www.bilibili.com/audio/au$sid",
                            durationSec = s.optInt("duration", 0),
                            audioSid = sid,
                            mediaType = "audio"
                        )
                    )
                }
                val firstSid = eps[0].audioSid
                val firstUrl = fetchBiliAudioStream(firstSid, headers)
                val series = if (eps.size > 1) SeriesInfo(menuTitle, "bili_audio", eps.size, 0, finalUrl, eps) else null
                return if (firstUrl.isNotBlank()) {
                    ParseResult(true, eps[0].title, firstUrl, "", "audio", eps[0].durationSec, "高品质音频", "", HashMap(headers), series)
                } else {
                    ParseResult(false, title = menuTitle, series = series, error = "已提取音频歌单，请登录后再试或选集嗅探")
                }
            } else if (mAu != null) {
                val sid = mAu.groupValues[1].toLongOrNull() ?: return null
                val infoRes = JSONObject(httpGetWithCookies("https://www.bilibili.com/audio/music-service-c/web/song/info?sid=$sid", headers).body)
                val sData = infoRes.optJSONObject("data")
                val title = sData?.optString("title")?.ifBlank { "au$sid" } ?: "au$sid"
                val streamUrl = fetchBiliAudioStream(sid, headers)
                if (streamUrl.isNotBlank()) {
                    return ParseResult(true, title, streamUrl, "", "audio", sData?.optInt("duration", 0) ?: 0, "高品质音频", sData?.optString("cover", "") ?: "", HashMap(headers))
                }
            }
            null
        } catch (_: Exception) {
            null
        }
    }

    private fun fetchBiliAudioStream(sid: Long, headers: MutableMap<String, String>): String {
        return try {
            val res = httpGetWithCookies("https://www.bilibili.com/audio/music-service-c/web/url?sid=$sid&privilege=2&quality=2", headers).body
            val cdns = JSONObject(res).optJSONObject("data")?.optJSONArray("cdns")
            if (cdns != null && cdns.length() > 0) cdns.optString(0, "") else ""
        } catch (_: Exception) {
            ""
        }
    }

    private fun findDouyinPlayNode(obj: Any?): JSONObject? {
        when (obj) {
            is JSONObject -> {
                val vid = obj.optJSONObject("video")
                if (vid != null && vid.has("play_addr")) return obj
                val keys = obj.keys()
                while (keys.hasNext()) {
                    val found = findDouyinPlayNode(obj.opt(keys.next()))
                    if (found != null) return found
                }
            }
            is org.json.JSONArray -> {
                for (i in 0 until obj.length()) {
                    val found = findDouyinPlayNode(obj.opt(i))
                    if (found != null) return found
                }
            }
        }
        return null
    }

    private fun parseDouyin(url: String): ParseResult {
        return try {
            val mobHeaders = mutableMapOf("User-Agent" to MOBILE_UA)
            val pageRes = httpGetWithCookies(url, mobHeaders)
            val finalUrl = pageRes.finalUrl
            val vidMatch = Regex("/(?:video|note)/(\\d+)").find(finalUrl)
                ?: Regex("(?:item_ids|modal_id)=(\\d+)").find(finalUrl)
                ?: Regex("\"aweme_?[iI]d\"\\s*:\\s*\"(\\d+)\"").find(pageRes.body)

            // 引擎 0: 使用移动端 UA 访问 iesdouyin /share/video/{id}/ 解析内置 _ROUTER_DATA (绕过桌面端 JS WAF 验证)
            if (vidMatch != null) {
                val vid = vidMatch.groupValues[1]
                try {
                    val shareRes = httpGetWithCookies("https://www.iesdouyin.com/share/video/$vid/", mobHeaders)
                    val routerJson = extractJsonVar(shareRes.body, "_ROUTER_DATA")
                    val item = findDouyinPlayNode(routerJson)
                    if (item != null) {
                        val desc = item.optString("desc").trim().ifBlank { "douyin_$vid" }
                            .replace(Regex("[\\r\\n\\t]+"), " ").take(80)
                        val urlList = item.optJSONObject("video")?.optJSONObject("play_addr")?.optJSONArray("url_list")
                        if (urlList != null && urlList.length() > 0) {
                            var rawPlay = urlList.optString(0, "").replace("playwm", "play")
                            if (rawPlay.startsWith("http")) {
                                try {
                                    val resolved = httpGetWithCookies(rawPlay, mobHeaders)
                                    if (resolved.finalUrl.startsWith("http")) rawPlay = resolved.finalUrl
                                } catch (_: Exception) {}
                                val rawDur = item.optInt("duration", 0)
                                val durSec = if (rawDur > 1000) rawDur / 1000 else rawDur
                                return ParseResult(
                                    success = true,
                                    title = desc,
                                    url = rawPlay,
                                    mediaType = "video",
                                    durationSec = durSec,
                                    resolution = "1080P",
                                    headers = mutableMapOf("User-Agent" to MOBILE_UA, "Referer" to "https://www.douyin.com/")
                                )
                            }
                        }
                    }
                } catch (_: Exception) {}
            }

            val html = pageRes.body
            val title = Regex("<title>([^<]+)</title>").find(html)?.groupValues?.get(1)?.replace(" - 抖音", "")?.trim() ?: "抖音视频"
            val decoded = try { URLDecoder.decode(html, "UTF-8") } catch (_: Exception) { html }
            val mPlay = Regex("\"play_addr\":\\{\"uri\":\"[^\"]*\",\"url_list\":\\[\"([^\"]+)\"").find(decoded)
                ?: Regex("\"(https://[^\\s\"'<>]+\\.douyinvod\\.com/[^\\s\"'<>]+)\"").find(decoded)
            if (mPlay != null) {
                val rawUrl = mPlay.groupValues[1].replace("\\u0026", "&").replace("playwm", "play")
                ParseResult(true, title, rawUrl, mediaType = "video", resolution = "1080P", headers = mutableMapOf("User-Agent" to MOBILE_UA, "Referer" to "https://www.douyin.com/"))
            } else {
                ParseResult(false, title = title, error = "NEED_WEBVIEW:抖音当前链接启用了动态 JS 验证")
            }
        } catch (e: Exception) {
            ParseResult(false, error = "抖音解析失败: ${e.message}")
        }
    }

    private fun parseKuaishou(url: String): ParseResult {
        return try {
            val h = mutableMapOf<String, String>()
            val pageRes = httpGetWithCookies(url, h)
            val html = pageRes.body
            val mVid = Regex("\"(?:photoUrl|url)\":\"(https?://[^\"]+\\.mp4[^\"]*)\"").find(html)
            if (mVid != null) {
                ParseResult(true, "快手视频", mVid.groupValues[1].replace("\\u0026", "&"), mediaType = "video", resolution = "高清", headers = mutableMapOf("Referer" to "https://www.kuaishou.com/"))
            } else {
                parseGenericWeb(pageRes.finalUrl, h)
            }
        } catch (e: Exception) {
            ParseResult(false, error = "快手解析失败: ${e.message}")
        }
    }

    private fun parseXiaohongshu(url: String): ParseResult {
        return try {
            val h = mutableMapOf<String, String>()
            val pageRes = httpGetWithCookies(url, h)
            val html = pageRes.body
            val mKey = Regex("originVideoKey\":\"([^\"]+)\"").find(html)
            if (mKey != null) {
                ParseResult(true, "小红书视频", "https://sns-video-bd.xhscdn.com/${mKey.groupValues[1]}", mediaType = "video", resolution = "高清", headers = mutableMapOf("Referer" to "https://www.xiaohongshu.com/"))
            } else {
                parseGenericWeb(pageRes.finalUrl, h)
            }
        } catch (e: Exception) {
            ParseResult(false, error = "小红书解析失败: ${e.message}")
        }
    }

    fun parseGenericWeb(url: String, extraHeaders: Map<String, String>): ParseResult {
        return try {
            val hdrs = extraHeaders.toMutableMap()
            val pageRes = httpGetWithCookies(url, hdrs)
            val finalUrl = pageRes.finalUrl
            val html = unwrapBase64DocumentWrite(pageRes.body)
            val unescapedHtml = html.replace("\\/", "/").replace("\\u002F", "/").replace("\\u0026", "&")
            val title = Regex("<title>([^<]+)</title>", RegexOption.IGNORE_CASE).find(html)?.groupValues?.get(1)?.replace(Regex("[\\r\\n\\t]+"), " ")?.trim() ?: "网页视频"
            val seriesInfo = extractGenericSeries(html, finalUrl, title)

            extractPlayerAaaa(html, finalUrl)?.let { p4 ->
                val finalTitle = p4.title.ifBlank { title.substringBefore(" - ").trim() }
                val refinedSeries = if (seriesInfo != null && p4.title.isNotBlank()) seriesInfo.copy(seriesTitle = p4.title) else seriesInfo
                return ParseResult(true, finalTitle, p4.url, mediaType = p4.mediaType, resolution = "高清", coverUrl = p4.coverUrl, headers = p4.headers, series = refinedSeries)
            }

            decodeEmbeddedEvPayload(html, finalUrl)?.let { ev ->
                return ParseResult(true, title.substringBefore(" - ").trim(), ev.url, mediaType = ev.mediaType, resolution = "高清", headers = ev.headers, series = seriesInfo)
            }

            val mM3u8 = Regex("[\"'](https?://[^\"'<>\\s]+\\.m3u8(?:\\?[^\"'<>\\s]*)?)[\"']", RegexOption.IGNORE_CASE).find(unescapedHtml)
            if (mM3u8 != null) {
                return ParseResult(true, title, mM3u8.groupValues[1], mediaType = "m3u8", resolution = "自适应", headers = mutableMapOf("Referer" to finalUrl), series = seriesInfo)
            }

            val mVid = Regex("<(?:video|source)[^>]+(?:src|data-src)=[\"'](https?://[^\"']+)[\"']", RegexOption.IGNORE_CASE).find(html)
                ?: Regex("property=[\"']og:video(?::url|:secure_url)?[\"'][^>]+content=[\"'](https?://[^\"']+)[\"']", RegexOption.IGNORE_CASE).find(html)
                ?: Regex("[\"'](https?://[^\"'<>\\s]+\\.(?:mp4|webm|mkv)(?:\\?[^\"'<>\\s]*)?)[\"']", RegexOption.IGNORE_CASE).find(unescapedHtml)
            if (mVid != null) {
                return ParseResult(true, title, mVid.groupValues[1], mediaType = "video", resolution = "高清", headers = mutableMapOf("Referer" to finalUrl), series = seriesInfo)
            }

            val mAud = Regex("<audio[^>]+src=[\"'](https?://[^\"']+)[\"']", RegexOption.IGNORE_CASE).find(html)
                ?: Regex("[\"'](https?://[^\"'<>\\s]+\\.(?:mp3|m4a|aac|flac)(?:\\?[^\"'<>\\s]*)?)[\"']", RegexOption.IGNORE_CASE).find(unescapedHtml)
            if (mAud != null) {
                return ParseResult(true, title, mAud.groupValues[1], mediaType = "audio", resolution = "高音质", headers = mutableMapOf("Referer" to finalUrl), series = seriesInfo)
            }

            val mSapi = Regex("var\\s+streamApi\\s*=\\s*[\"']([^\"']+)[\"']").find(html)
            val mVuid = Regex("var\\s+videoUid\\s*=\\s*[\"']([^\"']+)[\"']").find(html)
            if (mSapi != null && mVuid != null) {
                try {
                    val epUid = Regex("var\\s+currentEpisodeUid\\s*=\\s*[\"']([^\"']*)[\"']").find(html)?.groupValues?.get(1).orEmpty()
                    val apiBase = java.net.URI(finalUrl).resolve(mSapi.groupValues[1]).toString()
                    val sep = if (apiBase.contains("?")) "&" else "?"
                    var apiUrl = "$apiBase${sep}video_uid=${java.net.URLEncoder.encode(mVuid.groupValues[1], "UTF-8")}"
                    if (epUid.isNotBlank()) apiUrl += "&episode_uid=${java.net.URLEncoder.encode(epUid, "UTF-8")}"
                    val apiBody = httpGetWithCookies(apiUrl, hdrs, mapOf("Referer" to finalUrl)).body
                    val obj = JSONObject(apiBody)
                    val plist = obj.optJSONArray("playlist")
                    if (plist != null && plist.length() > 0) {
                        val first = plist.getJSONObject(0)
                        val sUrl = first.optString("url")
                        if (sUrl.startsWith("http")) {
                            val uType = first.optString("urlType").lowercase()
                            val mType = if (uType == "m3u8" || sUrl.lowercase().contains(".m3u8") || sUrl.lowercase().contains("/api/hls/")) "m3u8" else "video"
                            return ParseResult(true, title, sUrl, mediaType = mType, resolution = "高清", headers = mutableMapOf("Referer" to finalUrl), series = seriesInfo)
                        }
                    }
                } catch (_: Exception) {}
            }

            ParseResult(false, title = title, series = seriesInfo, error = if (seriesInfo != null) "已识别合集共 ${seriesInfo.total} 集，可选集批量爬取！" else "该网页通过 JS 动态加载加密流，点击「在内置浏览器中打开」播放即可自动嗅探捕获！")
        } catch (e: Exception) {
            ParseResult(false, error = "网页请求失败: ${e.message}")
        }
    }

    private fun unwrapBase64DocumentWrite(html: String): String {
        if (!html.contains("document.write")) return html
        val m = Regex("<script[^>]*>\\s*var\\s+[a-zA-Z_]\\w*\\s*=\\s*[\"']([A-Za-z0-9+/=]{200,})[\"']").find(html) ?: return html
        return try {
            var raw = String(Base64.decode(m.groupValues[1], Base64.DEFAULT), Charsets.UTF_8)
            raw = raw.replace("\\/", "/").replace("\\\"", "\"").replace("\\\\", "\\")
            if (raw.startsWith("\"") && raw.endsWith("\"")) raw = raw.substring(1, raw.length - 1)
            raw = Regex("\\\\u([0-9a-fA-F]{4})").replace(raw) { mr -> mr.groupValues[1].toInt(16).toChar().toString() }
            if (raw.contains("<html", true) || raw.contains("player_aaaa") || raw.contains("<a ", true)) raw else html
        } catch (_: Exception) {
            html
        }
    }

    private fun extractPlayerAaaa(html: String, pageUrl: String): ParseResult? {
        val idx = html.indexOf("player_aaaa")
        if (idx == -1) return null
        val start = html.indexOf('{', idx)
        if (start == -1) return null
        var depth = 0
        var inStr = false
        var esc = false
        var end = -1
        for (i in start until minOf(html.length, start + 8000)) {
            val ch = html[i]
            if (esc) { esc = false; continue }
            if (ch == '\\' && inStr) { esc = true; continue }
            if (ch == '"') { inStr = !inStr; continue }
            if (!inStr) {
                if (ch == '{') depth++
                else if (ch == '}') {
                    depth--
                    if (depth == 0) { end = i + 1; break }
                }
            }
        }
        if (end == -1) return null
        return try {
            val obj = JSONObject(html.substring(start, end))
            var vUrl = obj.optString("url", "").trim()
            if (vUrl.isNotEmpty() && !vUrl.startsWith("http") && obj.optInt("encrypt") == 1) {
                vUrl = URLDecoder.decode(vUrl, "UTF-8")
            } else if (vUrl.isNotEmpty() && !vUrl.startsWith("http") && obj.optInt("encrypt") == 2) {
                vUrl = URLDecoder.decode(String(Base64.decode(vUrl, Base64.DEFAULT), Charsets.UTF_8), "UTF-8")
            }
            if (vUrl.startsWith("http")) {
                val vod = obj.optJSONObject("vod_data")
                val u = URL(pageUrl)
                ParseResult(
                    success = true,
                    title = vod?.optString("vod_name", "")?.trim() ?: "",
                    url = vUrl,
                    mediaType = if (vUrl.lowercase().contains("m3u8")) "m3u8" else "video",
                    coverUrl = vod?.optString("vod_pic", "")?.trim() ?: "",
                    headers = mutableMapOf("Referer" to pageUrl, "Origin" to "${u.protocol}://${u.host}")
                )
            } else null
        } catch (_: Exception) {
            null
        }
    }

    private fun decodeEmbeddedEvPayload(html: String, pageUrl: String): ParseResult? {
        val m = Regex("ev:.*?\\{d:\\s*[\"']([^\"']+)[\"']\\s*,\\s*k:\\s*(\\d+)\\}").find(html) ?: return null
        return try {
            val rawBytes = Base64.decode(m.groupValues[1], Base64.DEFAULT)
            val shiftK = m.groupValues[2].toInt()
            val sb = StringBuilder(rawBytes.size)
            for (b in rawBytes) {
                sb.append(((b.toInt() and 0xFF) - shiftK).toChar())
            }
            val obj = JSONObject(sb.toString())
            val vUrl = obj.optString("videoUrl").ifBlank { obj.optString("url") }.trim()
            if (vUrl.isNotEmpty()) {
                val absUrl = URL(URL(pageUrl), vUrl).toString()
                val u = URL(pageUrl)
                ParseResult(
                    success = true,
                    url = absUrl,
                    mediaType = if (absUrl.lowercase().contains("hls") || absUrl.lowercase().contains("m3u8")) "m3u8" else "video",
                    headers = mutableMapOf("Referer" to pageUrl, "Origin" to "${u.protocol}://${u.host}")
                )
            } else null
        } catch (_: Exception) {
            null
        }
    }

    private fun extractGenericSeries(html: String, baseUrl: String, pageTitle: String): SeriesInfo? {
        return try {
            val baseUri = URL(baseUrl)
            val baseHost = baseUri.host.lowercase()
            val basePath = baseUri.path.trimEnd('/')
            val pathPrefix = basePath.replace(Regex("\\d+(?=(?:\\.[a-z]+)?$)"), "")

            val anchorRe = Regex("<a\\b[^>]*?href=(?:[\"']([^\"'#]+)[\"']|([^\\s>\"'#]+))[^>]*>(.*?)</a>", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
            val epLabelRe = Regex("(第\\s*\\d+\\s*[集话期章讲节课部回]|EP?\\s*\\d+|P\\d+|^\\d{1,3}$|^(?:集|话|期|课)\\s*\\d+|番外|先导|预告|全集)", RegexOption.IGNORE_CASE)
            val noiseRe = Regex("(次觀看|次观看|views|已完結|已完结|全\\s*\\d+\\s*集)", RegexOption.IGNORE_CASE)
            val actionPrefixRe = Regex("^(?:從|从|立即|开始|開始|观看|觀看|正在).*?(?:開始|开始|播放|观看|觀看)$|^(?:上一集|下一集|播放|正在播放)$", RegexOption.IGNORE_CASE)

            data class Cand(var title: String, val url: String, val isEpText: Boolean, val isSamePattern: Boolean)
            val cands = mutableListOf<Cand>()
            val seenIdx = mutableMapOf<String, Int>()

            for (m in anchorRe.findAll(html)) {
                val rawHref = (m.groupValues[1].ifEmpty { m.groupValues[2] }).trim()
                if (rawHref.isEmpty() || rawHref.startsWith("javascript:") || rawHref.startsWith("mailto:") || rawHref.startsWith("tel:")) continue
                val cleanText = m.groupValues[3].replace(Regex("<[^>]+>"), " ").replace(Regex("\\s+"), " ").trim()
                if (cleanText.isEmpty() || cleanText.length > 50 || noiseRe.containsMatchIn(cleanText)) continue

                val absUrl = try { URL(baseUri, rawHref).toString() } catch (_: Exception) { continue }
                val uAbs = try { URL(absUrl) } catch (_: Exception) { continue }
                if (!uAbs.host.equals(baseHost, true)) continue

                val absPath = uAbs.path.trimEnd('/')
                val isEpText = epLabelRe.containsMatchIn(cleanText)
                val isSamePattern = pathPrefix.length > 3 && absPath.startsWith(pathPrefix) && absPath != pathPrefix

                if (isEpText || isSamePattern) {
                    val existIdx = seenIdx[absUrl]
                    if (existIdx != null) {
                        val old = cands[existIdx]
                        if (actionPrefixRe.matches(old.title) && !actionPrefixRe.matches(cleanText)) {
                            old.title = cleanText
                        }
                        continue
                    }
                    seenIdx[absUrl] = cands.size
                    cands.add(Cand(cleanText, absUrl, isEpText, isSamePattern))
                }
            }

            val samePat = cands.filter { it.isSamePattern }
            val pool = if (samePat.size >= 2) samePat else cands.filter { it.isEpText }
            if (pool.size < 2) return null

            var curIdx = 0
            val eps = pool.take(150).mapIndexed { i, c ->
                if (c.url == baseUrl) curIdx = i
                SeriesEpisode(index = i + 1, title = c.title, pageUrl = c.url)
            }
            val cleanSeriesTitle = pageTitle.replace(Regex("\\s*[-_|—].*$"), "").trim().ifEmpty { "同系列合集" }
            SeriesInfo(cleanSeriesTitle, "web_series", eps.size, curIdx, baseUrl, eps)
        } catch (_: Exception) {
            null
        }
    }

    fun submitSeriesDownloads(
        context: Context,
        episodes: List<SeriesEpisode>,
        seriesTitle: String,
        createSubDir: Boolean,
        addPrefix: Boolean,
        extraHeaders: Map<String, String>,
        onStatus: (String) -> Unit
    ) {
        val seriesBase = seriesTitle.replace(Regex("[\\\\/*?:\"<>|]"), "_").trim().take(50)
        val safeSubDir = if (createSubDir) seriesBase else ""
        CoroutineScope(Dispatchers.IO).launch {
            var okCount = 0
            episodes.forEachIndexed { idx, ep ->
                val epClean = ep.title.replace(Regex("[\\\\/*?:\"<>|]"), "_").trim()
                val title = if (seriesBase.isNotBlank() && !epClean.contains(seriesBase, ignoreCase = true)) {
                    val epSuffix = if (addPrefix) String.format("%02d_%s", ep.index, epClean) else epClean
                    "$seriesBase - $epSuffix"
                } else {
                    val prefix = if (addPrefix) String.format("%02d_", ep.index) else ""
                    "$prefix$epClean"
                }.trim()
                withContext(Dispatchers.Main) {
                    onStatus("正在解析 (${idx + 1}/${episodes.size}): $title")
                }

                val biliHeaders = mutableMapOf(
                    "Referer" to "https://www.bilibili.com/",
                    "Origin" to "https://www.bilibili.com",
                    "User-Agent" to (extraHeaders["User-Agent"] ?: UA)
                ).apply {
                    mergeCookieStrings(extraHeaders["Cookie"], readWebViewCookie("https://www.bilibili.com")).takeIf { it.isNotBlank() }?.let { put("Cookie", it) }
                }

                val res: ParseResult = when {
                    ep.audioSid > 0L -> {
                        ensureBiliSessionCookies(biliHeaders)
                        val aUrl = fetchBiliAudioStream(ep.audioSid, biliHeaders)
                        if (aUrl.isNotBlank()) ParseResult(true, title, aUrl, "", "audio", ep.durationSec, "高品质音频", headers = HashMap(biliHeaders))
                        else parseVideoUrl(ep.pageUrl, extraHeaders)
                    }
                    ep.bvid.isNotBlank() && ep.cid > 0L -> {
                        ensureBiliSessionCookies(biliHeaders)
                        val stream = fetchBiliPlayUrl(ep.bvid, ep.cid, biliHeaders, ep.isPgc, ep.epId)
                        if (stream != null) {
                            ParseResult(true, title, stream.first, stream.second, if (stream.second.isNotBlank()) "bili_dash" else "video", ep.durationSec, stream.third, headers = HashMap(biliHeaders))
                        } else {
                            parseVideoUrl(ep.pageUrl, extraHeaders)
                        }
                    }
                    else -> parseVideoUrl(ep.pageUrl, extraHeaders)
                }

                if (res.success && res.url.isNotBlank()) {
                    val mergedHeaders = HashMap(extraHeaders).apply { putAll(res.headers) }
                    if (ep.pageUrl.isNotBlank() && !mergedHeaders.containsKey("Referer")) {
                        mergedHeaders["Referer"] = ep.pageUrl
                    }
                    val task = DownloadTask(
                        id = UUID.randomUUID().toString().take(8),
                        title = title,
                        url = res.url,
                        audioUrl = res.audioUrl,
                        pageUrl = ep.pageUrl,
                        mediaType = res.mediaType,
                        resolution = res.resolution,
                        durationSec = ep.durationSec,
                        subDir = safeSubDir,
                        headers = mergedHeaders
                    )
                    TaskManager.addTask(context, task, autoStart = true)
                    okCount++
                }
                delay(200)
            }
            withContext(Dispatchers.Main) {
                onStatus("已加入下载队列: 成功 $okCount / ${episodes.size} 集")
            }
        }
    }
}

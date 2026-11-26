package com.starstream.downloader.core

import android.content.Context
import android.util.Base64
import kotlinx.coroutines.*
import okhttp3.Request
import org.json.JSONObject
import java.net.URL
import java.net.URLDecoder
import java.util.UUID

/**
 * 星流安卓全网解析与同系列/合集提取引擎 (完整移植 PC 端 video_parser.py)
 */
object VideoParser {

    private const val UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    private fun httpGet(url: String, extraHeaders: Map<String, String> = emptyMap()): Pair<String, String> {
        val builder = Request.Builder().url(url).header("User-Agent", UA)
        extraHeaders.forEach { (k, v) -> if (v.isNotBlank()) builder.header(k, v) }
        HttpClientProvider.getClient().newCall(builder.build()).execute().use { resp ->
            val finalUrl = resp.request.url.toString()
            val body = resp.body?.string() ?: ""
            return finalUrl to body
        }
    }

    fun parseVideoUrl(rawInput: String, extraHeaders: Map<String, String> = emptyMap()): ParseResult {
        val trimmed = rawInput.trim()
        val mUrl = Regex("https?://[^\\s<>\"]+").find(trimmed)
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
        if (listOf(".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg").any { lowerPath.endsWith(it) }) {
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
            val (finalUrl, _) = httpGet(url, extraHeaders)
            val biliHeaders = mutableMapOf("Referer" to "https://www.bilibili.com", "User-Agent" to UA).apply {
                extraHeaders["Cookie"]?.let { put("Cookie", it) }
            }

            if (finalUrl.contains("/bangumi/play/")) {
                parseBiliBangumi(finalUrl, biliHeaders)?.let { return it }
            }

            val bvMatch = Regex("(BV[a-zA-Z0-9]+)").find(finalUrl) ?: return parseGenericWeb(finalUrl, extraHeaders)
            val bvid = bvMatch.groupValues[1]
            val pMatch = Regex("[?&]p=(\\d+)").find(finalUrl)
            val targetP = (pMatch?.groupValues?.get(1)?.toIntOrNull() ?: 1).coerceAtLeast(1)

            val (_, viewText) = httpGet("https://api.bilibili.com/x/web-interface/view?bvid=$bvid", biliHeaders)
            val viewJson = JSONObject(viewText)
            if (viewJson.optInt("code") != 0) {
                return ParseResult(false, error = "B站接口提示: ${viewJson.optString("message")}")
            }
            val vData = viewJson.getJSONObject("data")
            var title = vData.optString("title", "bilibili_$bvid")
            var cid = vData.optLong("cid", 0L)
            var duration = vData.optInt("duration", 0)
            val cover = vData.optString("pic", "")

            val pages = vData.optJSONArray("pages")
            if (pages != null && targetP <= pages.length()) {
                val pObj = pages.getJSONObject(targetP - 1)
                cid = pObj.optLong("cid", cid)
                duration = pObj.optInt("duration", duration)
                if (pages.length() > 1) {
                    val partName = pObj.optString("part", "")
                    if (partName.isNotBlank()) title = "$title - P$targetP $partName"
                }
            }

            val seriesInfo = extractBiliSeries(vData, bvid, targetP)
            val stream = fetchBiliPlayUrl(bvid, cid, biliHeaders)
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
            ParseResult(false, title = title, series = seriesInfo, error = "未能提取到 B站 视频流，可在内置浏览器登录后嗅探")
        } catch (e: Exception) {
            ParseResult(false, error = "B站解析异常: ${e.message}")
        }
    }

    private fun fetchBiliPlayUrl(bvid: String, cid: Long, headers: Map<String, String>, isPgc: Boolean = false, epId: Long = 0L): Triple<String, String, String>? {
        val dashApi = if (isPgc && epId > 0) {
            "https://api.bilibili.com/pgc/player/web/playurl?ep_id=$epId&cid=$cid&qn=80&fnval=16&fourk=1"
        } else {
            "https://api.bilibili.com/x/player/playurl?bvid=$bvid&cid=$cid&qn=80&fnval=16&fnver=0&fourk=1"
        }
        try {
            val (_, txt) = httpGet(dashApi, headers)
            val json = JSONObject(txt)
            if (json.optInt("code") == 0) {
                val dataObj = if (isPgc) json.optJSONObject("result") else json.optJSONObject("data")
                val dash = dataObj?.optJSONObject("dash")
                val videos = dash?.optJSONArray("video")
                val audios = dash?.optJSONArray("audio")
                if (videos != null && videos.length() > 0) {
                    var bestV = videos.getJSONObject(0)
                    for (i in 1 until videos.length()) {
                        val cur = videos.getJSONObject(i)
                        if (cur.optInt("id") > bestV.optInt("id")) bestV = cur
                    }
                    val vUrl = bestV.optString("baseUrl").ifBlank { bestV.optString("base_url") }
                    var aUrl = ""
                    if (audios != null && audios.length() > 0) {
                        // 安卓 MediaMuxer 仅原生支持 AAC (mp4a / 30216, 30232, 30280)，避免误选 FLAC/Dolby (30250/30251) 导致无声
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

    private fun parseBiliBangumi(finalUrl: String, headers: Map<String, String>): ParseResult? {
        val mEp = Regex("/ep(\\d+)").find(finalUrl)
        val mSs = Regex("/ss(\\d+)").find(finalUrl)
        if (mEp == null && mSs == null) return null
        val param = if (mEp != null) "ep_id=${mEp.groupValues[1]}" else "season_id=${mSs!!.groupValues[1]}"
        return try {
            val (_, txt) = httpGet("https://api.bilibili.com/pgc/view/web/season?$param", headers)
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
                ParseResult(true, curEp.title, stream.first, stream.second, "bili_dash", curEp.durationSec, stream.third, res.optString("cover", ""), headers.toMutableMap(), series)
            } else {
                ParseResult(false, title = seasonTitle, series = series, error = "该番剧需大会员或登录凭证，已识别全集清单，可在内置浏览器登录后嗅探")
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun parseDouyin(url: String): ParseResult {
        return try {
            val (finalUrl, html) = httpGet(url)
            val title = Regex("<title>([^<]+)</title>").find(html)?.groupValues?.get(1)?.replace(" - 抖音", "")?.trim() ?: "抖音视频"
            val decoded = try { URLDecoder.decode(html, "UTF-8") } catch (_: Exception) { html }
            val mPlay = Regex("\"play_addr\":\\{\"uri\":\"[^\"]*\",\"url_list\":\\[\"([^\"]+)\"").find(decoded)
                ?: Regex("\"(https://[^\\s\"'<>]+\\.douyinvod\\.com/[^\\s\"'<>]+)\"").find(decoded)
            if (mPlay != null) {
                val rawUrl = mPlay.groupValues[1].replace("\\u0026", "&").replace("playwm", "play")
                ParseResult(true, title, rawUrl, mediaType = "video", resolution = "1080P", headers = mutableMapOf("Referer" to "https://www.douyin.com/"))
            } else {
                ParseResult(false, title = title, error = "抖音当前视频触发了动态 JS 验证，请使用内置浏览器打开播放即可自动嗅探捕获！")
            }
        } catch (e: Exception) {
            ParseResult(false, error = "抖音解析失败: ${e.message}")
        }
    }

    private fun parseKuaishou(url: String): ParseResult {
        return try {
            val (finalUrl, html) = httpGet(url)
            val mVid = Regex("\"(?:photoUrl|url)\":\"(https?://[^\"]+\\.mp4[^\"]*)\"").find(html)
            if (mVid != null) {
                ParseResult(true, "快手视频", mVid.groupValues[1].replace("\\u0026", "&"), mediaType = "video", resolution = "高清", headers = mutableMapOf("Referer" to "https://www.kuaishou.com/"))
            } else {
                parseGenericWeb(finalUrl, emptyMap())
            }
        } catch (e: Exception) {
            ParseResult(false, error = "快手解析失败: ${e.message}")
        }
    }

    private fun parseXiaohongshu(url: String): ParseResult {
        return try {
            val (finalUrl, html) = httpGet(url)
            val mKey = Regex("originVideoKey\":\"([^\"]+)\"").find(html)
            if (mKey != null) {
                ParseResult(true, "小红书视频", "https://sns-video-bd.xhscdn.com/${mKey.groupValues[1]}", mediaType = "video", resolution = "高清", headers = mutableMapOf("Referer" to "https://www.xiaohongshu.com/"))
            } else {
                parseGenericWeb(finalUrl, emptyMap())
            }
        } catch (e: Exception) {
            ParseResult(false, error = "小红书解析失败: ${e.message}")
        }
    }

    fun parseGenericWeb(url: String, extraHeaders: Map<String, String>): ParseResult {
        return try {
            val (finalUrl, rawHtml) = httpGet(url, extraHeaders)
            val html = unwrapBase64DocumentWrite(rawHtml)
            val title = Regex("<title>([^<]+)</title>", RegexOption.IGNORE_CASE).find(html)?.groupValues?.get(1)?.replace(Regex("[\\r\\n\\t]+"), " ")?.trim() ?: "网页视频"
            val seriesInfo = extractGenericSeries(html, finalUrl, title)

            // 1. MacCMS player_aaaa={...}
            extractPlayerAaaa(html, finalUrl)?.let { p4 ->
                val finalTitle = p4.title.ifBlank { title.substringBefore(" - ").trim() }
                val refinedSeries = if (seriesInfo != null && p4.title.isNotBlank()) seriesInfo.copy(seriesTitle = p4.title) else seriesInfo
                return ParseResult(true, finalTitle, p4.url, mediaType = p4.mediaType, resolution = "高清", coverUrl = p4.coverUrl, headers = p4.headers, series = refinedSeries)
            }

            // 2. ev:{d:"...", k:N} 加密媒体
            decodeEmbeddedEvPayload(html, finalUrl)?.let { ev ->
                return ParseResult(true, title.substringBefore(" - ").trim(), ev.url, mediaType = ev.mediaType, resolution = "高清", headers = ev.headers, series = seriesInfo)
            }

            // 3. M3U8 / MP4 直链正则
            val mM3u8 = Regex("[\"'](https?://[^\"']+\\.m3u8(?:\\?[^\"']*)?)[\"']", RegexOption.IGNORE_CASE).find(html)
            if (mM3u8 != null) {
                return ParseResult(true, title, mM3u8.groupValues[1], mediaType = "m3u8", resolution = "自适应", headers = mutableMapOf("Referer" to finalUrl), series = seriesInfo)
            }

            val mVid = Regex("<(?:video|source)[^>]+src=[\"'](https?://[^\"']+\\.(?:mp4|webm|mkv)[^\"']*)[\"']", RegexOption.IGNORE_CASE).find(html)
            if (mVid != null) {
                return ParseResult(true, title, mVid.groupValues[1], mediaType = "video", resolution = "高清", headers = mutableMapOf("Referer" to finalUrl), series = seriesInfo)
            }

            // 4. StreamitVideoPlyr (streamApi + videoUid, 如 huangguo123.com)
            val mSapi = Regex("var\\s+streamApi\\s*=\\s*[\"']([^\"']+)[\"']").find(html)
            val mVuid = Regex("var\\s+videoUid\\s*=\\s*[\"']([^\"']+)[\"']").find(html)
            if (mSapi != null && mVuid != null) {
                try {
                    val epUid = Regex("var\\s+currentEpisodeUid\\s*=\\s*[\"']([^\"']*)[\"']").find(html)?.groupValues?.get(1).orEmpty()
                    val apiBase = java.net.URI(finalUrl).resolve(mSapi.groupValues[1]).toString()
                    val sep = if (apiBase.contains("?")) "&" else "?"
                    var apiUrl = "$apiBase${sep}video_uid=${java.net.URLEncoder.encode(mVuid.groupValues[1], "UTF-8")}"
                    if (epUid.isNotBlank()) apiUrl += "&episode_uid=${java.net.URLEncoder.encode(epUid, "UTF-8")}"
                    val (_, apiBody) = httpGet(apiUrl, extraHeaders + mapOf("Referer" to finalUrl))
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

            ParseResult(false, title = title, series = seriesInfo, error = if (seriesInfo != null) "已识别合集共 ${seriesInfo.total} 集，可选集批量爬取！" else "未直接发现公开媒体流，请在【嗅探浏览器】中播放捕获")
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
        val safeSubDir = if (createSubDir) seriesTitle.replace(Regex("[\\\\/*?:\"<>|]"), "_").trim().take(60) else ""
        CoroutineScope(Dispatchers.IO).launch {
            var okCount = 0
            episodes.forEachIndexed { idx, ep ->
                val prefix = if (addPrefix) String.format("%02d - ", ep.index) else ""
                val title = "$prefix${ep.title}".replace(Regex("[\\\\/*?:\"<>|]"), "_").trim()
                withContext(Dispatchers.Main) {
                    onStatus("正在解析 (${idx + 1}/${episodes.size}): $title")
                }

                val res: ParseResult = if (ep.bvid.isNotBlank() && ep.cid > 0L) {
                    val biliHeaders = mutableMapOf("Referer" to "https://www.bilibili.com", "User-Agent" to UA).apply {
                        extraHeaders["Cookie"]?.let { put("Cookie", it) }
                    }
                    val stream = fetchBiliPlayUrl(ep.bvid, ep.cid, biliHeaders, ep.isPgc, ep.epId)
                    if (stream != null) {
                        ParseResult(true, title, stream.first, stream.second, if (stream.second.isNotBlank()) "bili_dash" else "video", ep.durationSec, stream.third, headers = biliHeaders)
                    } else {
                        parseVideoUrl(ep.pageUrl, extraHeaders)
                    }
                } else {
                    parseVideoUrl(ep.pageUrl, extraHeaders)
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

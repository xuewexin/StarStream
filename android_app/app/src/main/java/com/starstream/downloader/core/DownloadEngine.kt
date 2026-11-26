package com.starstream.downloader.core

import android.content.Context
import android.webkit.CookieManager
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import okhttp3.ConnectionPool
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.net.InetSocketAddress
import java.net.Proxy
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import java.util.zip.Inflater
import javax.crypto.Cipher
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

object HttpClientProvider {
    private val pool = ConnectionPool(16, 2, TimeUnit.MINUTES)

    private val directClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectionPool(pool)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .followRedirects(true)
            .followSslRedirects(true)
            .build()
    }

    fun resetConnections() {
        try {
            pool.evictAll()
        } catch (_: Throwable) {}
    }

    fun getClient(): OkHttpClient {
        if (AppConfig.useProxy && AppConfig.proxyHost.isNotBlank() && AppConfig.proxyPort > 0) {
            return directClient.newBuilder()
                .proxy(Proxy(Proxy.Type.HTTP, InetSocketAddress(AppConfig.proxyHost, AppConfig.proxyPort)))
                .build()
        }
        return directClient
    }
}

/**
 * 移植自 PC 端 download_stream.py:refresh_task_credentials
 * 同步 WebView Cookie、源站 Set-Cookie、防盗链头、重解析页面新鲜 CDN Token 与重定向地址
 */
object CredentialRefresher {

    private fun mergeCookies(vararg sources: String?): String {
        val map = linkedMapOf<String, String>()
        for (s in sources) {
            if (s.isNullOrBlank()) continue
            s.split(";").forEach { part ->
                val idx = part.indexOf('=')
                if (idx > 0) {
                    val k = part.substring(0, idx).trim()
                    val v = part.substring(idx + 1).trim()
                    if (k.isNotEmpty() && v.isNotEmpty()) map[k] = v
                }
            }
        }
        return map.entries.joinToString("; ") { "${it.key}=${it.value}" }
    }

    fun refreshTaskCredentials(task: DownloadTask, rotateUa: Boolean = true): Boolean {
        var refreshed = false
        val newHeaders = HashMap(task.headers)
        if (rotateUa) {
            newHeaders["User-Agent"] = AppConfig.rotateIdentity()
        } else if (newHeaders["User-Agent"].isNullOrBlank()) {
            newHeaders["User-Agent"] = AppConfig.getUserAgentString()
        }

        val ref = task.pageUrl.ifBlank { newHeaders["Referer"] ?: "" }
        val targetLower = task.url.lowercase()
        when {
            targetLower.contains("bilivideo") || targetLower.contains("hdslb.com") || ref.contains("bilibili.com") -> {
                newHeaders["Referer"] = if (ref.startsWith("http")) ref else "https://www.bilibili.com/"
                newHeaders["Origin"] = "https://www.bilibili.com"
            }
            targetLower.contains("douyin") || targetLower.contains("snssdk.com") -> {
                newHeaders["Referer"] = "https://www.douyin.com/"
            }
            targetLower.contains("kwaicdn") || targetLower.contains("kwai.net") -> {
                newHeaders["Referer"] = "https://www.kuaishou.com/"
            }
            targetLower.contains("xhscdn") -> {
                newHeaders["Referer"] = "https://www.xiaohongshu.com/"
            }
            ref.startsWith("http") -> {
                newHeaders["Referer"] = ref
                try {
                    val u = URL(ref)
                    newHeaders["Origin"] = "${u.protocol}://${u.host}"
                } catch (_: Exception) {}
            }
        }

        // 1. 从内置 WebView CookieManager 同步最新会话 Cookie
        try {
            val cm = CookieManager.getInstance()
            val cPage = if (ref.startsWith("http")) cm.getCookie(ref) else ""
            val cUrl = if (task.url.startsWith("http")) cm.getCookie(task.url) else ""
            val merged = mergeCookies(newHeaders["Cookie"], cPage, cUrl)
            if (merged.isNotBlank() && merged != newHeaders["Cookie"]) {
                newHeaders["Cookie"] = merged
                refreshed = true
            }
        } catch (_: Throwable) {}

        // 2. 若有源页面 URL，重请求源页面拉取最新签名流地址（例如 B站临时签名过期/限流）或新 Set-Cookie
        if (task.pageUrl.startsWith("http")) {
            try {
                val parsed = VideoParser.parseVideoUrl(task.pageUrl, newHeaders)
                if (parsed.success && parsed.url.isNotBlank()) {
                    val wantAudioOnly = task.mediaType == "audio" && parsed.mediaType != "audio"
                    if (!wantAudioOnly) {
                        if (parsed.url != task.url) {
                            task.url = parsed.url
                            refreshed = true
                        }
                        if (parsed.audioUrl.isNotBlank()) {
                            if (parsed.audioUrl != task.audioUrl) refreshed = true
                            task.audioUrl = parsed.audioUrl
                            if (task.mediaType != "m3u8") task.mediaType = "bili_dash"
                        }
                    }
                    parsed.headers.forEach { (k, v) -> if (v.isNotBlank()) newHeaders[k] = v }
                }
            } catch (_: Exception) {}
        }

        // 3. 轻量跟踪资源 URL 重定向刷新临时 CDN Token / Set-Cookie
        if (task.url.startsWith("http")) {
            try {
                val reqB = Request.Builder().url(task.url).get()
                newHeaders.forEach { (k, v) -> if (v.isNotBlank()) reqB.header(k, v) }
                reqB.header("Range", "bytes=0-0")
                HttpClientProvider.getClient().newCall(reqB.build()).execute().use { resp ->
                    val resolved = resp.request.url.toString()
                    if (resolved.startsWith("http") && resolved != task.url && !resolved.contains("error")) {
                        task.url = resolved
                        refreshed = true
                    }
                    val setCookies = resp.headers("Set-Cookie")
                        .mapNotNull { it.substringBefore(";").takeIf { kv -> kv.contains("=") } }
                        .joinToString("; ")
                    if (setCookies.isNotBlank()) {
                        newHeaders["Cookie"] = mergeCookies(newHeaders["Cookie"], setCookies)
                        refreshed = true
                    }
                }
            } catch (_: Exception) {}
        }

        task.headers = newHeaders
        HttpClientProvider.resetConnections()
        return refreshed
    }
}

/**
 * 原生 FFmpeg + 多线程高速下载引擎
 * - 集成 FFmpegKit 真混流封装，彻底解决 B站/M3U8 音画丢失与合并失败
 * - 移植 PC 端主动打破限速 (Active Throttle Breaking)：实时监测 1s 瞬时速率与峰值回落，自动刷新令牌与重建链路
 * - 分片级/分块级断点续传，暂停/刷新令牌/重连不丢失已完成进度
 */
class DownloadRunner(
    private val context: Context,
    private val task: DownloadTask,
    private val onProgress: () -> Unit
) {
    private val cancelled = AtomicBoolean(false)
    private val tokenBoostRequested = AtomicBoolean(false)
    private var job: Job? = null

    fun cancel() {
        cancelled.set(true)
        job?.cancel()
    }

    fun isAlive(): Boolean = job?.isActive == true

    fun requestTokenBoost() {
        tokenBoostRequested.set(true)
    }

    fun start(scope: CoroutineScope, onComplete: (Boolean, String) -> Unit) {
        job = scope.launch(Dispatchers.IO) {
            var completedSuccess = false
            var completionMsg = ""
            try {
                task.status = TaskStatus.DOWNLOADING
                task.errorMsg = ""
                onProgress()

                val lowerUrl = task.url.lowercase().split("?")[0]
                val isBiliLink = task.mediaType == "bili_dash" || lowerUrl.contains("bilivideo") || lowerUrl.contains("hdslb.com")
                val hasRangeFrag = task.url.contains("range=", ignoreCase = true) || task.audioUrl.contains("range=", ignoreCase = true)
                val needsBiliRecovery = isBiliLink && (task.audioUrl.isBlank() || hasRangeFrag) &&
                    !lowerUrl.contains("302") && task.pageUrl.contains("bilibili.com")

                if (needsBiliRecovery) {
                    task.speedText = "正在补齐 B站完整高清音视频轨..."
                    onProgress()
                    CredentialRefresher.refreshTaskCredentials(task, rotateUa = false)
                }

                // 补全 B站 等防盗链必需请求头
                if (isBiliLink || task.pageUrl.contains("bilibili.com")) {
                    if (task.headers["Referer"].isNullOrBlank()) task.headers["Referer"] = "https://www.bilibili.com/"
                    if (task.headers["Origin"].isNullOrBlank()) task.headers["Origin"] = "https://www.bilibili.com"
                }

                val safeName = task.title.replace(Regex("[\\\\/*?:\"<>|]"), "_").trim().ifEmpty { "video_${System.currentTimeMillis()}" }
                val workRoot = File(context.getExternalFilesDir(null), "downloads")
                val outDir = if (task.subDir.isNotBlank()) File(workRoot, task.subDir) else workRoot
                outDir.mkdirs()

                val isM3u8 = task.mediaType == "m3u8" || lowerUrl.contains(".m3u8") || lowerUrl.contains("/api/hls/")
                val outFile: File = if (isM3u8) {
                    downloadM3u8(outDir, safeName)
                } else if (task.audioUrl.isNotBlank()) {
                    downloadDashDualTrack(outDir, safeName)
                } else {
                    downloadSingleFile(outDir, safeName)
                }

                if (cancelled.get()) {
                    completionMsg = "已暂停/取消"
                    return@launch
                }

                task.outputPath = outFile.absolutePath
                task.totalBytes = outFile.length()
                task.downloadedBytes = outFile.length()
                task.progress = 100
                task.speedText = "完成"
                task.status = TaskStatus.COMPLETED

                // 清理该任务所有临时分片目录 (.parts_* / seg_* / dash_*)
                try { File(context.cacheDir, "seg_${task.id}").deleteRecursively() } catch (_: Exception) {}
                try { File(context.cacheDir, "dash_${task.id}").deleteRecursively() } catch (_: Exception) {}
                try { File(outFile.parentFile, ".parts_${outFile.name}").deleteRecursively() } catch (_: Exception) {}

                var exported = ""
                try {
                    if (AppConfig.saveToGallery || AppConfig.customSaveUri.isNotBlank()) {
                        exported = AndroidMediaMuxer.exportToPublicDownloads(context, outFile, task.subDir)
                    }
                } catch (_: Throwable) {}
                task.exportedUri = exported
                completedSuccess = true
                completionMsg = "下载完成"
                onProgress()
            } catch (e: CancellationException) {
                task.status = TaskStatus.PAUSED
                task.speedText = "已暂停"
                completionMsg = "任务已暂停"
                onProgress()
            } catch (e: Throwable) {
                task.status = TaskStatus.ERROR
                task.errorMsg = e.message ?: "下载异常"
                task.speedText = "失败"
                completionMsg = task.errorMsg
                onProgress()
            } finally {
                onComplete(completedSuccess, completionMsg)
            }
        }
    }

    private fun buildRequest(url: String): Request {
        val builder = Request.Builder().url(url)
        val ua = task.headers["User-Agent"] ?: AppConfig.getUserAgentString()
        builder.header("User-Agent", ua)
        task.headers.forEach { (k, v) ->
            if (v.isNotBlank() && !k.equals("User-Agent", true)) {
                builder.header(k, v)
            }
        }
        return builder.build()
    }

    private fun fetchBytes(url: String, allowRefresh: Boolean = true): ByteArray? {
        var didRefresh = false
        for (retry in 0..3) {
            if (cancelled.get()) return null
            val client = HttpClientProvider.getClient()
            try {
                client.newCall(buildRequest(url)).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val bytes = resp.body?.bytes()
                        if (bytes != null && bytes.isNotEmpty()) return bytes
                    } else if (resp.code in listOf(401, 403, 410, 412, 416) && allowRefresh && !didRefresh) {
                        didRefresh = true
                        task.speedText = "HTTP ${resp.code} 自动刷新令牌..."
                        onProgress()
                        CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
                    }
                }
            } catch (_: Exception) {
                if (retry < 3) Thread.sleep(400)
            }
        }
        return null
    }

    private fun unwrapMediaBytes(raw: ByteArray): ByteArray {
        if (raw.size < 16) return raw
        val pngMagic = byteArrayOf(137.toByte(), 80, 78, 71, 13, 10, 26, 10)
        for (i in pngMagic.indices) {
            if (raw[i] != pngMagic[i]) return raw
        }
        val buf = ByteBuffer.wrap(raw).order(ByteOrder.BIG_ENDIAN)
        var pos = 8
        while (pos + 8 <= raw.size) {
            val len = buf.getInt(pos)
            val ctype = buf.getInt(pos + 4)
            val x = pos + 8
            if (len < 0 || x + len > raw.size) break
            if (ctype == 1919898980) { // 'roUd'
                val flags = raw[x].toInt()
                val payload = raw.copyOfRange(x + 1, x + len)
                return if ((flags and 1) != 0) inflateZlib(payload) else payload
            }
            pos = x + len + 4
        }
        return raw
    }

    private fun inflateZlib(data: ByteArray): ByteArray {
        val inflater = Inflater()
        inflater.setInput(data)
        val out = ByteArrayOutputStream(data.size * 2)
        val tmp = ByteArray(4096)
        while (!inflater.finished()) {
            val n = inflater.inflate(tmp)
            if (n <= 0) break
            out.write(tmp, 0, n)
        }
        inflater.end()
        return out.toByteArray()
    }

    /**
     * 移植 PC 端主动打破限速监控器（Rolling 1s window + 限速/跌落检测）
     */
    private class ThrottleMonitor {
        private var startMs = System.currentTimeMillis()
        private var sampleMs = System.currentTimeMillis()
        private var sampleBytes = 0L
        private var smoothBps = 0.0
        private var peakBps = 0.0
        private var lowSpeedStartMs = 0L
        private var lastRefreshMs = 0L
        private var refreshCount = 0

        fun updateAndCheckBoost(totalBytes: Long, remainingRatio: Double, manualFlag: AtomicBoolean): Pair<Double, Boolean> {
            val now = System.currentTimeMillis()
            val dtSec = (now - sampleMs) / 1000.0
            if (dtSec >= 0.8) {
                val inst = ((totalBytes - sampleBytes).coerceAtLeast(0L)) / dtSec
                smoothBps = if (smoothBps <= 0.0) inst else 0.7 * inst + 0.3 * smoothBps
                if (smoothBps > peakBps) peakBps = smoothBps
                sampleBytes = totalBytes
                sampleMs = now
            }

            if (manualFlag.compareAndSet(true, false)) {
                lastRefreshMs = now
                lowSpeedStartMs = 0L
                refreshCount++
                return smoothBps to true
            }

            val elapsedMs = now - startMs
            if (refreshCount < 8 && elapsedMs >= 9000L && remainingRatio > 0.04 && (now - lastRefreshMs >= 20000L)) {
                val inThrottleZone = smoothBps in (25 * 1024.0)..(620 * 1024.0)
                val speedDropped = (peakBps > 1.2 * 1024 * 1024 && smoothBps < peakBps * 0.25) ||
                    (elapsedMs >= 15000L && inThrottleZone)
                if (inThrottleZone && speedDropped) {
                    if (lowSpeedStartMs == 0L) {
                        lowSpeedStartMs = now
                    } else if (now - lowSpeedStartMs >= 6500L) {
                        lastRefreshMs = now
                        lowSpeedStartMs = 0L
                        refreshCount++
                        return smoothBps to true
                    }
                } else {
                    lowSpeedStartMs = 0L
                }
            }
            return smoothBps to false
        }
    }

    private data class HlsPlaylistParsed(
        val baseUrl: String,
        val segments: List<String>,
        val aesKey: ByteArray?,
        val aesIv: ByteArray?,
        val initUrl: String = ""
    )

    private fun parseSegmentPlaylist(playlistUrl: String, m3u8Text: String): HlsPlaylistParsed {
        var aesKey: ByteArray? = null
        var aesIv: ByteArray? = null
        var initUrl = ""
        val segments = mutableListOf<String>()
        val querySuffix = if (playlistUrl.contains("?")) playlistUrl.substringAfter("?") else if (task.url.contains("?")) task.url.substringAfter("?") else ""

        for (rawLine in m3u8Text.lines()) {
            val line = rawLine.trim()
            if (line.isEmpty()) continue
            if (line.startsWith("#EXT-X-MAP")) {
                val uriMatch = Regex("URI=\"([^\"]+)\"").find(line)
                if (uriMatch != null && initUrl.isEmpty()) {
                    initUrl = URL(URL(playlistUrl), uriMatch.groupValues[1]).toString()
                    if (querySuffix.isNotEmpty() && !initUrl.contains("?")) initUrl = "$initUrl?$querySuffix"
                }
                continue
            }
            if (line.startsWith("#EXT-X-KEY")) {
                if (line.contains("AES-128", ignoreCase = true)) {
                    val uriMatch = Regex("URI=\"([^\"]+)\"").find(line)
                    if (uriMatch != null) {
                        val keyUrl = URL(URL(playlistUrl), uriMatch.groupValues[1]).toString()
                        aesKey = fetchBytes(keyUrl)
                    }
                    val ivMatch = Regex("IV=0x([0-9a-fA-F]+)").find(line)
                    if (ivMatch != null) {
                        aesIv = hexToBytes(ivMatch.groupValues[1])
                    }
                }
                continue
            }
            if (line.startsWith("#")) continue
            var segUrl = URL(URL(playlistUrl), line).toString()
            if (querySuffix.isNotEmpty() && !segUrl.contains("?")) {
                segUrl = "$segUrl?$querySuffix"
            }
            segments.add(segUrl)
        }
        return HlsPlaylistParsed(playlistUrl, segments, aesKey, aesIv, initUrl)
    }

    private suspend fun downloadPlaylistSegments(
        parsed: HlsPlaylistParsed,
        tmpDir: File,
        prefix: String,
        progressBase: Int,
        progressSpan: Int
    ): File = coroutineScope {
        val totalCount = parsed.segments.size
        val doneCount = AtomicInteger(0)
        val totalDownloaded = AtomicLong(0)
        val threads = (if (task.threadOverride > 0) task.threadOverride else AppConfig.threadCount).coerceIn(1, 24)
        val semaphore = Semaphore(threads)
        val monitor = ThrottleMonitor()
        val refreshLock = Any()

        val initFile = File(tmpDir, "${prefix}_init.bin")
        val initBytes = if (parsed.initUrl.isNotEmpty()) {
            if (initFile.exists() && initFile.length() > 0) initFile.readBytes()
            else fetchBytes(parsed.initUrl)?.also { initFile.writeBytes(it) }
        } else null

        val jobs = parsed.segments.mapIndexed { idx, segUrl ->
            async {
                semaphore.withPermit {
                    if (cancelled.get()) return@withPermit
                    val segFile = File(tmpDir, "${prefix}_%05d.ts".format(idx))
                    val bytesLen: Long
                    if (segFile.exists() && segFile.length() > 0) {
                        bytesLen = segFile.length()
                    } else {
                        var bytes = fetchBytes(segUrl) ?: throw Exception("分片 #$idx 拉取失败")
                        bytes = unwrapMediaBytes(bytes)
                        if (parsed.aesKey != null) {
                            bytes = decryptAes128(bytes, parsed.aesKey, parsed.aesIv ?: defaultIv(idx))
                        }
                        FileOutputStream(segFile).use { it.write(bytes) }
                        bytesLen = bytes.size.toLong()
                    }

                    val done = doneCount.incrementAndGet()
                    val dlBytes = totalDownloaded.addAndGet(bytesLen)
                    val remRatio = (totalCount - done).toDouble() / totalCount.coerceAtLeast(1)
                    val (bps, needBoost) = synchronized(monitor) {
                        monitor.updateAndCheckBoost(dlBytes, remRatio, tokenBoostRequested)
                    }
                    if (needBoost && !cancelled.get()) {
                        synchronized(refreshLock) {
                            task.speedText = "智能刷新令牌提速中..."
                            onProgress()
                            CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
                        }
                    }
                    task.downloadedBytes = dlBytes
                    task.progress = (progressBase + (done * progressSpan.toDouble()) / totalCount).toInt().coerceIn(1, 95)
                    task.speedText = if (!needBoost) formatSpeed(bps.toLong()) else "已刷新令牌提速"
                    onProgress()
                }
            }
        }
        jobs.awaitAll()
        if (cancelled.get()) throw CancellationException()

        val extOut = if (initBytes != null) "mp4" else "ts"
        val mergedFile = File(tmpDir, "${prefix}_merged.$extOut")
        FileOutputStream(mergedFile).use { fos ->
            if (initBytes != null) fos.write(initBytes)
            for (idx in parsed.segments.indices) {
                val segFile = File(tmpDir, "${prefix}_%05d.ts".format(idx))
                if (segFile.exists()) {
                    segFile.inputStream().use { it.copyTo(fos) }
                }
            }
        }
        mergedFile
    }

    private suspend fun downloadM3u8(outDir: File, safeName: String): File = coroutineScope {
        val rawM3u8 = fetchBytes(task.url) ?: throw Exception("无法拉取 M3U8 清单 (请下拉刷新令牌或检查网络)")
        var m3u8Text = String(unwrapMediaBytes(rawM3u8), Charsets.UTF_8)
        var baseUrl = task.url
        var audioPlaylistUrl = ""

        if (m3u8Text.contains("#EXT-X-STREAM-INF")) {
            val lines = m3u8Text.lines()
            val audioGroups = mutableMapOf<String, String>()
            for (l in lines) {
                val trimL = l.trim()
                if (trimL.startsWith("#EXT-X-MEDIA") && trimL.contains("TYPE=AUDIO", ignoreCase = true)) {
                    val gid = Regex("GROUP-ID=\"([^\"]+)\"").find(trimL)?.groupValues?.get(1) ?: ""
                    val uri = Regex("URI=\"([^\"]+)\"").find(trimL)?.groupValues?.get(1) ?: ""
                    if (uri.isNotEmpty()) {
                        val absUri = URL(URL(baseUrl), uri).toString()
                        if (!audioGroups.containsKey(gid) || trimL.contains("DEFAULT=YES", ignoreCase = true)) {
                            audioGroups[gid] = absUri
                        }
                    }
                }
            }

            var bestUrl = ""
            var bestBw = -1L
            var bestAudioGroup = ""
            for (i in lines.indices) {
                val l = lines[i].trim()
                if (l.startsWith("#EXT-X-STREAM-INF") && i + 1 < lines.size) {
                    val bw = Regex("BANDWIDTH=(\\d+)").find(l)?.groupValues?.get(1)?.toLongOrNull() ?: 0L
                    val nextLine = lines[i + 1].trim()
                    if (nextLine.isNotEmpty() && !nextLine.startsWith("#") && bw >= bestBw) {
                        bestBw = bw
                        bestUrl = URL(URL(baseUrl), nextLine).toString()
                        bestAudioGroup = Regex("AUDIO=\"([^\"]+)\"").find(l)?.groupValues?.get(1) ?: ""
                    }
                }
            }
            if (bestUrl.isNotEmpty()) {
                baseUrl = bestUrl
                val subBytes = fetchBytes(bestUrl) ?: throw Exception("无法拉取清晰度子清单")
                m3u8Text = String(unwrapMediaBytes(subBytes), Charsets.UTF_8)
                audioPlaylistUrl = audioGroups[bestAudioGroup] ?: audioGroups.values.firstOrNull() ?: ""
            }
        }

        val parsedVideo = parseSegmentPlaylist(baseUrl, m3u8Text)
        if (parsedVideo.segments.isEmpty()) throw Exception("M3U8 中未解析到有效切片")

        var parsedAudio: HlsPlaylistParsed? = null
        if (audioPlaylistUrl.isNotEmpty()) {
            val aRaw = fetchBytes(audioPlaylistUrl)
            if (aRaw != null) {
                val aText = String(unwrapMediaBytes(aRaw), Charsets.UTF_8)
                val pAudio = parseSegmentPlaylist(audioPlaylistUrl, aText)
                if (pAudio.segments.isNotEmpty()) parsedAudio = pAudio
            }
        }

        // 确定性分片缓存目录，确保暂停/刷新令牌/重连可断点续传不重下
        val tmpDir = File(context.cacheDir, "seg_${task.id}")
        tmpDir.mkdirs()
        LocalStreamProxy.registerTaskCacheDir(task.id, tmpDir)

        var completedOk = false
        try {
            val videoSpan = if (parsedAudio != null) 75 else 95
            val mergedVideo = downloadPlaylistSegments(parsedVideo, tmpDir, "vseg", 0, videoSpan)
            val mergedAudio = if (parsedAudio != null) {
                downloadPlaylistSegments(parsedAudio, tmpDir, "aseg", 75, 20)
            } else null

            task.status = TaskStatus.MUXING
            task.progress = 96
            task.speedText = "FFmpeg 无损混流封装中..."
            onProgress()

            val finalMp4 = File(outDir, "$safeName.mp4")
            if (mergedAudio != null && AndroidMediaMuxer.muxVideoAndAudio(mergedVideo, mergedAudio, finalMp4)) {
                completedOk = true
                return@coroutineScope finalMp4
            }
            if (AppConfig.autoConvertMp4 && AndroidMediaMuxer.remuxTsToMp4(mergedVideo, finalMp4)) {
                completedOk = true
                return@coroutineScope finalMp4
            }
            val fallbackExt = mergedVideo.extension.ifBlank { "ts" }
            val fallbackFile = File(outDir, "$safeName.$fallbackExt")
            mergedVideo.copyTo(fallbackFile, overwrite = true)
            completedOk = true
            return@coroutineScope fallbackFile
        } finally {
            LocalStreamProxy.unregisterTaskCacheDir(task.id)
            if (completedOk) tmpDir.deleteRecursively()
        }
    }

    private suspend fun downloadDashDualTrack(outDir: File, safeName: String): File = coroutineScope {
        val tmpDir = File(context.cacheDir, "dash_${task.id}")
        tmpDir.mkdirs()
        var completedOk = false
        try {
            val videoTmp = File(tmpDir, "video.m4s")
            val audioTmp = File(tmpDir, "audio.m4s")
            val totalDl = AtomicLong(0)
            val monitor = ThrottleMonitor()

            task.speedText = "正在高速并发下载视频轨..."
            onProgress()
            downloadTrackResumable({ task.url }, videoTmp, totalDl, monitor, 0, 68)

            if (cancelled.get()) throw CancellationException()

            task.speedText = "正在下载高品质独立音频轨..."
            onProgress()
            downloadTrackResumable({ task.audioUrl }, audioTmp, totalDl, monitor, 68, 94)

            if (cancelled.get()) throw CancellationException()

            if (AndroidMediaMuxer.isHtmlOrInvalidFile(videoTmp) || AndroidMediaMuxer.isHtmlOrInvalidFile(audioTmp)) {
                // 凭证失效导致返回错误页时，强制刷新源站直链并重下校验
                task.speedText = "检测到音视频流失效，刷新令牌重新拉取..."
                onProgress()
                CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
                videoTmp.delete()
                audioTmp.delete()
                downloadTrackResumable({ task.url }, videoTmp, totalDl, monitor, 0, 68)
                downloadTrackResumable({ task.audioUrl }, audioTmp, totalDl, monitor, 68, 94)
            }

            task.status = TaskStatus.MUXING
            task.speedText = "FFmpeg 音画无损混流中..."
            task.progress = 96
            onProgress()

            val outMp4 = File(outDir, "$safeName.mp4")
            // 智能流探测：对于泛网站配对双流 (dual_dash)，若视频文件本身已自带原生音轨，优先保留其原生音画避免误被背景音乐替换；
            // 若视频轨无声音 (!vIn.second) 或为 B站标准 DASH，立即调用 FFmpeg 进行双轨无损合并！
            val vIn = AndroidMediaMuxer.probeStreamPresence(videoTmp)
            if (task.mediaType == "dual_dash" && vIn.first && vIn.second) {
                task.speedText = "视频自身已含完整音画，正在封装标准 MP4..."
                onProgress()
                if (!AndroidMediaMuxer.remuxTsToMp4(videoTmp, outMp4)) {
                    videoTmp.copyTo(outMp4, overwrite = true)
                }
            } else {
                val ok = AndroidMediaMuxer.muxVideoAndAudio(videoTmp, audioTmp, outMp4)
                if (!ok || !outMp4.exists() || outMp4.length() < 1024) {
                    throw Exception("FFmpeg 音画双轨合成 MP4 失败（请下拉刷新令牌后重试）")
                }
            }
            completedOk = true
            outMp4
        } finally {
            LocalStreamProxy.unregisterTaskCacheDir(task.id)
            if (completedOk) tmpDir.deleteRecursively()
        }
    }

    private suspend fun downloadSingleFile(outDir: File, safeName: String): File = coroutineScope {
        val cleanPath = task.url.substringBefore("?").substringBefore("#").lowercase()
        val urlExt = cleanPath.substringAfterLast('.', "")
        val knownExts = (AppConfig.getSniffExtensions() + listOf("mp4", "mkv", "webm", "flv", "mov", "avi", "mp3", "m4a", "aac", "flac", "wav", "ogg", "opus", "pdf", "zip", "rar", "7z", "apk")).toSet()
        val ext = when {
            urlExt in knownExts -> urlExt
            task.mediaType == "audio" -> "m4a"
            task.mediaType == "file" -> "bin"
            else -> "mp4"
        }
        val outFile = File(outDir, "$safeName.$ext")
        task.outputPath = outFile.absolutePath
        val totalDl = AtomicLong(0)
        val monitor = ThrottleMonitor()

        downloadTrackResumable({ task.url }, outFile, totalDl, monitor, 0, 98)

        if (ext in listOf("flv", "ts", "mkv", "webm") && AppConfig.autoConvertMp4 && task.mediaType != "file") {
            val mp4Out = File(outDir, "$safeName.mp4")
            if (mp4Out.absolutePath != outFile.absolutePath) {
                task.status = TaskStatus.MUXING
                task.speedText = "正在封装标准 MP4..."
                onProgress()
                if (AndroidMediaMuxer.remuxTsToMp4(outFile, mp4Out)) {
                    outFile.delete()
                    return@coroutineScope mp4Out
                }
            }
        }
        outFile
    }

    /**
     * 移植 PC 端多线程 Range 分块 + 单流断点续传 + 自动刷新令牌加速
     */
    private suspend fun downloadTrackResumable(
        urlSupplier: () -> String,
        destFile: File,
        sharedDl: AtomicLong,
        monitor: ThrottleMonitor,
        progStart: Int,
        progSpanStartToEnd: Int
    ) = coroutineScope {
        val threads = (if (task.threadOverride > 0) task.threadOverride else AppConfig.threadCount).coerceIn(1, 24)
        var targetUrl = urlSupplier()
        var totalLen = -1L
        var acceptRanges = false

        // 先探测资源长度与 Range 支持，若遇 401/403/412 自动刷新令牌后再试
        for (probeTry in 0..1) {
            var retryProbe = false
            try {
                val client = HttpClientProvider.getClient()
                val probeReq = buildRequest(targetUrl).newBuilder().header("Range", "bytes=0-0").build()
                client.newCall(probeReq).execute().use { r ->
                    if (r.code == 206 || r.code == 200) {
                        acceptRanges = r.code == 206 || (r.header("Accept-Ranges") ?: "").contains("bytes", ignoreCase = true)
                        val cr = r.header("Content-Range") ?: ""
                        if (cr.contains("/")) {
                            totalLen = cr.substringAfterLast("/").trim().toLongOrNull() ?: -1L
                        }
                        if (totalLen <= 0L && r.code == 200) {
                            totalLen = r.header("Content-Length")?.toLongOrNull() ?: -1L
                        }
                    } else if (r.code in listOf(401, 403, 410, 412) && probeTry == 0) {
                        CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
                        targetUrl = urlSupplier()
                        retryProbe = true
                    }
                }
            } catch (_: Exception) {
                break
            }
            if (!retryProbe) break
        }

        if (acceptRanges && totalLen >= 2 * 1024 * 1024 && threads > 1) {
            task.totalBytes = maxOf(task.totalBytes, totalLen)
            val partDir = File(destFile.parentFile, ".parts_${destFile.name}")
            partDir.mkdirs()

            val chunkSize = (totalLen / threads).coerceAtLeast(256 * 1024)
            val ranges = mutableListOf<Pair<Long, Long>>()
            var s = 0L
            while (s < totalLen) {
                val e = minOf(s + chunkSize - 1, totalLen - 1)
                ranges.add(s to e)
                s = e + 1
            }

            // 统计已存在的分块续传字节
            var preDone = 0L
            ranges.forEachIndexed { idx, (rs, re) ->
                val pf = File(partDir, "p_$idx")
                if (pf.exists()) {
                    val expected = re - rs + 1
                    val plen = pf.length().coerceIn(0L, expected)
                    if (pf.length() != plen) pf.delete() else preDone += plen
                }
            }
            if (preDone > 0) sharedDl.addAndGet(preDone)

            val sem = Semaphore(threads)
            val refreshLock = Any()
            val jobs = ranges.mapIndexed { idx, (rs, re) ->
                async {
                    sem.withPermit {
                        val partFile = File(partDir, "p_$idx")
                        var curStart = rs + (if (partFile.exists()) partFile.length() else 0L)
                        if (curStart > re) return@withPermit

                        var attempt = 0
                        while (attempt < 5) {
                            if (cancelled.get()) throw CancellationException()
                            var boostedReconnect = false
                            try {
                                val reqUrl = urlSupplier()
                                val req = buildRequest(reqUrl).newBuilder()
                                    .header("Range", "bytes=$curStart-$re")
                                    .build()
                                HttpClientProvider.getClient().newCall(req).execute().use { resp ->
                                    if (resp.code in listOf(401, 403, 410, 412)) {
                                        synchronized(refreshLock) {
                                            task.speedText = "HTTP ${resp.code} 刷新令牌中..."
                                            onProgress()
                                            CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
                                        }
                                        delay(500)
                                        attempt++
                                        boostedReconnect = true
                                    } else {
                                        if (!resp.isSuccessful) throw Exception("Range HTTP ${resp.code}")
                                        val body = resp.body ?: throw Exception("空分块")
                                        val append = curStart > rs
                                        FileOutputStream(partFile, append).use { fos ->
                                            body.byteStream().use { inp ->
                                                val buf = ByteArray(32 * 1024)
                                                while (true) {
                                                    if (cancelled.get()) throw CancellationException()
                                                    val n = inp.read(buf)
                                                    if (n <= 0) break
                                                    fos.write(buf, 0, n)
                                                    curStart += n
                                                    val cur = sharedDl.addAndGet(n.toLong())
                                                    val remRatio = ((totalLen - cur).coerceAtLeast(0L)).toDouble() / totalLen.coerceAtLeast(1L)
                                                    val (bps, needBoost) = synchronized(monitor) {
                                                        monitor.updateAndCheckBoost(cur, remRatio, tokenBoostRequested)
                                                    }
                                                    task.downloadedBytes = cur
                                                    val span = (progSpanStartToEnd - progStart).coerceAtLeast(1)
                                                    task.progress = (progStart + (cur * span.toDouble() / totalLen.coerceAtLeast(1L))).toInt().coerceIn(progStart, progSpanStartToEnd)
                                                    if (needBoost) {
                                                        synchronized(refreshLock) {
                                                            task.speedText = "智能刷新令牌提速中..."
                                                            onProgress()
                                                            CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
                                                        }
                                                        boostedReconnect = true
                                                        break
                                                    }
                                                    task.speedText = "${formatSpeed(bps.toLong())} (${threads}线程)"
                                                    onProgress()
                                                }
                                            }
                                        }
                                    }
                                }
                                if (curStart > re) return@withPermit
                                if (!boostedReconnect) attempt++
                            } catch (ce: CancellationException) {
                                throw ce
                            } catch (e: Exception) {
                                attempt++
                                if (attempt >= 5) throw e
                                delay(500)
                            }
                        }
                    }
                }
            }
            jobs.awaitAll()
            if (cancelled.get()) throw CancellationException()

            FileOutputStream(destFile, false).use { outFos ->
                val buf = ByteArray(64 * 1024)
                for (idx in ranges.indices) {
                    val pf = File(partDir, "p_$idx")
                    if (!pf.exists()) throw Exception("缺失分块 #$idx")
                    pf.inputStream().use { inp ->
                        while (true) {
                            val n = inp.read(buf)
                            if (n <= 0) break
                            outFos.write(buf, 0, n)
                        }
                    }
                }
            }
            partDir.deleteRecursively()
            return@coroutineScope
        }

        // 单流支持断点续传 + 自动刷新令牌提速
        var downloadedForFile = if (destFile.exists()) destFile.length() else 0L
        if (downloadedForFile > 0) sharedDl.addAndGet(downloadedForFile)

        var attempt = 0
        while (attempt < 5) {
            if (cancelled.get()) throw CancellationException()
            val reqUrl = urlSupplier()
            val reqB = buildRequest(reqUrl).newBuilder()
            if (downloadedForFile > 0) reqB.header("Range", "bytes=$downloadedForFile-")

            var needReconnect = false
            var countAsRetry = false
            HttpClientProvider.getClient().newCall(reqB.build()).execute().use { resp ->
                if (resp.code in listOf(401, 403, 410, 412)) {
                    task.speedText = "HTTP ${resp.code} 自动刷新令牌..."
                    onProgress()
                    CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
                    needReconnect = true
                    countAsRetry = true
                } else if (resp.code == 416) {
                    return@coroutineScope
                } else {
                    if (!resp.isSuccessful) throw Exception("HTTP ${resp.code}")

                    val append = resp.code == 206 && downloadedForFile > 0
                    if (!append && downloadedForFile > 0) {
                        sharedDl.addAndGet(-downloadedForFile)
                        downloadedForFile = 0L
                    }
                    val body = resp.body ?: throw Exception("空响应体")
                    val cLen = body.contentLength()
                    val estTotal = if (cLen > 0) downloadedForFile + cLen else totalLen
                    if (estTotal > 0) task.totalBytes = maxOf(task.totalBytes, estTotal)

                    FileOutputStream(destFile, append).use { out ->
                        body.byteStream().use { inp ->
                            val buf = ByteArray(32 * 1024)
                            while (true) {
                                if (cancelled.get()) throw CancellationException()
                                val n = inp.read(buf)
                                if (n <= 0) break
                                out.write(buf, 0, n)
                                downloadedForFile += n
                                val cur = sharedDl.addAndGet(n.toLong())
                                val denom = estTotal.coerceAtLeast(1L)
                                val remRatio = if (estTotal > 0) ((estTotal - downloadedForFile).coerceAtLeast(0L)).toDouble() / denom else 0.5
                                val (bps, needBoost) = monitor.updateAndCheckBoost(cur, remRatio, tokenBoostRequested)
                                task.downloadedBytes = cur
                                if (estTotal > 0) {
                                    val span = (progSpanStartToEnd - progStart).coerceAtLeast(1)
                                    task.progress = (progStart + (downloadedForFile * span.toDouble() / denom)).toInt().coerceIn(progStart, progSpanStartToEnd)
                                }
                                if (needBoost && downloadedForFile < estTotal) {
                                    task.speedText = "智能刷新令牌提速中..."
                                    onProgress()
                                    CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
                                    needReconnect = true
                                    break
                                }
                                task.speedText = formatSpeed(bps.toLong())
                                onProgress()
                            }
                        }
                    }
                }
            }
            if (!needReconnect) break
            if (countAsRetry) attempt++
            delay(350)
        }
    }

    private fun decryptAes128(data: ByteArray, key: ByteArray, iv: ByteArray): ByteArray {
        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), IvParameterSpec(iv))
        return cipher.doFinal(data)
    }

    private fun defaultIv(seq: Int): ByteArray {
        val iv = ByteArray(16)
        iv[14] = ((seq shr 8) and 0xFF).toByte()
        iv[15] = (seq and 0xFF).toByte()
        return iv
    }

    private fun hexToBytes(hex: String): ByteArray {
        val clean = hex.padStart(32, '0').takeLast(32)
        return ByteArray(16) { i -> clean.substring(i * 2, i * 2 + 2).toInt(16).toByte() }
    }

    private fun formatSpeed(bps: Long): String {
        return when {
            bps >= 1024 * 1024 -> String.format("%.2f MB/s", bps / (1024.0 * 1024.0))
            bps >= 1024 -> String.format("%.1f KB/s", bps / 1024.0)
            else -> "$bps B/s"
        }
    }
}

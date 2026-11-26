package com.starstream.downloader.core

import android.content.Context
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
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
    private val directClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .followRedirects(true)
            .followSslRedirects(true)
            .build()
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
 * 原生流媒体与多线程直链下载核心引擎
 * 修复：
 * 1. 支持 Master M3U8 中 #EXT-X-MEDIA:TYPE=AUDIO 分离音轨抓取与混流
 * 2. B站 DASH 嗅探若漏掉音轨，自动通过 pageUrl 二次补齐 AAC 音轨
 * 3. 单文件支持按 AppConfig.threadCount 多线程 Range 分块并发下载
 */
class DownloadRunner(
    private val context: Context,
    private val task: DownloadTask,
    private val onProgress: () -> Unit
) {
    private val cancelled = AtomicBoolean(false)
    private var job: Job? = null

    fun cancel() {
        cancelled.set(true)
        job?.cancel()
    }

    fun start(scope: CoroutineScope, onComplete: (Boolean, String) -> Unit) {
        job = scope.launch(Dispatchers.IO) {
            try {
                task.status = TaskStatus.DOWNLOADING
                task.errorMsg = ""
                onProgress()

                // 自动补齐未配对的 B 站音轨，防止下载成静音视频
                val lowerUrl = task.url.lowercase().split("?")[0]
                val isBiliVideoOnly = (task.mediaType == "bili_dash" || lowerUrl.contains("bilivideo") || lowerUrl.contains("hdslb.com")) &&
                    !lowerUrl.contains("302") && task.audioUrl.isBlank() && task.pageUrl.contains("bilibili.com")
                if (isBiliVideoOnly) {
                    task.speedText = "正在补齐 B站音轨..."
                    onProgress()
                    try {
                        val recovered = VideoParser.parseVideoUrl(task.pageUrl, task.headers)
                        if (recovered.success && recovered.audioUrl.isNotBlank()) {
                            task.audioUrl = recovered.audioUrl
                            if (recovered.url.isNotBlank()) task.url = recovered.url
                        }
                    } catch (_: Exception) {}
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
                    onComplete(false, "已暂停/取消")
                    return@launch
                }

                if (AppConfig.saveToGallery || AppConfig.customSaveUri.isNotBlank()) {
                    AndroidMediaMuxer.exportToPublicDownloads(context, outFile, task.subDir)
                }
                task.outputPath = outFile.absolutePath
                task.progress = 100
                task.speedText = "完成"
                task.status = TaskStatus.COMPLETED
                onProgress()
                onComplete(true, "下载完成")
            } catch (e: CancellationException) {
                task.status = TaskStatus.PAUSED
                task.speedText = "已暂停"
                onProgress()
                onComplete(false, "任务已暂停")
            } catch (e: Exception) {
                task.status = TaskStatus.ERROR
                task.errorMsg = e.message ?: "下载异常"
                task.speedText = "失败"
                onProgress()
                onComplete(false, task.errorMsg)
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

    private fun fetchBytes(url: String): ByteArray? {
        val client = HttpClientProvider.getClient()
        for (retry in 0..2) {
            if (cancelled.get()) return null
            try {
                client.newCall(buildRequest(url)).execute().use { resp ->
                    if (resp.isSuccessful) {
                        return resp.body?.bytes()
                    }
                }
            } catch (_: Exception) {
                if (retry < 2) Thread.sleep(400)
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
        val startTime = System.currentTimeMillis()
        val semaphore = Semaphore(AppConfig.threadCount)

        val initBytes = if (parsed.initUrl.isNotEmpty()) fetchBytes(parsed.initUrl) else null

        val jobs = parsed.segments.mapIndexed { idx, segUrl ->
            async {
                semaphore.withPermit {
                    if (cancelled.get()) return@withPermit
                    var bytes = fetchBytes(segUrl) ?: throw Exception("分片 #$idx 拉取失败")
                    bytes = unwrapMediaBytes(bytes)
                    if (parsed.aesKey != null) {
                        bytes = decryptAes128(bytes, parsed.aesKey, parsed.aesIv ?: defaultIv(idx))
                    }
                    val segFile = File(tmpDir, "${prefix}_%05d.ts".format(idx))
                    FileOutputStream(segFile).use { it.write(bytes) }

                    val done = doneCount.incrementAndGet()
                    val dlBytes = totalDownloaded.addAndGet(bytes.size.toLong())
                    val elapsedSec = ((System.currentTimeMillis() - startTime) / 1000.0).coerceAtLeast(0.1)
                    task.downloadedBytes = dlBytes
                    task.progress = (progressBase + (done * progressSpan.toDouble()) / totalCount).toInt().coerceIn(1, 95)
                    task.speedText = formatSpeed((dlBytes / elapsedSec).toLong())
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
        val rawM3u8 = fetchBytes(task.url) ?: throw Exception("无法拉取 M3U8 清单 (防盗链或网络异常)")
        var m3u8Text = String(unwrapMediaBytes(rawM3u8), Charsets.UTF_8)
        var baseUrl = task.url
        var audioPlaylistUrl = ""

        // 1. 处理 Master Playlist：选择最高画质视频轨 + 检查是否含独立 #EXT-X-MEDIA 音频轨
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

        val tmpDir = File(context.cacheDir, "seg_${task.id}_${System.currentTimeMillis()}")
        tmpDir.mkdirs()
        LocalStreamProxy.registerTaskCacheDir(task.id, tmpDir)

        try {
            val videoSpan = if (parsedAudio != null) 75 else 95
            val mergedVideo = downloadPlaylistSegments(parsedVideo, tmpDir, "vseg", 0, videoSpan)
            val mergedAudio = if (parsedAudio != null) {
                downloadPlaylistSegments(parsedAudio, tmpDir, "aseg", 75, 20)
            } else null

            task.status = TaskStatus.MUXING
            task.speedText = "正在封装有声 MP4..."
            onProgress()

            val finalMp4 = File(outDir, "$safeName.mp4")
            if (mergedAudio != null) {
                if (AndroidMediaMuxer.muxVideoAndAudio(mergedVideo, mergedAudio, finalMp4)) {
                    task.totalBytes = finalMp4.length()
                    return@coroutineScope finalMp4
                }
            }
            if (AppConfig.autoConvertMp4 && AndroidMediaMuxer.remuxTsToMp4(mergedVideo, finalMp4)) {
                task.totalBytes = finalMp4.length()
                return@coroutineScope finalMp4
            } else {
                val fallbackTs = File(outDir, "$safeName.ts")
                mergedVideo.copyTo(fallbackTs, overwrite = true)
                task.totalBytes = fallbackTs.length()
                return@coroutineScope fallbackTs
            }
        } finally {
            LocalStreamProxy.unregisterTaskCacheDir(task.id)
            tmpDir.deleteRecursively()
        }
    }

    private suspend fun downloadDashDualTrack(outDir: File, safeName: String): File = coroutineScope {
        val tmpDir = File(context.cacheDir, "dash_${task.id}_${System.currentTimeMillis()}")
        tmpDir.mkdirs()
        try {
            val videoTmp = File(tmpDir, "video.m4s")
            val audioTmp = File(tmpDir, "audio.m4s")
            val totalDl = AtomicLong(0)
            val startTime = System.currentTimeMillis()

            val vJob = async { streamToFile(task.url, videoTmp, totalDl, startTime) }
            val aJob = async { streamToFile(task.audioUrl, audioTmp, totalDl, startTime) }
            awaitAll(vJob, aJob)

            if (cancelled.get()) throw CancellationException()

            task.status = TaskStatus.MUXING
            task.speedText = "音画无损合并中..."
            task.progress = 96
            onProgress()

            val outMp4 = File(outDir, "$safeName.mp4")
            val ok = AndroidMediaMuxer.muxVideoAndAudio(videoTmp, audioTmp, outMp4)
            if (!ok || !outMp4.exists() || outMp4.length() < 1024) {
                throw Exception("音画双轨合成 MP4 失败")
            }
            task.totalBytes = outMp4.length()
            outMp4
        } finally {
            LocalStreamProxy.unregisterTaskCacheDir(task.id)
            tmpDir.deleteRecursively()
        }
    }

    private suspend fun downloadSingleFile(outDir: File, safeName: String): File = coroutineScope {
        val cleanPath = task.url.substringBefore("?").substringBefore("#").lowercase()
        val urlExt = cleanPath.substringAfterLast('.', "")
        val knownExts = setOf("mp4", "mkv", "webm", "flv", "mov", "avi", "mp3", "m4a", "aac", "flac", "wav", "ogg", "opus", "pdf", "zip", "rar", "7z", "apk", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "epub", "txt", "iso")
        val ext = when {
            urlExt in knownExts -> urlExt
            task.mediaType == "audio" -> "m4a"
            task.mediaType == "file" -> "bin"
            else -> "mp4"
        }
        val outFile = File(outDir, "$safeName.$ext")
        task.outputPath = outFile.absolutePath
        val totalDl = AtomicLong(0)
        val startTime = System.currentTimeMillis()

        // 当用户设置多线程 > 1 且大直链支持 Range 时，启用 HTTP Range 分块多线程并发下载
        val threads = AppConfig.threadCount.coerceIn(1, 16)
        var usedMultiThread = false
        if (threads > 1) {
            try {
                val client = HttpClientProvider.getClient()
                val headReq = buildRequest(task.url).newBuilder().head().build()
                var totalLen = -1L
                var acceptRanges = false
                client.newCall(headReq).execute().use { r ->
                    if (r.isSuccessful) {
                        totalLen = r.header("Content-Length")?.toLongOrNull() ?: -1L
                        acceptRanges = (r.header("Accept-Ranges") ?: "").contains("bytes", ignoreCase = true)
                    }
                }
                if (acceptRanges && totalLen >= 2 * 1024 * 1024) {
                    usedMultiThread = true
                    task.totalBytes = totalLen
                    RandomAccessFile(outFile, "rw").use { it.setLength(totalLen) }
                    val chunkSize = (totalLen / threads).coerceAtLeast(512 * 1024)
                    val ranges = mutableListOf<Pair<Long, Long>>()
                    var start = 0L
                    while (start < totalLen) {
                        val end = minOf(start + chunkSize - 1, totalLen - 1)
                        ranges.add(start to end)
                        start = end + 1
                    }
                    val sem = Semaphore(threads)
                    val jobs = ranges.map { (s, e) ->
                        async {
                            sem.withPermit {
                                val rangeReq = buildRequest(task.url).newBuilder()
                                    .header("Range", "bytes=$s-$e")
                                    .build()
                                client.newCall(rangeReq).execute().use { resp ->
                                    if (!resp.isSuccessful) throw Exception("Range HTTP ${resp.code}")
                                    val body = resp.body ?: throw Exception("空分块")
                                    body.byteStream().use { inp ->
                                        RandomAccessFile(outFile, "rw").use { raf ->
                                            raf.seek(s)
                                            val buf = ByteArray(16 * 1024)
                                            while (true) {
                                                if (cancelled.get()) throw CancellationException()
                                                val n = inp.read(buf)
                                                if (n <= 0) break
                                                raf.write(buf, 0, n)
                                                val cur = totalDl.addAndGet(n.toLong())
                                                task.downloadedBytes = cur
                                                val elapsed = ((System.currentTimeMillis() - startTime) / 1000.0).coerceAtLeast(0.1)
                                                task.speedText = "${formatSpeed((cur / elapsed).toLong())} (${threads}线程)"
                                                task.progress = ((cur * 98.0) / totalLen).toInt().coerceIn(1, 98)
                                                onProgress()
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    jobs.awaitAll()
                }
            } catch (_: Exception) {
                usedMultiThread = false
                totalDl.set(0)
                task.totalBytes = 0
            }
        }

        if (!usedMultiThread) {
            streamToFile(task.url, outFile, totalDl, startTime)
        }
        task.totalBytes = outFile.length()
        outFile
    }

    private fun streamToFile(url: String, destFile: File, sharedBytes: AtomicLong, startTime: Long) {
        val client = HttpClientProvider.getClient()
        client.newCall(buildRequest(url)).execute().use { resp ->
            if (!resp.isSuccessful) throw Exception("HTTP ${resp.code}")
            val body = resp.body ?: throw Exception("空响应体")
            val len = body.contentLength()
            if (len > 0) task.totalBytes += len
            body.byteStream().use { inp ->
                FileOutputStream(destFile).use { out ->
                    val buf = ByteArray(16 * 1024)
                    while (true) {
                        if (cancelled.get()) throw CancellationException()
                        val n = inp.read(buf)
                        if (n <= 0) break
                        out.write(buf, 0, n)
                        val cur = sharedBytes.addAndGet(n.toLong())
                        task.downloadedBytes = cur
                        val elapsed = ((System.currentTimeMillis() - startTime) / 1000.0).coerceAtLeast(0.1)
                        task.speedText = formatSpeed((cur / elapsed).toLong())
                        if (task.totalBytes > 0) {
                            task.progress = ((cur * 95.0) / task.totalBytes).toInt().coerceIn(1, 95)
                        }
                        onProgress()
                    }
                }
            }
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

package com.starstream.downloader.core

import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.io.RandomAccessFile
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * 本地高速流媒体代理服务：
 * 1. 为外部播放器提供携带原始 Referer / Cookie / User-Agent 的 127.0.0.1 在线预览地址（防 403）
 * 2. 支持“边下边看”：优先读取本地已落盘分片/文件，未就绪部分无缝透传上游节点
 * 3. 自动重写 M3U8 子清单与切片路径，适配外部专业播放器与内置播放器
 */
object LocalStreamProxy {

    data class StreamSource(
        val token: String,
        val url: String,
        val mediaType: String,
        val headers: Map<String, String>,
        val taskId: String = ""
    )

    private val sources = ConcurrentHashMap<String, StreamSource>()
    private val taskCacheDirs = ConcurrentHashMap<String, File>()
    private val executor = Executors.newCachedThreadPool()

    @Volatile
    private var serverSocket: ServerSocket? = null

    @Volatile
    private var localPort: Int = 0

    @Synchronized
    fun ensureStarted(): Int {
        if (localPort > 0 && serverSocket != null && serverSocket?.isClosed == false) {
            return localPort
        }
        val ss = ServerSocket(0, 64, InetAddress.getByName("127.0.0.1"))
        serverSocket = ss
        localPort = ss.localPort
        val t = Thread {
            while (!ss.isClosed) {
                try {
                    val client = ss.accept()
                    executor.execute { handleClient(client) }
                } catch (_: Throwable) {
                    if (ss.isClosed) break
                }
            }
        }
        t.isDaemon = true
        t.name = "StarStream-LocalProxy"
        t.start()
        return localPort
    }

    fun registerTaskCacheDir(taskId: String, dir: File) {
        if (taskId.isNotBlank()) taskCacheDirs[taskId] = dir
    }

    fun unregisterTaskCacheDir(taskId: String) {
        taskCacheDirs.remove(taskId)
    }

    fun buildPreviewUrl(
        url: String,
        mediaType: String,
        headers: Map<String, String>,
        taskId: String = ""
    ): String {
        val port = ensureStarted()
        val token = UUID.randomUUID().toString().replace("-", "").take(12)
        sources[token] = StreamSource(token, url, mediaType, HashMap(headers), taskId)
        val ext = when {
            mediaType == "m3u8" || url.lowercase().contains(".m3u8") -> ".m3u8"
            mediaType == "audio" -> ".m4a"
            else -> ".mp4"
        }
        return "http://127.0.0.1:$port/play/$token$ext"
    }

    fun buildTaskStreamUrl(task: DownloadTask): String {
        val port = ensureStarted()
        val existing = sources.values.firstOrNull { it.taskId == task.id }
        val token = existing?.token ?: UUID.randomUUID().toString().replace("-", "").take(12).also { tok ->
            sources[tok] = StreamSource(tok, task.url, task.mediaType, HashMap(task.headers), task.id)
        }
        val ext = if (task.mediaType == "m3u8" || task.url.lowercase().contains(".m3u8")) ".m3u8" else ".mp4"
        return "http://127.0.0.1:$port/play/$token$ext"
    }

    private fun handleClient(socket: Socket) {
        socket.use { sock ->
            try {
                sock.soTimeout = 15000
                val inp = BufferedInputStream(sock.getInputStream())
                val out = BufferedOutputStream(sock.getOutputStream())

                val reqLine = readLineAscii(inp) ?: return
                val parts = reqLine.split(" ")
                if (parts.size < 2) return
                val method = parts[0].uppercase()
                val rawPath = parts[1]

                val reqHeaders = mutableMapOf<String, String>()
                while (true) {
                    val line = readLineAscii(inp) ?: break
                    if (line.isEmpty()) break
                    val idx = line.indexOf(':')
                    if (idx > 0) {
                        reqHeaders[line.substring(0, idx).trim().lowercase()] = line.substring(idx + 1).trim()
                    }
                }

                if (method != "GET" && method != "HEAD") {
                    sendSimpleError(out, 405, "Method Not Allowed")
                    return
                }

                when {
                    rawPath.startsWith("/play/") -> {
                        val token = rawPath.removePrefix("/play/").substringBefore("?").substringBefore(".")
                        val src = sources[token]
                        if (src == null) {
                            sendSimpleError(out, 404, "Not Found")
                            return
                        }
                        servePlayRequest(out, src, method, reqHeaders["range"])
                    }
                    rawPath.startsWith("/seg") -> {
                        val q = rawPath.substringAfter("?", "")
                        val params = parseQuery(q)
                        val tok = params["t"] ?: ""
                        val encUrl = params["u"] ?: ""
                        val idxStr = params["idx"] ?: ""
                        val src = sources[tok]
                        if (src == null || encUrl.isEmpty()) {
                            sendSimpleError(out, 404, "Missing segment info")
                            return
                        }
                        val targetUrl = String(Base64.decode(encUrl, Base64.URL_SAFE or Base64.NO_WRAP), Charsets.UTF_8)
                        serveUpstreamOrCache(out, src, targetUrl, idxStr.toIntOrNull(), method, reqHeaders["range"])
                    }
                    else -> sendSimpleError(out, 404, "Unknown route")
                }
            } catch (_: Throwable) {}
        }
    }

    private fun servePlayRequest(out: BufferedOutputStream, src: StreamSource, method: String, rangeHeader: String?) {
        // 如果对应下载任务已彻底完成且本地文件可读，直接走本地 Range 极速秒开
        if (src.taskId.isNotBlank()) {
            val task = TaskManager.getAllTasks().find { it.id == src.taskId }
            if (task != null && task.status == TaskStatus.COMPLETED && task.outputPath.isNotBlank()) {
                val f = File(task.outputPath)
                if (f.exists() && f.length() > 0) {
                    serveLocalFile(out, f, method, rangeHeader)
                    return
                }
            }
        }

        val lower = src.url.lowercase().substringBefore("?")
        if (src.mediaType == "m3u8" || lower.endsWith(".m3u8") || lower.contains("/api/hls/")) {
            serveRewrittenM3u8(out, src, src.url, method)
        } else {
            serveUpstreamOrCache(out, src, src.url, null, method, rangeHeader)
        }
    }

    private fun serveRewrittenM3u8(out: BufferedOutputStream, src: StreamSource, playlistUrl: String, method: String) {
        val bytes = fetchUpstreamBytes(playlistUrl, src.headers)
        if (bytes == null) {
            sendSimpleError(out, 502, "Failed to fetch M3U8")
            return
        }
        val rawText = String(unwrapPngWrapper(bytes), Charsets.UTF_8)
        var targetUrl = playlistUrl
        var m3u8Text = rawText

        // 若是 Master 清单，自动展开最佳画质子列表
        if (m3u8Text.contains("#EXT-X-STREAM-INF")) {
            val lines = m3u8Text.lines()
            var bestUrl = ""
            var bestBw = -1L
            for (i in lines.indices) {
                val l = lines[i].trim()
                if (l.startsWith("#EXT-X-STREAM-INF") && i + 1 < lines.size) {
                    val bw = Regex("BANDWIDTH=(\\d+)").find(l)?.groupValues?.get(1)?.toLongOrNull() ?: 0L
                    val next = lines[i + 1].trim()
                    if (next.isNotEmpty() && !next.startsWith("#") && bw >= bestBw) {
                        bestBw = bw
                        bestUrl = URL(URL(targetUrl), next).toString()
                    }
                }
            }
            if (bestUrl.isNotEmpty()) {
                val subBytes = fetchUpstreamBytes(bestUrl, src.headers)
                if (subBytes != null) {
                    targetUrl = bestUrl
                    m3u8Text = String(unwrapPngWrapper(subBytes), Charsets.UTF_8)
                }
            }
        }

        val querySuffix = if (targetUrl.contains("?")) targetUrl.substringAfter("?") else if (src.url.contains("?")) src.url.substringAfter("?") else ""
        val sb = StringBuilder()
        var segIdx = 0
        for (rawLine in m3u8Text.lines()) {
            val line = rawLine.trim()
            if (line.isEmpty()) continue
            if (line.startsWith("#EXT-X-KEY") || line.startsWith("#EXT-X-MAP")) {
                val uriMatch = Regex("URI=\"([^\"]+)\"").find(line)
                if (uriMatch != null) {
                    var abs = URL(URL(targetUrl), uriMatch.groupValues[1]).toString()
                    if (querySuffix.isNotEmpty() && !abs.contains("?")) abs = "$abs?$querySuffix"
                    val b64 = Base64.encodeToString(abs.toByteArray(Charsets.UTF_8), Base64.URL_SAFE or Base64.NO_WRAP)
                    val proxySeg = "http://127.0.0.1:$localPort/seg?t=${src.token}&u=$b64"
                    sb.append(line.replace(uriMatch.value, "URI=\"$proxySeg\"")).append('\n')
                    continue
                }
                sb.append(line).append('\n')
                continue
            }
            if (line.startsWith("#")) {
                sb.append(line).append('\n')
                continue
            }
            var segUrl = URL(URL(targetUrl), line).toString()
            if (querySuffix.isNotEmpty() && !segUrl.contains("?")) segUrl = "$segUrl?$querySuffix"
            val b64 = Base64.encodeToString(segUrl.toByteArray(Charsets.UTF_8), Base64.URL_SAFE or Base64.NO_WRAP)
            sb.append("http://127.0.0.1:$localPort/seg?t=${src.token}&idx=$segIdx&u=$b64\n")
            segIdx++
        }

        val payload = sb.toString().toByteArray(Charsets.UTF_8)
        val hdr = "HTTP/1.1 200 OK\r\n" +
            "Content-Type: application/vnd.apple.mpegurl; charset=utf-8\r\n" +
            "Content-Length: ${payload.size}\r\n" +
            "Access-Control-Allow-Origin: *\r\n" +
            "Connection: close\r\n\r\n"
        out.write(hdr.toByteArray(Charsets.US_ASCII))
        if (method != "HEAD") out.write(payload)
        out.flush()
    }

    private fun serveUpstreamOrCache(
        out: BufferedOutputStream,
        src: StreamSource,
        targetUrl: String,
        segIdx: Int?,
        method: String,
        rangeHeader: String?
    ) {
        // 检查本地分片缓存，命中则 0 延迟秒播
        if (segIdx != null && src.taskId.isNotBlank()) {
            val cacheDir = taskCacheDirs[src.taskId]
            if (cacheDir != null) {
                val cached = listOf(
                    File(cacheDir, "vseg_%05d.ts".format(segIdx)),
                    File(cacheDir, "seg_%05d.ts".format(segIdx))
                ).firstOrNull { it.exists() && it.length() > 0 }
                if (cached != null) {
                    serveLocalFile(out, cached, method, rangeHeader)
                    return
                }
            }
        }

        val reqB = Request.Builder().url(targetUrl)
        val ua = src.headers["User-Agent"] ?: AppConfig.getUserAgentString()
        reqB.header("User-Agent", ua)
        src.headers.forEach { (k, v) ->
            if (v.isNotBlank() && !k.equals("User-Agent", true)) reqB.header(k, v)
        }
        if (!rangeHeader.isNullOrBlank()) reqB.header("Range", rangeHeader)
        if (method == "HEAD") reqB.head()

        HttpClientProvider.getClient().newCall(reqB.build()).execute().use { resp ->
            val code = resp.code
            val statusMsg = if (code == 206) "Partial Content" else "OK"
            val cType = resp.header("Content-Type") ?: if (segIdx != null) "video/mp2t" else "video/mp4"
            val cLen = resp.header("Content-Length")
            val cRange = resp.header("Content-Range")
            val acceptRanges = resp.header("Accept-Ranges") ?: "bytes"

            val h = StringBuilder("HTTP/1.1 $code $statusMsg\r\n")
            h.append("Content-Type: $cType\r\n")
            h.append("Accept-Ranges: $acceptRanges\r\n")
            if (cLen != null) h.append("Content-Length: $cLen\r\n")
            if (cRange != null) h.append("Content-Range: $cRange\r\n")
            h.append("Access-Control-Allow-Origin: *\r\n")
            h.append("Connection: close\r\n\r\n")
            out.write(h.toString().toByteArray(Charsets.US_ASCII))

            if (method != "HEAD") {
                val body = resp.body ?: return
                body.byteStream().use { stream ->
                    val buf = ByteArray(32 * 1024)
                    while (true) {
                        val n = stream.read(buf)
                        if (n <= 0) break
                        out.write(buf, 0, n)
                    }
                }
            }
            out.flush()
        }
    }

    private fun serveLocalFile(out: BufferedOutputStream, file: File, method: String, rangeHeader: String?) {
        val total = file.length()
        val ext = file.extension.lowercase()
        val cType = when (ext) {
            "ts" -> "video/mp2t"
            "m3u8" -> "application/vnd.apple.mpegurl"
            "m4a", "mp3", "aac" -> "audio/mp4"
            else -> "video/mp4"
        }
        var start = 0L
        var end = total - 1L
        var isPartial = false
        if (!rangeHeader.isNullOrBlank() && rangeHeader.startsWith("bytes=")) {
            isPartial = true
            val spec = rangeHeader.removePrefix("bytes=").substringBefore(",")
            val sPart = spec.substringBefore("-").trim()
            val ePart = spec.substringAfter("-", "").trim()
            if (sPart.isNotEmpty()) start = sPart.toLongOrNull()?.coerceIn(0, total - 1) ?: 0L
            if (ePart.isNotEmpty()) end = ePart.toLongOrNull()?.coerceIn(start, total - 1) ?: (total - 1)
        }
        val len = (end - start + 1).coerceAtLeast(0L)
        val status = if (isPartial) "206 Partial Content" else "200 OK"
        val hdr = StringBuilder("HTTP/1.1 $status\r\n")
        hdr.append("Content-Type: $cType\r\n")
        hdr.append("Accept-Ranges: bytes\r\n")
        hdr.append("Content-Length: $len\r\n")
        if (isPartial) hdr.append("Content-Range: bytes $start-$end/$total\r\n")
        hdr.append("Connection: close\r\n\r\n")
        out.write(hdr.toString().toByteArray(Charsets.US_ASCII))

        if (method != "HEAD" && len > 0) {
            RandomAccessFile(file, "r").use { raf ->
                raf.seek(start)
                val buf = ByteArray(32 * 1024)
                var remain = len
                while (remain > 0) {
                    val toRead = minOf(buf.size.toLong(), remain).toInt()
                    val n = raf.read(buf, 0, toRead)
                    if (n <= 0) break
                    out.write(buf, 0, n)
                    remain -= n
                }
            }
        }
        out.flush()
    }

    private fun fetchUpstreamBytes(url: String, headers: Map<String, String>): ByteArray? {
        return try {
            val reqB = Request.Builder().url(url)
            val ua = headers["User-Agent"] ?: AppConfig.getUserAgentString()
            reqB.header("User-Agent", ua)
            headers.forEach { (k, v) ->
                if (v.isNotBlank() && !k.equals("User-Agent", true)) reqB.header(k, v)
            }
            HttpClientProvider.getClient().newCall(reqB.build()).execute().use { resp ->
                if (resp.isSuccessful) resp.body?.bytes() else null
            }
        } catch (_: Throwable) {
            null
        }
    }

    private fun unwrapPngWrapper(raw: ByteArray): ByteArray {
        if (raw.size < 16) return raw
        val pngMagic = byteArrayOf(137.toByte(), 80, 78, 71, 13, 10, 26, 10)
        for (i in pngMagic.indices) if (raw[i] != pngMagic[i]) return raw
        val buf = ByteBuffer.wrap(raw).order(ByteOrder.BIG_ENDIAN)
        var pos = 8
        while (pos + 8 <= raw.size) {
            val len = buf.getInt(pos)
            val ctype = buf.getInt(pos + 4)
            val x = pos + 8
            if (len < 0 || x + len > raw.size) break
            if (ctype == 1919898980) {
                val flags = raw[x].toInt()
                val payload = raw.copyOfRange(x + 1, x + len)
                return if ((flags and 1) != 0) inflateBytes(payload) else payload
            }
            pos = x + len + 4
        }
        return raw
    }

    private fun inflateBytes(data: ByteArray): ByteArray {
        val inflater = java.util.zip.Inflater()
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

    private fun parseQuery(q: String): Map<String, String> {
        val map = mutableMapOf<String, String>()
        if (q.isBlank()) return map
        q.split("&").forEach { pair ->
            val idx = pair.indexOf('=')
            if (idx > 0) map[pair.substring(0, idx)] = pair.substring(idx + 1)
        }
        return map
    }

    private fun readLineAscii(inp: InputStream): String? {
        val baos = ByteArrayOutputStream()
        var prev = -1
        while (true) {
            val b = inp.read()
            if (b == -1) return if (baos.size() == 0) null else String(baos.toByteArray(), Charsets.US_ASCII)
            if (b == '\n'.code) {
                val arr = baos.toByteArray()
                val len = if (prev == '\r'.code && arr.isNotEmpty()) arr.size - 1 else arr.size
                return String(arr, 0, len, Charsets.US_ASCII)
            }
            baos.write(b)
            prev = b
        }
    }

    private fun sendSimpleError(out: BufferedOutputStream, code: Int, msg: String) {
        val resp = "HTTP/1.1 $code $msg\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        out.write(resp.toByteArray(Charsets.US_ASCII))
        out.flush()
    }

    suspend fun openExternalPreview(
        context: android.content.Context,
        url: String,
        mediaType: String,
        headers: Map<String, String>,
        taskId: String = ""
    ): String = withContext(Dispatchers.IO) {
        buildPreviewUrl(url, mediaType, headers, taskId)
    }
}

package com.starstream.downloader.ui

import android.annotation.SuppressLint
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.starstream.downloader.R
import com.starstream.downloader.browser.SnifferScripts
import com.starstream.downloader.core.*
import kotlinx.coroutines.*
import java.util.UUID

class ParserActivity : AppCompatActivity() {

    private lateinit var rootContainer: ViewGroup
    private lateinit var etInput: EditText
    private lateinit var tvStatus: TextView
    private lateinit var btnBrowserFallback: Button
    private lateinit var cardSingle: View
    private lateinit var tvResTitle: TextView
    private lateinit var tvResMeta: TextView
    private lateinit var cardSeries: View
    private lateinit var tvSeriesTitle: TextView
    private lateinit var rvSeries: RecyclerView
    private lateinit var btnDownloadSeries: Button

    private var currentResult: ParseResult? = null
    private var lastParsedUrl: String = ""
    private var silentWebView: WebView? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_parser)

        val root = findViewById<ViewGroup>(R.id.root_parser_container)
        rootContainer = root
        ThemeManager.applyTheme(this, root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, windowInsets ->
            val insets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(insets.left, insets.top, insets.right, insets.bottom)
            windowInsets
        }

        findViewById<View>(R.id.btn_parser_back).setOnClickListener { finish() }

        etInput = findViewById(R.id.et_parse_input)
        tvStatus = findViewById(R.id.tv_parse_status)
        btnBrowserFallback = findViewById(R.id.btn_open_browser_fallback)
        cardSingle = findViewById(R.id.card_single_result)
        tvResTitle = findViewById(R.id.tv_res_title)
        tvResMeta = findViewById(R.id.tv_res_meta)
        cardSeries = findViewById(R.id.card_series_result)
        tvSeriesTitle = findViewById(R.id.tv_series_title)
        rvSeries = findViewById(R.id.rv_series_episodes)
        btnDownloadSeries = findViewById(R.id.btn_download_series)

        rvSeries.layoutManager = LinearLayoutManager(this)

        findViewById<Button>(R.id.btn_paste).setOnClickListener {
            val cb = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val txt = cb.primaryClip?.getItemAt(0)?.text?.toString() ?: ""
            etInput.setText(txt)
        }

        findViewById<Button>(R.id.btn_parse).setOnClickListener { startParse() }

        btnBrowserFallback.setOnClickListener {
            val u = lastParsedUrl.ifBlank { etInput.text.toString().trim() }
            if (u.startsWith("http")) {
                startActivity(Intent(this, BrowserActivity::class.java).putExtra("open_url", u))
                finish()
            }
        }

        findViewById<Button>(R.id.btn_download_single).setOnClickListener {
            val r = currentResult ?: return@setOnClickListener
            val task = DownloadTask(
                id = UUID.randomUUID().toString().take(8),
                title = r.title.ifBlank { "video" },
                url = r.url,
                audioUrl = r.audioUrl,
                pageUrl = lastParsedUrl,
                mediaType = r.mediaType,
                resolution = r.resolution,
                durationSec = r.durationSec,
                headers = HashMap(r.headers)
            )
            TaskManager.addTask(this, task, autoStart = true)
            Toast.makeText(this, "已加入下载队列: ${task.title}", Toast.LENGTH_SHORT).show()
            finish()
        }

        findViewById<Button>(R.id.btn_ser_all).setOnClickListener {
            val eps = currentResult?.series?.episodes ?: return@setOnClickListener
            eps.forEach { it.selected = true }
            rvSeries.adapter?.notifyDataSetChanged()
            updateSeriesBtnCount()
        }

        findViewById<Button>(R.id.btn_ser_none).setOnClickListener {
            val eps = currentResult?.series?.episodes ?: return@setOnClickListener
            eps.forEach { it.selected = !it.selected }
            rvSeries.adapter?.notifyDataSetChanged()
            updateSeriesBtnCount()
        }

        btnDownloadSeries.setOnClickListener {
            val s = currentResult?.series ?: return@setOnClickListener
            val chosen = s.episodes.filter { it.selected }
            if (chosen.isEmpty()) return@setOnClickListener
            VideoParser.submitSeriesDownloads(this, chosen, s.seriesTitle, true, true, currentResult?.headers ?: emptyMap()) { msg ->
                Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
            }
            finish()
        }

        val initialUrl = intent?.getStringExtra("initial_url") ?: ""
        if (initialUrl.isNotBlank()) {
            etInput.setText(initialUrl)
            startParse()
        }
    }

    override fun onDestroy() {
        destroySilentWebView()
        scope.cancel()
        super.onDestroy()
    }

    private fun destroySilentWebView() {
        silentWebView?.let { wv ->
            try {
                wv.stopLoading()
                wv.removeJavascriptInterface("StarStreamBridge")
                (wv.parent as? ViewGroup)?.removeView(wv)
                wv.destroy()
            } catch (_: Throwable) {}
        }
        silentWebView = null
    }

    private fun startParse() {
        val raw = etInput.text.toString().trim()
        if (raw.isEmpty()) {
            Toast.makeText(this, "请先粘贴分享链接或视频地址", Toast.LENGTH_SHORT).show()
            return
        }
        val mUrl = Regex("https?://[^\\s<>\"'\\]\\）】]+").find(raw)
        val extracted = mUrl?.value ?: raw
        lastParsedUrl = if (extracted.startsWith("http")) extracted else ""

        destroySilentWebView()
        tvStatus.visibility = View.VISIBLE
        tvStatus.text = "正在同步会话 Cookie 并深度解析网页、音视频双流与同系列选集..."
        btnBrowserFallback.visibility = View.GONE
        cardSingle.visibility = View.GONE
        cardSeries.visibility = View.GONE

        val extraHeaders = mutableMapOf<String, String>()
        if (lastParsedUrl.startsWith("http")) {
            try {
                val c = CookieManager.getInstance().getCookie(lastParsedUrl) ?: ""
                if (c.isNotBlank()) extraHeaders["Cookie"] = c
            } catch (_: Throwable) {}
            extraHeaders["User-Agent"] = AppConfig.getUserAgentString()
        }

        scope.launch {
            var res = withContext(Dispatchers.IO) { VideoParser.parseVideoUrl(raw, extraHeaders) }
            if (!res.success && lastParsedUrl.startsWith("http") &&
                (res.error.contains("NEED_WEBVIEW") || res.error.contains("JS") || lastParsedUrl.contains("douyin.com") || lastParsedUrl.contains("xiaohongshu.com"))
            ) {
                tvStatus.text = "检测到目标页启用了动态 JS 验证，正在后台调用内置浏览器内核自动执行提取..."
                val wvRes = extractViaSilentWebView(lastParsedUrl, res.title)
                if (wvRes != null && wvRes.success) {
                    res = wvRes.copy(series = wvRes.series ?: res.series)
                }
            }

            currentResult = res
            if (!res.success && res.series == null) {
                val cleanErr = res.error.removePrefix("NEED_WEBVIEW:")
                tvStatus.text = "解析提示: $cleanErr，可点击下方按钮在内置浏览器中打开并播放自动捕获。"
                if (lastParsedUrl.startsWith("http")) {
                    btnBrowserFallback.visibility = View.VISIBLE
                }
                return@launch
            }
            tvStatus.text = if (res.success) "解析成功" else "已识别合集列表（可配合内置浏览器嗅探）"
            if (!res.success && lastParsedUrl.startsWith("http")) {
                btnBrowserFallback.visibility = View.VISIBLE
            }
            val series = res.series
            if (series != null && series.episodes.size > 1) {
                cardSeries.visibility = View.VISIBLE
                tvSeriesTitle.text = "${series.seriesTitle} (共 ${series.total} 集)"
                rvSeries.adapter = SeriesAdapter(series.episodes) { updateSeriesBtnCount() }
                updateSeriesBtnCount()
            }
            if (res.url.isNotBlank()) {
                cardSingle.visibility = View.VISIBLE
                tvResTitle.text = res.title.ifBlank { "提取视频" }
                val audioTag = if (res.audioUrl.isNotBlank()) " · FFmpeg 音画双流混流" else ""
                tvResMeta.text = "${res.mediaType.uppercase()} · ${res.resolution.ifBlank { "高清" }}$audioTag"
            }
        }
    }

    /**
     * 后台静默调用真实 Chromium WebView 执行页面 JS（突破抖音/小红书等动态 JS 校验，无需手动跳转）
     */
    @SuppressLint("SetJavaScriptEnabled")
    private suspend fun extractViaSilentWebView(targetUrl: String, fallbackTitle: String): ParseResult? {
        val deferred = CompletableDeferred<ParseResult?>()
        var foundVideoUrl = ""
        var foundAudioUrl = ""
        var foundMediaType = "video"
        var foundTitle = fallbackTitle

        val ua = if (targetUrl.contains("douyin.com") || targetUrl.contains("iesdouyin.com")) {
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
        } else {
            AppConfig.getUserAgentString()
        }

        val wv = try {
            WebView(this).apply {
                visibility = View.INVISIBLE
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.mediaPlaybackRequiresUserGesture = false
                settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                settings.userAgentString = ua
            }
        } catch (_: Throwable) {
            return null
        }

        fun handleHit(url: String, hintType: String, pageTitle: String) {
            val clean = url.lowercase().substringBefore("#")
            val path = clean.substringBefore("?")
            if (Regex("\\.(jpg|jpeg|png|webp|avif|gif|svg|ico|css|js|json|woff2?|ttf|vtt|srt|ass)(\\?|#|$)").containsMatchIn(path)) return
            if (path.endsWith("init.mp4") || path.endsWith("init.m4s") || clean.contains("bvc_preview") || clean.contains("sprite")) return

            val isAud = hintType == "audio" || Regex("\\.(mp3|m4a|aac|flac|wav|ogg|opus)(\\?|#|$)|302\\d{2}\\.m4s|mime(?:_type)?=audio|/ies-music/|douyinstatic\\.com.*\\.(?:mp3|m4a)").containsMatchIn(clean)
            val isM3u8 = Regex("\\.(m3u8|mpd)(\\?|#|$)|/api/hls/").containsMatchIn(clean)
            val isVid = !isAud && (isM3u8 || Regex("\\.(mp4|m4s|flv|webm|mkv|mov)(\\?|#|$)|douyinvod\\.com|iesdouyin\\.com|bytevcloudvod\\.com|bilivideo\\.(com|cn)|hdslb\\.com|kwaicdn\\.com|xhscdn\\.com|googlevideo\\.com/videoplayback").containsMatchIn(clean))

            if (!isAud && !isVid) return
            if (pageTitle.isNotBlank() && foundTitle.isBlank()) foundTitle = pageTitle
            if (isAud) {
                if (foundAudioUrl.isBlank()) foundAudioUrl = url
            } else {
                if (foundVideoUrl.isBlank()) {
                    foundVideoUrl = url
                    foundMediaType = when {
                        isM3u8 -> "m3u8"
                        clean.contains("bilivideo") || clean.contains("hdslb.com") -> "bili_dash"
                        else -> "video"
                    }
                }
            }
            if (foundVideoUrl.isNotBlank() && !deferred.isCompleted) {
                val cookie = try { CookieManager.getInstance().getCookie(targetUrl) ?: "" } catch (_: Throwable) { "" }
                val hdrs = mutableMapOf("Referer" to targetUrl, "User-Agent" to ua)
                if (cookie.isNotBlank()) hdrs["Cookie"] = cookie
                if (foundAudioUrl.isNotBlank() && foundMediaType != "m3u8" && foundMediaType != "bili_dash") {
                    foundMediaType = "dual_dash"
                }
                deferred.complete(
                    ParseResult(
                        success = true,
                        title = foundTitle.ifBlank { "网页提取视频" },
                        url = foundVideoUrl,
                        audioUrl = foundAudioUrl,
                        mediaType = foundMediaType,
                        resolution = "高清",
                        headers = hdrs
                    )
                )
            }
        }

        wv.addJavascriptInterface(object {
            @JavascriptInterface
            fun onMediaFound(url: String, mediaType: String, title: String, pageUrl: String, durationSec: Int, resolution: String) {
                handleHit(url, mediaType, title)
            }
        }, "StarStreamBridge")

        wv.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                val t = view?.title?.trim() ?: ""
                if (t.isNotBlank()) foundTitle = t
                view?.evaluateJavascript(SnifferScripts.buildInjectSnifferJs(AppConfig.getSniffExtensions()), null)
            }

            override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
                val u = request?.url?.toString()
                if (!u.isNullOrBlank()) handleHit(u, "", foundTitle)
                return super.shouldInterceptRequest(view, request)
            }
        }

        silentWebView = wv
        rootContainer.addView(wv, ViewGroup.LayoutParams(1, 1))
        wv.loadUrl(targetUrl)

        val res = withTimeoutOrNull(7500L) { deferred.await() }
        // 若先抓到视频但音频晚 400ms 才到达，稍等片刻让音频也合入
        if (res != null && res.audioUrl.isBlank() && res.mediaType != "m3u8") {
            delay(500L)
            if (foundAudioUrl.isNotBlank()) {
                val updated = res.copy(
                    audioUrl = foundAudioUrl,
                    mediaType = if (res.mediaType == "bili_dash") "bili_dash" else "dual_dash"
                )
                destroySilentWebView()
                return updated
            }
        }
        destroySilentWebView()
        return res
    }

    private fun updateSeriesBtnCount() {
        val cnt = currentResult?.series?.episodes?.count { it.selected } ?: 0
        btnDownloadSeries.text = "一键爬取选中剧集 ($cnt 集)"
        btnDownloadSeries.isEnabled = cnt > 0
    }
}

package com.starstream.downloader.ui

import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.starstream.downloader.R
import com.starstream.downloader.core.*
import kotlinx.coroutines.*
import java.util.UUID

class ParserActivity : AppCompatActivity() {

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
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_parser)

        val root = findViewById<View>(R.id.root_parser_container)
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
        scope.cancel()
        super.onDestroy()
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
            val res = withContext(Dispatchers.IO) { VideoParser.parseVideoUrl(raw, extraHeaders) }
            currentResult = res
            if (!res.success && res.series == null) {
                tvStatus.text = "解析提示: ${res.error}"
                if (lastParsedUrl.startsWith("http")) {
                    btnBrowserFallback.visibility = View.VISIBLE
                }
                return@launch
            }
            tvStatus.text = if (res.success) "解析成功" else "已识别合集列表（可配合内置浏览器嗅探）"
            if (!res.success && lastParsedUrl.startsWith("http")) {
                btnBrowserFallback.visibility = View.VISIBLE
            }
            if (res.series != null && res.series.episodes.size > 1) {
                cardSeries.visibility = View.VISIBLE
                tvSeriesTitle.text = "${res.series.seriesTitle} (共 ${res.series.total} 集)"
                rvSeries.adapter = SeriesAdapter(res.series.episodes) { updateSeriesBtnCount() }
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

    private fun updateSeriesBtnCount() {
        val cnt = currentResult?.series?.episodes?.count { it.selected } ?: 0
        btnDownloadSeries.text = "一键爬取选中剧集 ($cnt 集)"
        btnDownloadSeries.isEnabled = cnt > 0
    }
}

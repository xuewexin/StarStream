package com.starstream.downloader.ui

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.webkit.*
import android.widget.*
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.GravityCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.drawerlayout.widget.DrawerLayout
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.starstream.downloader.R
import com.starstream.downloader.browser.SnifferScripts
import com.starstream.downloader.core.*
import kotlinx.coroutines.*
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.util.UUID
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.TimeUnit

class BrowserActivity : AppCompatActivity() {

    private data class BrowserTab(
        val id: String = UUID.randomUUID().toString().take(8),
        var webView: WebView? = null,
        @Volatile var currentUrl: String = "",
        @Volatile var currentTitle: String = "新标签页",
        var isStartPage: Boolean = true,
        val sniffedList: CopyOnWriteArrayList<SniffedMedia> = CopyOnWriteArrayList(),
        val seenKeys: MutableSet<String> = mutableSetOf()
    )

    private lateinit var drawerLayout: DrawerLayout
    private lateinit var swipeBrowser: SwipeRefreshLayout
    private lateinit var webViewContainer: FrameLayout
    private lateinit var etUrl: EditText
    private lateinit var progressBar: ProgressBar
    private lateinit var tvSniffedCount: TextView
    private lateinit var btnTabsDrawer: TextView
    private lateinit var btnBookmark: ImageButton
    private lateinit var startPageContainer: View
    private lateinit var tvEngineHint: TextView
    private lateinit var uaChipsRow: LinearLayout
    private lateinit var engineChipsRow: LinearLayout
    private lateinit var bookmarkFoldersRow: LinearLayout
    private lateinit var bookmarksBody: View
    private lateinit var ivBookmarksChevron: ImageView
    private lateinit var bookmarksContainer: LinearLayout
    private lateinit var tvBookmarksEmpty: TextView
    private lateinit var historyBody: View
    private lateinit var ivHistoryChevron: ImageView
    private lateinit var historyPreviewContainer: LinearLayout
    private lateinit var tvHistoryEmpty: TextView
    private lateinit var etHomeSearch: EditText
    private lateinit var drawerTabsList: LinearLayout
    private lateinit var drawerBookmarksList: LinearLayout

    private var selectedBookmarkFolder: String = "全部"

    private val tabs = mutableListOf<BrowserTab>()
    private var activeTabIndex = 0
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    @Volatile private var cachedUserAgent: String = ""
    @Volatile private var cachedAdBlock: Boolean = true
    @Volatile private var cachedSniffExts: Set<String> = emptySet()

    private val probeClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(6, TimeUnit.SECONDS)
            .readTimeout(8, TimeUnit.SECONDS)
            .followRedirects(true)
            .build()
    }

    private val uaProfiles = listOf(
        "chrome_pc" to "Chrome 桌面",
        "chrome_mobile" to "Chrome 手机",
        "edge_pc" to "Edge 桌面",
        "safari_ios" to "Safari iOS",
        "firefox_pc" to "Firefox 桌面"
    )

    private val engines = listOf(
        "baidu" to "百度",
        "google" to "Google",
        "bing" to "Bing",
        "duckduckgo" to "DuckDuckGo",
        "yandex" to "Yandex"
    )

    private val adTrackerHosts = setOf(
        "doubleclick.net", "googlesyndication.com", "google-analytics.com",
        "googletagmanager.com", "cnzz.com", "umeng.com", "hm.baidu.com",
        "pos.baidu.com", "cpro.baidu.com", "adservice.google.com"
    )

    private fun syncConfigFlags() {
        cachedUserAgent = AppConfig.getUserAgentString()
        cachedAdBlock = AppConfig.adBlockEnabled
        cachedSniffExts = AppConfig.getSniffExtensions().map { it.lowercase() }.toSet()
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AppConfig.init(this)
        setContentView(R.layout.activity_browser)
        syncConfigFlags()

        drawerLayout = findViewById(R.id.browser_drawer_layout)
        val mainRoot = findViewById<View>(R.id.browser_main_root)
        val leftDrawer = findViewById<View>(R.id.drawer_tabs_panel)
        val rightDrawer = findViewById<View>(R.id.drawer_bookmarks_panel)

        ViewCompat.setOnApplyWindowInsetsListener(mainRoot) { v, wi ->
            val insets = wi.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(insets.left, insets.top, insets.right, insets.bottom)
            wi
        }
        ViewCompat.setOnApplyWindowInsetsListener(leftDrawer) { v, wi ->
            val insets = wi.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(36, insets.top + 28, 36, insets.bottom + 28)
            wi
        }
        ViewCompat.setOnApplyWindowInsetsListener(rightDrawer) { v, wi ->
            val insets = wi.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(36, insets.top + 28, 36, insets.bottom + 28)
            wi
        }

        swipeBrowser = findViewById(R.id.swipe_browser)
        webViewContainer = findViewById(R.id.webview_container)
        etUrl = findViewById(R.id.et_url)
        progressBar = findViewById(R.id.web_progress)
        tvSniffedCount = findViewById(R.id.tv_sniffed_count)
        btnTabsDrawer = findViewById(R.id.btn_tabs_drawer)
        btnBookmark = findViewById(R.id.btn_bookmark)
        startPageContainer = findViewById(R.id.start_page_container)
        tvEngineHint = findViewById(R.id.tv_engine_hint)
        uaChipsRow = findViewById(R.id.ua_chips_row)
        engineChipsRow = findViewById(R.id.engine_chips_row)
        bookmarkFoldersRow = findViewById(R.id.bookmark_folders_row)
        bookmarksBody = findViewById(R.id.bookmarks_body)
        ivBookmarksChevron = findViewById(R.id.iv_bookmarks_chevron)
        bookmarksContainer = findViewById(R.id.bookmarks_container)
        tvBookmarksEmpty = findViewById(R.id.tv_bookmarks_empty)
        historyBody = findViewById(R.id.history_body)
        ivHistoryChevron = findViewById(R.id.iv_history_chevron)
        historyPreviewContainer = findViewById(R.id.history_preview_container)
        tvHistoryEmpty = findViewById(R.id.tv_history_empty)
        findViewById<View>(R.id.btn_all_history).setOnClickListener { showHistoryDialog() }
        findViewById<View>(R.id.btn_refresh_identity).setOnClickListener { refreshIdentity() }
        findViewById<View>(R.id.btn_new_bookmark_folder).setOnClickListener { promptCreateBookmarkFolder() }
        findViewById<View>(R.id.header_bookmarks_toggle).setOnClickListener {
            AppConfig.bookmarksExpanded = !AppConfig.bookmarksExpanded
            applyExpandStates()
        }
        findViewById<View>(R.id.header_history_toggle).setOnClickListener {
            AppConfig.historyExpanded = !AppConfig.historyExpanded
            applyExpandStates()
        }
        applyExpandStates()
        etHomeSearch = findViewById(R.id.et_home_search)
        drawerTabsList = findViewById(R.id.drawer_tabs_list)
        drawerBookmarksList = findViewById(R.id.drawer_bookmarks_list)

        swipeBrowser.setColorSchemeResources(R.color.accent_cyan, R.color.accent_blue)
        swipeBrowser.setProgressBackgroundColorSchemeResource(R.color.bg_card)
        swipeBrowser.setOnChildScrollUpCallback { _, _ ->
            val tab = currentTab()
            tab.isStartPage || (tab.webView?.scrollY ?: 0) > 0
        }
        swipeBrowser.setOnRefreshListener {
            val tab = currentTab()
            if (!tab.isStartPage && tab.webView != null) {
                tab.webView?.reload()
            } else {
                swipeBrowser.isRefreshing = false
            }
        }

        if (tabs.isEmpty()) {
            val saved = AppConfig.getSavedTabs()
            if (saved.isNotEmpty()) {
                saved.forEach { st ->
                    tabs.add(
                        BrowserTab(
                            id = st.id,
                            currentUrl = st.currentUrl,
                            currentTitle = st.currentTitle,
                            isStartPage = st.isStartPage || !st.currentUrl.startsWith("http")
                        )
                    )
                }
                activeTabIndex = AppConfig.savedActiveTabIndex.coerceIn(0, tabs.lastIndex)
            } else {
                tabs.add(BrowserTab())
                activeTabIndex = 0
            }
        }

        findViewById<View>(R.id.btn_exit_browser).setOnClickListener { finish() }
        btnTabsDrawer.setOnClickListener {
            renderTabsDrawer()
            drawerLayout.openDrawer(GravityCompat.START)
        }
        findViewById<View>(R.id.btn_new_tab).setOnClickListener {
            tabs.add(BrowserTab())
            switchToTab(tabs.lastIndex)
            drawerLayout.closeDrawer(GravityCompat.START)
        }

        findViewById<View>(R.id.btn_home).setOnClickListener { showStartPageForActiveTab() }
        findViewById<View>(R.id.btn_back).setOnClickListener {
            val tab = currentTab()
            val wv = tab.webView
            if (!tab.isStartPage && wv != null && wv.canGoBack()) wv.goBack() else showStartPageForActiveTab()
        }
        findViewById<View>(R.id.btn_forward).setOnClickListener {
            val tab = currentTab()
            if (!tab.isStartPage) tab.webView?.takeIf { it.canGoForward() }?.goForward()
        }
        findViewById<View>(R.id.btn_refresh).setOnClickListener {
            val tab = currentTab()
            if (tab.isStartPage) {
                renderStartPageHeaders()
                renderBookmarks()
            } else {
                tab.webView?.reload()
            }
        }

        btnBookmark.setOnClickListener {
            val tab = currentTab()
            val u = tab.currentUrl.ifBlank { etUrl.text.toString().trim() }
            if (tab.isStartPage || !u.startsWith("http")) {
                Toast.makeText(this, "请先打开一个网页再收藏", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            if (AppConfig.isBookmarked(u)) {
                ThemeManager.dialogBuilder(this)
                    .setTitle("管理当前网页收藏")
                    .setItems(arrayOf("更换所在文件夹", "取消收藏该网页")) { _, w ->
                        if (w == 0) {
                            promptBookmarkIntoFolder(tab.currentTitle, u)
                        } else {
                            AppConfig.removeBookmark(u)
                            updateBookmarkIcon(u)
                            renderBookmarks()
                            Toast.makeText(this, "已取消收藏", Toast.LENGTH_SHORT).show()
                        }
                    }
                    .show()
            } else {
                promptBookmarkIntoFolder(tab.currentTitle, u)
            }
        }

        etUrl.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_GO) {
                navigateTo(etUrl.text.toString())
                true
            } else false
        }
        findViewById<Button>(R.id.btn_home_search).setOnClickListener { navigateTo(etHomeSearch.text.toString()) }
        etHomeSearch.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEARCH || actionId == EditorInfo.IME_ACTION_GO) {
                navigateTo(etHomeSearch.text.toString())
                true
            } else false
        }

        findViewById<View>(R.id.btn_sniffed_sheet).setOnClickListener { showSniffedBottomSheet() }
        findViewById<View>(R.id.btn_series_crawl).setOnClickListener { openSeriesPicker() }
        findViewById<View>(R.id.btn_deep_parse).setOnClickListener {
            val tab = currentTab()
            val u = tab.currentUrl.ifBlank { etUrl.text.toString().trim() }
            if (u.startsWith("http")) {
                startActivity(Intent(this, ParserActivity::class.java).putExtra("initial_url", u))
            } else {
                Toast.makeText(this, "请先打开网页或输入链接", Toast.LENGTH_SHORT).show()
            }
        }
        findViewById<View>(R.id.btn_browser_menu).setOnClickListener { showBrowserMenu() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (drawerLayout.isDrawerOpen(GravityCompat.START)) {
                    drawerLayout.closeDrawer(GravityCompat.START)
                } else if (drawerLayout.isDrawerOpen(GravityCompat.END)) {
                    drawerLayout.closeDrawer(GravityCompat.END)
                } else if (!currentTab().isStartPage) {
                    val wv = currentTab().webView
                    if (wv != null && wv.canGoBack()) {
                        wv.goBack()
                    } else {
                        // 仅剩单个网页时，左滑返回先回到浏览器主页
                        showStartPageForActiveTab()
                    }
                } else {
                    persistTabsState()
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        switchToTab(activeTabIndex)
        val openUrlExtra = intent?.getStringExtra("open_url") ?: ""
        if (openUrlExtra.startsWith("http")) {
            navigateTo(openUrlExtra)
        }
    }

    override fun onResume() {
        super.onResume()
        syncConfigFlags()
        ThemeManager.applyTheme(this, findViewById(R.id.browser_main_root))
        tabs.forEach { it.webView?.settings?.userAgentString = cachedUserAgent }
        if (currentTab().isStartPage) {
            renderStartPageHeaders()
            renderHistoryPreview()
        }
    }

    override fun onPause() {
        super.onPause()
        persistTabsState()
    }

    override fun onStop() {
        super.onStop()
        persistTabsState()
    }

    override fun onDestroy() {
        persistTabsState()
        scope.cancel()
        tabs.forEach { tab ->
            tab.webView?.let { wv ->
                wv.stopLoading()
                wv.removeJavascriptInterface("StarStreamBridge")
                wv.destroy()
            }
            tab.webView = null
        }
        super.onDestroy()
    }

    private fun currentTab(): BrowserTab {
        if (tabs.isEmpty()) tabs.add(BrowserTab())
        activeTabIndex = activeTabIndex.coerceIn(0, tabs.lastIndex)
        return tabs[activeTabIndex]
    }

    private fun persistTabsState() {
        val stateList = tabs.map {
            AppConfig.SavedTabState(
                id = it.id,
                currentUrl = it.currentUrl,
                currentTitle = it.currentTitle,
                isStartPage = it.isStartPage
            )
        }
        AppConfig.saveTabsState(stateList, activeTabIndex)
    }

    private fun switchToTab(index: Int) {
        if (tabs.isEmpty()) tabs.add(BrowserTab())
        activeTabIndex = index.coerceIn(0, tabs.lastIndex)
        val tab = currentTab()
        btnTabsDrawer.text = tabs.size.toString()

        webViewContainer.removeAllViews()
        swipeBrowser.isRefreshing = false
        if (tab.isStartPage || !tab.currentUrl.startsWith("http")) {
            tab.isStartPage = true
            swipeBrowser.visibility = View.GONE
            startPageContainer.visibility = View.VISIBLE
            progressBar.visibility = View.GONE
            etUrl.setText("")
            updateBookmarkIcon("")
            renderStartPageHeaders()
            renderBookmarks()
            renderHistoryPreview()
        } else {
            val needInitialLoad = tab.webView == null
            val wv = ensureWebViewForTab(tab)
            if (wv == null) {
                tab.isStartPage = true
                switchToTab(activeTabIndex)
                return
            }
            startPageContainer.visibility = View.GONE
            swipeBrowser.visibility = View.VISIBLE
            webViewContainer.addView(
                wv,
                FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            )
            etUrl.setText(tab.currentUrl)
            updateBookmarkIcon(tab.currentUrl)
            if (needInitialLoad) {
                wv.loadUrl(tab.currentUrl)
            }
        }
        updateSniffBadge()
        persistTabsState()
    }

    private fun showStartPageForActiveTab() {
        val tab = currentTab()
        tab.isStartPage = true
        tab.currentUrl = ""
        tab.currentTitle = "新标签页"
        switchToTab(activeTabIndex)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun ensureWebViewForTab(tab: BrowserTab): WebView? {
        tab.webView?.let { return it }
        val wv = try {
            WebView(this)
        } catch (e: Throwable) {
            Toast.makeText(this, "WebView 初始化失败: ${e.message}", Toast.LENGTH_LONG).show()
            return null
        }
        try {
            CookieManager.getInstance().setAcceptCookie(true)
            CookieManager.getInstance().setAcceptThirdPartyCookies(wv, true)
        } catch (_: Throwable) {}

        wv.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            useWideViewPort = true
            loadWithOverviewMode = true
            builtInZoomControls = true
            displayZoomControls = false
            userAgentString = cachedUserAgent
        }

        wv.addJavascriptInterface(object {
            @JavascriptInterface
            fun onMediaFound(
                url: String,
                mediaType: String,
                title: String,
                pageUrl: String,
                durationSec: Int,
                resolution: String
            ) {
                recordCandidate(tab, url, mediaType, title, pageUrl, durationSec, resolution, 0L)
            }
        }, "StarStreamBridge")

        wv.setDownloadListener { url, _, contentDisposition, mimetype, contentLength ->
            if (!url.startsWith("http")) return@setDownloadListener
            val guessedTitle = URLUtil.guessFileName(url, contentDisposition, mimetype)
            recordCandidate(tab, url, "", guessedTitle, tab.currentUrl, 0, "", contentLength.coerceAtLeast(0L))
            runOnUiThread {
                if (!isFinishing) {
                    Toast.makeText(this, "已捕获可下载文件: $guessedTitle", Toast.LENGTH_SHORT).show()
                    showSniffedBottomSheet()
                }
            }
        }

        wv.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (isFinishing || currentTab() !== tab || tab.isStartPage) return
                progressBar.visibility = if (newProgress < 100) View.VISIBLE else View.GONE
                progressBar.progress = newProgress
                if (newProgress >= 100) {
                    swipeBrowser.isRefreshing = false
                }
            }

            override fun onReceivedTitle(view: WebView?, title: String?) {
                if (!title.isNullOrBlank()) {
                    tab.currentTitle = title
                    if (tab.currentUrl.startsWith("http")) {
                        AppConfig.recordHistory(title, tab.currentUrl)
                        persistTabsState()
                    }
                }
            }
        }

        wv.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                val safeUrl = url ?: ""
                tab.currentUrl = safeUrl
                if (safeUrl.startsWith("http")) {
                    tab.isStartPage = false
                    persistTabsState()
                }
                if (!isFinishing && currentTab() === tab && safeUrl.isNotEmpty()) {
                    etUrl.setText(safeUrl)
                    updateBookmarkIcon(safeUrl)
                }
                tab.sniffedList.clear()
                synchronized(tab.seenKeys) { tab.seenKeys.clear() }
                if (currentTab() === tab) updateSniffBadge()
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                val safeUrl = url ?: ""
                tab.currentUrl = safeUrl
                if (!isFinishing) {
                    swipeBrowser.isRefreshing = false
                    if (currentTab() === tab && safeUrl.isNotEmpty()) {
                        etUrl.setText(safeUrl)
                        updateBookmarkIcon(safeUrl)
                    }
                    view?.title?.takeIf { it.isNotBlank() }?.let { tab.currentTitle = it }
                    if (safeUrl.startsWith("http")) {
                        AppConfig.recordHistory(tab.currentTitle, safeUrl)
                        persistTabsState()
                    }
                    view?.evaluateJavascript(SnifferScripts.buildInjectSnifferJs(AppConfig.getSniffExtensions()), null)
                }
            }

            override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
                val uri = request?.url ?: return null
                val host = uri.host?.lowercase() ?: ""
                if (cachedAdBlock && adTrackerHosts.any { host == it || host.endsWith(".$it") }) {
                    return WebResourceResponse("text/plain", "utf-8", ByteArrayInputStream(ByteArray(0)))
                }
                val u = uri.toString()
                if (isMediaCandidate(u)) {
                    recordCandidate(tab, u, "", tab.currentTitle, tab.currentUrl, 0, "", 0L)
                }
                return super.shouldInterceptRequest(view, request)
            }
        }

        tab.webView = wv
        return wv
    }

    private fun navigateTo(raw: String) {
        var u = raw.trim()
        if (u.isEmpty()) return
        if (!u.startsWith("http://") && !u.startsWith("https://")) {
            u = if (u.contains(".") && !u.contains(" ")) "https://$u"
            else AppConfig.buildSearchUrl(u)
        }
        val tab = currentTab()
        val wv = ensureWebViewForTab(tab) ?: return
        tab.isStartPage = false
        tab.currentUrl = u
        switchToTab(activeTabIndex)
        wv.loadUrl(u)
    }

    private fun renderStartPageHeaders() {
        tvEngineHint.text = "${AppConfig.getUaLabel()} · ${AppConfig.getSearchEngineLabel()} · 下拉网页即可刷新"

        uaChipsRow.removeAllViews()
        val curUa = AppConfig.uaProfile
        uaProfiles.forEach { (id, name) ->
            val selected = id == curUa
            val tv = TextView(this).apply {
                text = name
                textSize = 11.5f
                setPadding(24, 10, 24, 10)
                setTextColor(getColor(if (selected) R.color.accent_blue else R.color.text_secondary))
                setBackgroundResource(if (selected) R.drawable.bg_card else R.drawable.bg_input)
                layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                    marginEnd = 14
                }
                setOnClickListener {
                    AppConfig.uaProfile = id
                    cachedUserAgent = AppConfig.getUserAgentString()
                    tabs.forEach { it.webView?.settings?.userAgentString = cachedUserAgent }
                    renderStartPageHeaders()
                }
            }
            uaChipsRow.addView(tv)
        }

        engineChipsRow.removeAllViews()
        val curEngine = AppConfig.searchEngine
        engines.forEach { (id, name) ->
            val selected = id == curEngine
            val tv = TextView(this).apply {
                text = name
                textSize = 11.5f
                setPadding(24, 10, 24, 10)
                setTextColor(getColor(if (selected) R.color.accent_cyan else R.color.text_secondary))
                setBackgroundResource(if (selected) R.drawable.bg_card else R.drawable.bg_input)
                layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                    marginEnd = 14
                }
                setOnClickListener {
                    AppConfig.searchEngine = id
                    renderStartPageHeaders()
                }
            }
            engineChipsRow.addView(tv)
        }
    }

    private fun applyExpandStates() {
        val bExp = AppConfig.bookmarksExpanded
        bookmarksBody.visibility = if (bExp) View.VISIBLE else View.GONE
        ivBookmarksChevron.setImageResource(if (bExp) R.drawable.ic_expand_less else R.drawable.ic_expand_more)

        val hExp = AppConfig.historyExpanded
        historyBody.visibility = if (hExp) View.VISIBLE else View.GONE
        ivHistoryChevron.setImageResource(if (hExp) R.drawable.ic_expand_less else R.drawable.ic_expand_more)
    }

    private fun refreshIdentity() {
        cachedUserAgent = AppConfig.rotateIdentity()
        try {
            CookieManager.getInstance().removeSessionCookies(null)
            CookieManager.getInstance().flush()
        } catch (_: Throwable) {}
        tabs.forEach { tab ->
            tab.webView?.settings?.userAgentString = cachedUserAgent
            tab.webView?.clearCache(false)
        }
        val tab = currentTab()
        if (tab.isStartPage) {
            renderStartPageHeaders()
        } else {
            tab.webView?.reload()
        }
        Toast.makeText(this, "已刷新浏览器身份指纹并重置会话 (${AppConfig.getUaLabel()})", Toast.LENGTH_SHORT).show()
    }

    private fun promptCreateBookmarkFolder(onCreated: ((String) -> Unit)? = null) {
        val input = EditText(this).apply {
            hint = "输入文件夹名称 (如: 影视 / 学习 / 工具)"
            setPadding(40, 30, 40, 30)
        }
        ThemeManager.dialogBuilder(this)
            .setTitle("新建收藏文件夹")
            .setView(input)
            .setPositiveButton("创建") { _, _ ->
                val name = input.text.toString().trim()
                if (name.isEmpty()) {
                    Toast.makeText(this, "文件夹名不能为空", Toast.LENGTH_SHORT).show()
                } else {
                    AppConfig.createBookmarkFolder(name)
                    selectedBookmarkFolder = name
                    renderBookmarks()
                    Toast.makeText(this, "已创建文件夹：$name", Toast.LENGTH_SHORT).show()
                    onCreated?.invoke(name)
                }
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun promptBookmarkIntoFolder(title: String, url: String) {
        val folders = AppConfig.getBookmarkFolders()
        val options = (folders + "+ 新建文件夹...").toTypedArray()
        ThemeManager.dialogBuilder(this)
            .setTitle("选择保存到的收藏文件夹")
            .setItems(options) { _, which ->
                if (which == folders.size) {
                    promptCreateBookmarkFolder { newName ->
                        AppConfig.addBookmarkToFolder(title, url, newName)
                        updateBookmarkIcon(url)
                        renderBookmarks()
                        Toast.makeText(this, "已收藏到「$newName」", Toast.LENGTH_SHORT).show()
                    }
                } else {
                    val chosen = folders[which]
                    AppConfig.addBookmarkToFolder(title, url, chosen)
                    updateBookmarkIcon(url)
                    renderBookmarks()
                    Toast.makeText(this, "已收藏到「$chosen」", Toast.LENGTH_SHORT).show()
                }
            }
            .show()
    }

    private fun renderBookmarks() {
        val folders = listOf("全部") + AppConfig.getBookmarkFolders()
        if (selectedBookmarkFolder !in folders) selectedBookmarkFolder = "全部"

        bookmarkFoldersRow.removeAllViews()
        folders.forEach { folderName ->
            val selected = folderName == selectedBookmarkFolder
            val chip = TextView(this).apply {
                text = folderName
                textSize = 11.5f
                setPadding(24, 10, 24, 10)
                setTextColor(getColor(if (selected) R.color.accent_amber else R.color.text_secondary))
                setBackgroundResource(if (selected) R.drawable.bg_card else R.drawable.bg_input)
                layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                    marginEnd = 12
                }
                setOnClickListener {
                    selectedBookmarkFolder = folderName
                    renderBookmarks()
                }
                setOnLongClickListener {
                    if (folderName != "全部" && folderName != "默认收藏") {
                        ThemeManager.dialogBuilder(this@BrowserActivity)
                            .setTitle("删除收藏文件夹")
                            .setMessage("确定删除「$folderName」吗？其中的书签会自动移回「默认收藏」。")
                            .setPositiveButton("删除") { _, _ ->
                                AppConfig.deleteBookmarkFolder(folderName)
                                selectedBookmarkFolder = "默认收藏"
                                renderBookmarks()
                            }
                            .setNegativeButton("取消", null)
                            .show()
                    }
                    true
                }
            }
            bookmarkFoldersRow.addView(chip)
        }

        val all = AppConfig.getBookmarks()
        val shown = if (selectedBookmarkFolder == "全部") all else all.filter { it.folder == selectedBookmarkFolder }
        renderBookmarkRowsInto(bookmarksContainer, shown) { }
        tvBookmarksEmpty.visibility = if (shown.isEmpty()) View.VISIBLE else View.GONE
        renderBookmarkRowsInto(drawerBookmarksList, all) { drawerLayout.closeDrawer(GravityCompat.END) }
    }

    private fun renderBookmarkRowsInto(container: LinearLayout, list: List<AppConfig.BookmarkEntry>, onOpen: () -> Unit) {
        container.removeAllViews()
        list.forEach { bm ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setBackgroundResource(R.drawable.bg_input)
                setPadding(24, 18, 14, 18)
                layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                    bottomMargin = 12
                }
                setOnClickListener {
                    onOpen()
                    navigateTo(bm.url)
                }
            }
            val textCol = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            }
            textCol.addView(TextView(this).apply {
                text = "[${bm.folder}] ${bm.title}"
                setTextColor(getColor(R.color.text_primary))
                textSize = 13f
                maxLines = 1
                ellipsize = android.text.TextUtils.TruncateAt.END
            })
            textCol.addView(TextView(this).apply {
                text = bm.url
                setTextColor(getColor(R.color.text_muted))
                textSize = 10.5f
                maxLines = 1
                ellipsize = android.text.TextUtils.TruncateAt.END
            })
            row.addView(textCol)
            row.addView(ImageButton(this).apply {
                setImageResource(R.drawable.ic_close)
                setColorFilter(getColor(R.color.accent_red))
                background = null
                setPadding(16, 10, 12, 10)
                setOnClickListener {
                    AppConfig.removeBookmark(bm.url)
                    renderBookmarks()
                }
            })
            container.addView(row)
        }
    }

    private fun renderTabsDrawer() {
        drawerTabsList.removeAllViews()
        tabs.forEachIndexed { idx, tab ->
            val isActive = idx == activeTabIndex
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setBackgroundResource(if (isActive) R.drawable.bg_card else R.drawable.bg_input)
                setPadding(20, 18, 14, 18)
                layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                    bottomMargin = 12
                }
                setOnClickListener {
                    switchToTab(idx)
                    drawerLayout.closeDrawer(GravityCompat.START)
                }
            }
            row.addView(ImageView(this).apply {
                setImageResource(if (tab.isStartPage) R.drawable.ic_home else R.drawable.ic_browser)
                setColorFilter(getColor(if (isActive) R.color.accent_cyan else R.color.text_muted))
                layoutParams = LinearLayout.LayoutParams(36, 36).apply { marginEnd = 16 }
            })
            row.addView(TextView(this).apply {
                text = if (tab.isStartPage) "极简起始页" else "${tab.currentTitle} (${tab.sniffedList.size})"
                setTextColor(getColor(if (isActive) R.color.accent_cyan else R.color.text_primary))
                textSize = 13f
                maxLines = 1
                ellipsize = android.text.TextUtils.TruncateAt.END
                layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            })
            if (tabs.size > 1) {
                row.addView(ImageButton(this).apply {
                    setImageResource(R.drawable.ic_close)
                    setColorFilter(getColor(R.color.accent_red))
                    background = null
                    setPadding(16, 10, 12, 10)
                    setOnClickListener {
                        tab.webView?.let { wv ->
                            wv.stopLoading()
                            wv.removeJavascriptInterface("StarStreamBridge")
                            wv.destroy()
                        }
                        tabs.removeAt(idx)
                        if (activeTabIndex >= tabs.size) activeTabIndex = tabs.lastIndex
                        switchToTab(activeTabIndex)
                        renderTabsDrawer()
                    }
                })
            }
            drawerTabsList.addView(row)
        }
    }

    private fun updateBookmarkIcon(url: String) {
        if (!::btnBookmark.isInitialized) return
        val saved = url.startsWith("http") && AppConfig.isBookmarked(url)
        btnBookmark.setImageResource(if (saved) R.drawable.ic_star_filled else R.drawable.ic_star_outline)
    }

    private fun showBrowserMenu() {
        val items = listOf(
            IconMenuItem(R.drawable.ic_history, "浏览历史记录", "查看或重新打开访问过的网页"),
            IconMenuItem(R.drawable.ic_fingerprint, "身份刷新 (重置指纹与缓存)", "轮换内核版本号并清理当前会话 Cookie"),
            IconMenuItem(R.drawable.ic_browser, "切换内置浏览器内核", "当前: ${AppConfig.getUaLabel()}"),
            IconMenuItem(R.drawable.ic_search, "切换默认搜索引擎", "当前: ${AppConfig.getSearchEngineLabel()}"),
            IconMenuItem(
                R.drawable.ic_shield,
                if (cachedAdBlock) "广告追踪拦截：已开启" else "广告追踪拦截：已关闭",
                "点击立即切换过滤状态"
            ),
            IconMenuItem(R.drawable.ic_star_filled, "打开收藏夹抽屉", "快速访问或管理收藏网页"),
            IconMenuItem(R.drawable.ic_add, "新建浏览器标签页", "隔离浏览会话与媒体嗅探列表"),
            IconMenuItem(R.drawable.ic_settings, "自定义嗅探类型 / 下载存储设置", "增删爬取文件扩展名、并发数、线程数、路径")
        )
        showIconMenuDialog(this, "星流浏览器菜单", items) { which ->
            when (which) {
                0 -> showHistoryDialog()
                1 -> refreshIdentity()
                2 -> showUaPickerDialog()
                3 -> showEnginePickerDialog()
                4 -> {
                    AppConfig.adBlockEnabled = !cachedAdBlock
                    cachedAdBlock = AppConfig.adBlockEnabled
                    Toast.makeText(this, if (cachedAdBlock) "已开启广告拦截" else "已关闭广告拦截", Toast.LENGTH_SHORT).show()
                }
                5 -> {
                    renderBookmarks()
                    drawerLayout.openDrawer(GravityCompat.END)
                }
                6 -> {
                    tabs.add(BrowserTab())
                    switchToTab(tabs.lastIndex)
                }
                7 -> startActivity(Intent(this, SettingsActivity::class.java))
            }
        }
    }

    private fun renderHistoryPreview() {
        if (!::historyPreviewContainer.isInitialized) return
        val list = AppConfig.getHistory().take(5)
        historyPreviewContainer.removeAllViews()
        tvHistoryEmpty.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
        val fmt = java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault())
        list.forEach { entry ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setBackgroundResource(R.drawable.bg_input)
                setPadding(24, 16, 14, 16)
                layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                    bottomMargin = 10
                }
                setOnClickListener { navigateTo(entry.url) }
            }
            val col = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            }
            col.addView(TextView(this).apply {
                text = entry.title
                setTextColor(getColor(R.color.text_primary))
                textSize = 13f
                maxLines = 1
                ellipsize = android.text.TextUtils.TruncateAt.END
            })
            col.addView(TextView(this).apply {
                text = "${fmt.format(java.util.Date(entry.timestamp))} · ${entry.url}"
                setTextColor(getColor(R.color.text_muted))
                textSize = 10.5f
                maxLines = 1
                ellipsize = android.text.TextUtils.TruncateAt.END
            })
            row.addView(col)
            row.addView(ImageButton(this).apply {
                setImageResource(R.drawable.ic_close)
                setColorFilter(getColor(R.color.accent_red))
                background = null
                setPadding(16, 8, 10, 8)
                setOnClickListener {
                    AppConfig.deleteHistoryItem(entry.url)
                    renderHistoryPreview()
                }
            })
            historyPreviewContainer.addView(row)
        }
    }

    private fun showHistoryDialog() {
        val dlg = BottomSheetDialog(this)
        ThemeManager.styleBottomSheet(dlg, this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(ThemeManager.current().bgPanel)
            setPadding(36, 32, 36, 32)
        }
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, 0, 0, 18)
        }
        header.addView(ImageView(this).apply {
            setImageResource(R.drawable.ic_history)
            setColorFilter(getColor(R.color.accent_cyan))
            layoutParams = LinearLayout.LayoutParams(48, 48).apply { marginEnd = 14 }
        })
        val tvTitle = TextView(this).apply {
            setTextColor(getColor(R.color.text_primary))
            textSize = 15.5f
            setTypeface(null, android.graphics.Typeface.BOLD)
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }
        header.addView(tvTitle)
        val btnClear = TextView(this).apply {
            text = "清空全部"
            setTextColor(getColor(R.color.accent_red))
            textSize = 12.5f
            setBackgroundResource(R.drawable.bg_input)
            setPadding(24, 12, 24, 12)
        }
        header.addView(btnClear)
        root.addView(header)

        val scroll = ScrollView(this)
        val listBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        scroll.addView(listBox)
        root.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 820))

        val fmt = java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault())
        fun rebuild() {
            val list = AppConfig.getHistory()
            tvTitle.text = "浏览器访问历史 (${list.size})"
            listBox.removeAllViews()
            if (list.isEmpty()) {
                listBox.addView(TextView(this).apply {
                    text = "暂无访问记录"
                    setTextColor(getColor(R.color.text_muted))
                    textSize = 13f
                    gravity = Gravity.CENTER
                    setPadding(0, 80, 0, 80)
                })
                return
            }
            list.forEach { entry ->
                val row = LinearLayout(this).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = Gravity.CENTER_VERTICAL
                    setBackgroundResource(R.drawable.bg_card)
                    setPadding(24, 18, 12, 18)
                    layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                        bottomMargin = 12
                    }
                    setOnClickListener {
                        dlg.dismiss()
                        navigateTo(entry.url)
                    }
                }
                val col = LinearLayout(this).apply {
                    orientation = LinearLayout.VERTICAL
                    layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
                }
                col.addView(TextView(this).apply {
                    text = entry.title
                    setTextColor(getColor(R.color.text_primary))
                    textSize = 13.5f
                    maxLines = 1
                    ellipsize = android.text.TextUtils.TruncateAt.END
                })
                col.addView(TextView(this).apply {
                    text = "${fmt.format(java.util.Date(entry.timestamp))} · ${entry.url}"
                    setTextColor(getColor(R.color.text_muted))
                    textSize = 10.5f
                    maxLines = 1
                    ellipsize = android.text.TextUtils.TruncateAt.END
                })
                row.addView(col)
                row.addView(ImageButton(this).apply {
                    setImageResource(R.drawable.ic_close)
                    setColorFilter(getColor(R.color.accent_red))
                    background = null
                    setPadding(16, 10, 12, 10)
                    setOnClickListener {
                        AppConfig.deleteHistoryItem(entry.url)
                        rebuild()
                        renderHistoryPreview()
                    }
                })
                listBox.addView(row)
            }
        }

        btnClear.setOnClickListener {
            AppConfig.clearHistory()
            rebuild()
            renderHistoryPreview()
            Toast.makeText(this, "已清空访问历史", Toast.LENGTH_SHORT).show()
        }

        rebuild()
        dlg.setContentView(root)
        dlg.show()
    }

    private fun showUaPickerDialog() {
        val names = uaProfiles.map { it.second }.toTypedArray()
        val curIdx = uaProfiles.indexOfFirst { it.first == AppConfig.uaProfile }.coerceAtLeast(0)
        ThemeManager.dialogBuilder(this)
            .setTitle("选择内置浏览器内核 (UA)")
            .setSingleChoiceItems(names, curIdx) { dlg, which ->
                AppConfig.uaProfile = uaProfiles[which].first
                cachedUserAgent = AppConfig.getUserAgentString()
                tabs.forEach { it.webView?.settings?.userAgentString = cachedUserAgent }
                if (currentTab().isStartPage) renderStartPageHeaders() else currentTab().webView?.reload()
                Toast.makeText(this, "已切换为 ${uaProfiles[which].second}", Toast.LENGTH_SHORT).show()
                dlg.dismiss()
            }
            .show()
    }

    private fun showEnginePickerDialog() {
        val names = engines.map { it.second }.toTypedArray()
        val curIdx = engines.indexOfFirst { it.first == AppConfig.searchEngine }.coerceAtLeast(0)
        ThemeManager.dialogBuilder(this)
            .setTitle("选择默认搜索引擎")
            .setSingleChoiceItems(names, curIdx) { dlg, which ->
                AppConfig.searchEngine = engines[which].first
                if (currentTab().isStartPage) renderStartPageHeaders()
                dlg.dismiss()
            }
            .show()
    }

    private fun classifyCandidate(url: String, hintType: String): Pair<String, String>? {
        val clean = url.substringBefore("#").lowercase()
        val path = clean.substringBefore("?")
        val ext = path.substringAfterLast(".", "").takeIf { it.length in 1..10 } ?: ""
        val customExts = cachedSniffExts

        val alwaysNoise = setOf("jpg", "jpeg", "png", "webp", "avif", "gif", "svg", "ico", "css", "js", "json", "woff", "woff2", "ttf", "eot", "vtt", "srt", "ass")
        if (ext in alwaysNoise && ext !in customExts) {
            return null
        }
        if (ext == "ts" && "ts" !in customExts) return null
        if (path.endsWith("init.mp4") || path.endsWith("init.m4s")) return null
        if (clean.contains("/bfs/") || clean.contains("bvc_preview") || clean.contains("sprite") || clean.contains("avatar") || clean.contains("thumb")) {
            return null
        }

        val audioExts = setOf("mp3", "m4a", "aac", "flac", "wav", "ogg", "opus")
        val streamExts = setOf("m3u8", "mpd")
        val videoExts = setOf("mp4", "flv", "webm", "mkv", "mov", "avi", "m4s", "ts", "rmvb", "m4v")

        if (hintType == "audio" ||
            Regex("302\\d{2}\\.m4s|mime(?:_type)?=audio|/ies-music/|douyinstatic\\.com.*\\.(?:mp3|m4a|aac)", RegexOption.IGNORE_CASE).containsMatchIn(clean) ||
            (ext in audioExts && ext in customExts)
        ) {
            return "audio" to (ext.ifBlank { "m4a" })
        }
        if ((ext in streamExts && ext in customExts) || clean.contains("/api/hls/")) {
            return "m3u8" to (ext.ifBlank { "m3u8" })
        }
        if (Regex("(bilivideo\\.(com|cn)|hdslb\\.com|/upgcxcode/)", RegexOption.IGNORE_CASE).containsMatchIn(clean) &&
            Regex("\\.(m4s|mp4|flv|m3u8)(\\?|#|$)|playurl", RegexOption.IGNORE_CASE).containsMatchIn(clean)
        ) {
            return "bili_dash" to (ext.ifBlank { "mp4" })
        }
        if (Regex("(douyinvod\\.com|iesdouyin\\.com|bytevcloudvod\\.com|kwaicdn\\.com|xhscdn\\.com|googlevideo\\.com/videoplayback)", RegexOption.IGNORE_CASE).containsMatchIn(clean)) {
            return "video" to (ext.ifBlank { "mp4" })
        }
        if (ext.isNotEmpty() && ext in customExts) {
            return when {
                ext in audioExts -> "audio" to ext
                ext in streamExts -> "m3u8" to ext
                ext in videoExts -> "video" to ext
                else -> "file" to ext
            }
        }
        return null
    }

    private fun isMediaCandidate(url: String): Boolean = classifyCandidate(url, "") != null

    private fun normalizeDedupKey(url: String): String {
        val noHash = url.substringBefore("#")
        val path = noHash.substringBefore("?")
        return if (path.endsWith(".m4s") || path.endsWith(".mp4") || path.endsWith(".m3u8")) path else noHash
    }

    private fun recordCandidate(
        tab: BrowserTab,
        url: String,
        hintType: String,
        pageTitle: String,
        pageUrl: String,
        durationSec: Int,
        resolution: String,
        contentLength: Long
    ) {
        val (mType, fileExt) = classifyCandidate(url, hintType) ?: return
        val key = normalizeDedupKey(url)

        synchronized(tab.seenKeys) {
            if (tab.seenKeys.contains(key)) {
                val existing = tab.sniffedList.find { normalizeDedupKey(it.url) == key }
                if (existing != null) {
                    if (durationSec > 0 && existing.durationSec == 0) existing.durationSec = durationSec
                    if (resolution.isNotBlank() && existing.resolution.isBlank()) existing.resolution = resolution
                    if (contentLength > 0 && existing.contentLength == 0L) existing.contentLength = contentLength
                }
                return
            }
            if (tab.sniffedList.size >= 80) return
            tab.seenKeys.add(key)
        }

        val lower = url.lowercase()
        val isBili = lower.contains("bilivideo") || lower.contains("hdslb.com")
        val isAudio = mType == "audio"

        val headers = mutableMapOf<String, String>()
        if (isBili) {
            headers["Referer"] = if (pageUrl.startsWith("http")) pageUrl else "https://www.bilibili.com/"
            headers["Origin"] = "https://www.bilibili.com"
        } else if (pageUrl.startsWith("http")) {
            headers["Referer"] = pageUrl
        }
        val cookie = try { CookieManager.getInstance().getCookie(pageUrl.ifEmpty { url }) ?: "" } catch (_: Throwable) { "" }
        if (cookie.isNotBlank()) headers["Cookie"] = cookie
        headers["User-Agent"] = cachedUserAgent

        // 全站通用音画自动配对：仿照 B站 DASH 模式推广至抖音、YouTube 及所有音视频分离网站
        if (isAudio) {
            val isCompatAac = Regex("302(80|32|16)\\.m4s|mp4a|\\.m4a|\\.aac", RegexOption.IGNORE_CASE).containsMatchIn(lower)
            var pairedCount = 0
            tab.sniffedList.forEach { v ->
                val samePage = pageUrl.isBlank() || v.pageUrl.isBlank() || v.pageUrl == pageUrl
                val isVideoTarget = v.mediaType == "bili_dash" || v.mediaType == "dual_dash" || v.mediaType == "video"
                if (samePage && isVideoTarget && (v.audioUrl.isBlank() || isCompatAac)) {
                    v.audioUrl = url
                    val vIsBili = v.url.lowercase().contains("bilivideo") || v.url.lowercase().contains("hdslb.com") || v.mediaType == "bili_dash"
                    v.mediaType = if (vIsBili) "bili_dash" else "dual_dash"
                    if (!v.title.startsWith("[音画合一]")) {
                        v.title = "[音画合一] ${v.title.removePrefix("[音画合一] ")}"
                    }
                    pairedCount++
                }
            }
            if (isBili && pairedCount > 0) {
                if (currentTab() === tab) updateSniffBadge()
                return
            }
        }

        var pairedAudio = ""
        var finalType = mType
        if (!isAudio && (mType == "video" || mType == "bili_dash")) {
            val matchA = tab.sniffedList.find {
                it.mediaType == "audio" &&
                    (pageUrl.isBlank() || it.pageUrl.isBlank() || it.pageUrl == pageUrl) &&
                    Regex("302(80|32|16)\\.m4s|mp4a|\\.m4a|\\.aac", RegexOption.IGNORE_CASE).containsMatchIn(it.url.lowercase())
            } ?: tab.sniffedList.find {
                it.mediaType == "audio" && (pageUrl.isBlank() || it.pageUrl.isBlank() || it.pageUrl == pageUrl)
            }
            if (matchA != null) {
                pairedAudio = matchA.url
                finalType = if (isBili) "bili_dash" else "dual_dash"
            }
        }

        val cleanTitle = pageTitle.ifBlank { "网页捕获媒体" }
        val displayTitle = when {
            pairedAudio.isNotBlank() && !cleanTitle.startsWith("[音画合一]") -> "[音画合一] $cleanTitle"
            isAudio -> "[独立音频] $cleanTitle"
            else -> cleanTitle
        }

        val item = SniffedMedia(
            id = UUID.randomUUID().toString().take(8),
            title = displayTitle,
            url = url,
            audioUrl = pairedAudio,
            mediaType = finalType,
            resolution = resolution,
            durationSec = durationSec,
            contentLength = contentLength,
            fileExt = fileExt,
            pageUrl = pageUrl,
            headers = headers
        )
        if (isAudio) {
            tab.sniffedList.add(item)
        } else {
            tab.sniffedList.add(0, item)
        }
        if (currentTab() === tab) updateSniffBadge()
    }

    private fun updateSniffBadge() {
        runOnUiThread {
            if (!isFinishing && ::tvSniffedCount.isInitialized) {
                tvSniffedCount.text = currentTab().sniffedList.size.toString()
            }
        }
    }

    private fun showSniffedBottomSheet() {
        val tab = currentTab()
        val dlg = BottomSheetDialog(this)
        ThemeManager.styleBottomSheet(dlg, this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(ThemeManager.current().bgPanel)
            setPadding(36, 32, 36, 32)
        }

        val headerRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, 0, 0, 20)
        }
        headerRow.addView(ImageView(this).apply {
            setImageResource(R.drawable.ic_download)
            setColorFilter(getColor(R.color.accent_cyan))
            layoutParams = LinearLayout.LayoutParams(48, 48).apply { marginEnd = 16 }
        })
        headerRow.addView(TextView(this).apply {
            text = if (tab.sniffedList.isEmpty()) {
                "暂未捕获资源 (可播放视频或点击下载链接)"
            } else {
                "已捕获媒体与文件 (${tab.sniffedList.size}) · 点击查看详情"
            }
            setTextColor(getColor(R.color.text_primary))
            textSize = 14.5f
            setTypeface(null, android.graphics.Typeface.BOLD)
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        })
        root.addView(headerRow)

        lateinit var sniffAdapter: SniffedAdapter
        sniffAdapter = SniffedAdapter(
            tab.sniffedList.toMutableList(),
            onInspect = { item ->
                showMediaDetailDialog(item) {
                    sniffAdapter.notifyDataSetChanged()
                }
            },
            onPreview = { item ->
                launchExternalPreview(item)
            },
            onDownload = { item ->
                TaskManager.addFromSniffed(this@BrowserActivity, item)
                Toast.makeText(this@BrowserActivity, "已加入下载队列: ${item.title}", Toast.LENGTH_SHORT).show()
                dlg.dismiss()
                finish()
            }
        )

        val rv = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@BrowserActivity)
            adapter = sniffAdapter
        }
        root.addView(rv, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 780))
        dlg.setContentView(root)
        dlg.show()
    }

    private fun showMediaDetailDialog(item: SniffedMedia, onMetadataUpdated: () -> Unit) {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(getColor(R.color.bg_panel))
            setPadding(44, 38, 44, 24)
        }

        val typeName = when {
            item.audioUrl.isNotBlank() || item.mediaType == "bili_dash" || item.mediaType == "dual_dash" -> "音画双流分离合并 (FFmpeg 一键合成 MP4)"
            item.mediaType == "m3u8" -> "M3U8 HLS 分片流"
            item.mediaType == "audio" -> "音频文件 (.${item.fileExt.ifBlank { "m4a" }})"
            item.mediaType == "file" -> "文档 / 压缩包 / 安装包 (.${item.fileExt.ifBlank { "bin" }})"
            else -> "视频直链 (.${item.fileExt.ifBlank { "mp4" }})"
        }

        val tvInfo = TextView(this).apply {
            setTextColor(getColor(R.color.text_secondary))
            textSize = 13f
            setLineSpacing(8f, 1.15f)
            setBackgroundResource(R.drawable.bg_card)
            setPadding(28, 24, 28, 24)
        }

        fun renderDetailText(probing: Boolean) {
            val durStr = if (item.durationSec > 0) "${SniffedAdapter.formatDuration(item.durationSec)} (${item.durationSec} 秒)" else if (probing) "正在探测..." else "未知 / 直播流"
            val resStr = item.resolution.ifBlank { if (probing) "正在探测..." else "未知 (下载后原生封装保留原画)" }
            val sizeStr = if (item.contentLength > 0) SniffedAdapter.formatBytes(item.contentLength) else if (item.mediaType == "m3u8") "流媒体分片 (按播放时长估算)" else if (probing) "正在探测..." else "未知"
            val codecLine = if (item.codecHint.isNotBlank()) "\n编码信息：${item.codecHint}" else ""

            tvInfo.text = buildString {
                append("标题：${item.title}\n")
                append("类型：$typeName\n")
                append("时长：$durStr\n")
                append("分辨率：$resStr\n")
                append("文件大小：$sizeStr")
                append(codecLine)
                append("\n\n直链地址：\n${item.url}")
                if (item.pageUrl.isNotBlank()) {
                    append("\n\n来源网页：\n${item.pageUrl}")
                }
            }
        }

        renderDetailText(probing = true)
        box.addView(tvInfo)

        val dlg = ThemeManager.dialogBuilder(this)
            .setTitle("资源详细信息")
            .setView(box)
            .setPositiveButton("立即下载") { _, _ ->
                TaskManager.addFromSniffed(this, item)
                Toast.makeText(this, "已加入下载队列: ${item.title}", Toast.LENGTH_SHORT).show()
                finish()
            }
            .setNeutralButton(if (item.mediaType == "file") "复制链接" else "外部在线预览") { _, _ ->
                if (item.mediaType == "file") {
                    val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    cm.setPrimaryClip(ClipData.newPlainText("url", item.url))
                    Toast.makeText(this, "已复制资源链接到剪贴板", Toast.LENGTH_SHORT).show()
                } else {
                    launchExternalPreview(item)
                }
            }
            .setNegativeButton("关闭", null)
            .create()
        dlg.show()

        scope.launch(Dispatchers.IO) {
            probeMediaMetadata(item)
            withContext(Dispatchers.Main) {
                if (!isFinishing && dlg.isShowing) {
                    renderDetailText(probing = false)
                    onMetadataUpdated()
                }
            }
        }
    }

    private fun launchExternalPreview(item: SniffedMedia) {
        Toast.makeText(this, "正在建立本地防盗链代理通道...", Toast.LENGTH_SHORT).show()
        scope.launch {
            val proxyUrl = LocalStreamProxy.openExternalPreview(
                this@BrowserActivity,
                item.url,
                item.mediaType,
                item.headers
            )
            if (isFinishing) return@launch
            try {
                val mime = if (item.mediaType == "audio") "audio/*" else "video/*"
                val intent = Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(android.net.Uri.parse(proxyUrl), mime)
                }
                startActivity(Intent.createChooser(intent, "选择外部播放器在线预览"))
            } catch (_: Throwable) {
                Toast.makeText(this@BrowserActivity, "未找到可用的外部播放器，正在尝试内置播放", Toast.LENGTH_SHORT).show()
                startActivity(
                    Intent(this@BrowserActivity, PlayerActivity::class.java)
                        .putExtra("play_url", proxyUrl)
                        .putExtra("title", item.title)
                )
            }
        }
    }

    private fun probeMediaMetadata(item: SniffedMedia) {
        try {
            val reqB = Request.Builder().url(item.url)
            item.headers.forEach { (k, v) -> if (k.isNotBlank() && v.isNotBlank()) reqB.header(k, v) }

            if (item.mediaType == "m3u8") {
                probeClient.newCall(reqB.get().build()).execute().use { resp ->
                    val body = resp.body?.string()?.take(65536) ?: return
                    if (item.resolution.isBlank()) {
                        Regex("RESOLUTION=(\\d+x\\d+)", RegexOption.IGNORE_CASE).findAll(body).maxByOrNull { m ->
                            m.groupValues[1].substringAfter("x").toIntOrNull() ?: 0
                        }?.let { m -> item.resolution = m.groupValues[1] }
                    }
                    if (item.codecHint.isBlank()) {
                        Regex("CODECS=\"([^\"]+)\"", RegexOption.IGNORE_CASE).find(body)?.let { m ->
                            item.codecHint = m.groupValues[1]
                        }
                    }
                    if (item.durationSec <= 0) {
                        var sum = 0.0
                        Regex("#EXTINF:([0-9.]+)").findAll(body).forEach { m ->
                            sum += m.groupValues[1].toDoubleOrNull() ?: 0.0
                        }
                        if (sum > 0.5) item.durationSec = sum.toInt()
                    }
                }
            } else {
                probeClient.newCall(reqB.head().build()).execute().use { resp ->
                    val len = resp.header("Content-Length")?.toLongOrNull() ?: 0L
                    if (len > 0L) item.contentLength = len
                    val cType = resp.header("Content-Type") ?: ""
                    if (item.codecHint.isBlank() && cType.isNotBlank()) {
                        item.codecHint = cType.substringBefore(";")
                    }
                }
            }
        } catch (_: Throwable) {}
    }

    private fun openSeriesPicker() {
        val tab = currentTab()
        val wv = tab.webView
        val curUrl = wv?.url ?: tab.currentUrl
        if (tab.isStartPage || !curUrl.startsWith("http")) {
            Toast.makeText(this, "请先打开一个剧集/视频网页", Toast.LENGTH_SHORT).show()
            return
        }

        val cookie = try { CookieManager.getInstance().getCookie(curUrl) ?: "" } catch (_: Throwable) { "" }
        val hdrs = mapOf("Cookie" to cookie, "User-Agent" to cachedUserAgent)

        Toast.makeText(this, "正在探测当前网页同系列合集...", Toast.LENGTH_SHORT).show()
        wv?.evaluateJavascript(SnifferScripts.SCAN_SERIES_JS) { jsRes ->
            scope.launch(Dispatchers.IO) {
                val apiRes = VideoParser.parseVideoUrl(curUrl, hdrs)
                var chosenSeries = apiRes.series

                if (chosenSeries == null && !jsRes.isNullOrBlank() && jsRes != "null") {
                    try {
                        val unquoted = JSONObject("{\"v\":$jsRes}").getString("v")
                        val obj = JSONObject(unquoted)
                        if (obj.optBoolean("has_series")) {
                            val arr = obj.getJSONArray("episodes")
                            val eps = (0 until arr.length()).map { i ->
                                val o = arr.getJSONObject(i)
                                SeriesEpisode(o.getInt("index"), o.getString("title"), o.getString("page_url"))
                            }
                            if (eps.size > 1) {
                                chosenSeries = SeriesInfo(obj.optString("series_title", "同系列合集"), "web_dom", eps.size, obj.optInt("current_index"), curUrl, eps)
                            }
                        }
                    } catch (_: Exception) {}
                }

                withContext(Dispatchers.Main) {
                    if (isFinishing) return@withContext
                    val finalSeries = chosenSeries
                    if (finalSeries == null || finalSeries.episodes.size < 2) {
                        Toast.makeText(this@BrowserActivity, "当前页面未检测到多集或合集列表", Toast.LENGTH_SHORT).show()
                    } else {
                        showSeriesPickerDialog(finalSeries, hdrs)
                    }
                }
            }
        }
    }

    private fun showSeriesPickerDialog(series: SeriesInfo, extraHeaders: Map<String, String>) {
        val dlg = BottomSheetDialog(this)
        ThemeManager.styleBottomSheet(dlg, this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(ThemeManager.current().bgPanel)
            setPadding(36, 32, 36, 32)
        }
        val titleRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, 0, 0, 16)
        }
        titleRow.addView(ImageView(this).apply {
            setImageResource(R.drawable.ic_series)
            setColorFilter(getColor(R.color.accent_cyan))
            layoutParams = LinearLayout.LayoutParams(46, 46).apply { marginEnd = 14 }
        })
        titleRow.addView(TextView(this).apply {
            text = "${series.seriesTitle} (共 ${series.total} 集)"
            setTextColor(getColor(R.color.accent_cyan))
            textSize = 15.5f
            setTypeface(null, android.graphics.Typeface.BOLD)
        })
        root.addView(titleRow)

        lateinit var dlBtn: Button
        val adapter = SeriesAdapter(series.episodes) {
            val cnt = series.episodes.count { it.selected }
            dlBtn.text = "一键爬取选中 ($cnt 集)"
            dlBtn.isEnabled = cnt > 0
        }

        val rv = RecyclerView(this).apply {
            layoutManager = LinearLayoutManager(this@BrowserActivity)
            this.adapter = adapter
        }
        root.addView(rv, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 680))

        dlBtn = Button(this).apply {
            text = "一键爬取选中 (${series.episodes.count { it.selected }} 集)"
            setBackgroundResource(R.drawable.bg_pill_series)
            setTextColor(0xFFFFFFFF.toInt())
            setOnClickListener {
                val chosen = series.episodes.filter { it.selected }
                if (chosen.isEmpty()) return@setOnClickListener
                VideoParser.submitSeriesDownloads(this@BrowserActivity, chosen, series.seriesTitle, true, true, extraHeaders) { msg ->
                    if (!isFinishing) Toast.makeText(this@BrowserActivity, msg, Toast.LENGTH_SHORT).show()
                }
                dlg.dismiss()
                finish()
            }
        }
        val lpBtn = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 114).apply { topMargin = 20 }
        root.addView(dlBtn, lpBtn)
        dlg.setContentView(root)
        dlg.show()
    }
}

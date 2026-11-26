package com.starstream.downloader

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.webkit.MimeTypeMap
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.core.view.GravityCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.drawerlayout.widget.DrawerLayout
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.google.android.material.floatingactionbutton.FloatingActionButton
import com.google.android.material.navigation.NavigationView
import com.starstream.downloader.core.AppConfig
import com.starstream.downloader.core.DownloadTask
import com.starstream.downloader.core.HttpClientProvider
import com.starstream.downloader.core.TaskManager
import com.starstream.downloader.core.TaskStatus
import com.starstream.downloader.ui.BrowserActivity
import com.starstream.downloader.ui.DownloadTaskAdapter
import com.starstream.downloader.ui.IconMenuItem
import com.starstream.downloader.ui.OnboardingDialog
import com.starstream.downloader.ui.ParserActivity
import com.starstream.downloader.ui.SettingsActivity
import com.starstream.downloader.ui.ThemeManager
import com.starstream.downloader.ui.showIconMenuDialog
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.util.UUID

class MainActivity : AppCompatActivity() {

    private lateinit var drawerLayout: DrawerLayout
    private lateinit var swipeDownloads: SwipeRefreshLayout
    private lateinit var rvDownloads: RecyclerView
    private lateinit var emptyView: View
    private lateinit var tabAll: TextView
    private lateinit var tabActive: TextView
    private lateinit var tabDone: TextView
    private lateinit var adapter: DownloadTaskAdapter
    private lateinit var tvToolbarTitle: TextView
    private lateinit var layoutSelectionBar: View
    private lateinit var tvSelectionCount: TextView
    private val mainScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var filterMode = 0 // 0=全部, 1=队列中, 2=已完成

    companion object {
        private const val CURRENT_VERSION = "3.3.0"
        private const val REPO_URL = "https://github.com/xuewexin/StarStream"
        private const val ISSUES_URL = "https://github.com/xuewexin/StarStream/issues"
    }

    private val listener: () -> Unit = {
        runOnUiThread {
            if (!isFinishing && !isDestroyed) refreshList()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AppConfig.init(this)
        TaskManager.init(this)
        setContentView(R.layout.activity_main)

        val coordinator = findViewById<View>(R.id.main_coordinator)
        val navView = findViewById<NavigationView>(R.id.nav_view)
        ViewCompat.setOnApplyWindowInsetsListener(coordinator) { v, windowInsets ->
            val insets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(insets.left, insets.top, insets.right, insets.bottom)
            windowInsets
        }
        ViewCompat.setOnApplyWindowInsetsListener(navView) { v, windowInsets ->
            val insets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(0, insets.top, 0, insets.bottom)
            windowInsets
        }

        drawerLayout = findViewById(R.id.drawer_layout)
        swipeDownloads = findViewById(R.id.swipe_downloads)
        rvDownloads = findViewById(R.id.rv_downloads)
        emptyView = findViewById(R.id.tv_empty_downloads)
        tabAll = findViewById(R.id.tab_all)
        tabActive = findViewById(R.id.tab_active)
        tabDone = findViewById(R.id.tab_done)

        swipeDownloads.setColorSchemeResources(R.color.accent_cyan, R.color.accent_blue)
        swipeDownloads.setProgressBackgroundColorSchemeResource(R.color.bg_card)
        swipeDownloads.setOnRefreshListener {
            refreshList()
            mainScope.launch {
                val refreshedCnt = TaskManager.refreshAllTaskTokens(this@MainActivity)
                if (!isFinishing) {
                    refreshList()
                    swipeDownloads.isRefreshing = false
                    val msg = if (refreshedCnt > 0) {
                        "已刷新下载列表，并更新 $refreshedCnt 个任务的加速令牌"
                    } else {
                        "下载列表已是最新状态"
                    }
                    Toast.makeText(this@MainActivity, msg, Toast.LENGTH_SHORT).show()
                }
            }
        }

        tvToolbarTitle = findViewById(R.id.tv_toolbar_title)
        layoutSelectionBar = findViewById(R.id.layout_selection_bar)
        tvSelectionCount = findViewById(R.id.tv_selection_count)
        adapter = DownloadTaskAdapter(
            emptyList(),
            onAction = { task -> handleTaskAction(task) },
            onPreview = { task -> startWatchWhileDownloading(task) },
            onDelete = { task -> promptDeleteTaskDialog(task) },
            onMore = { task -> showTaskMoreMenu(task) },
            onSelectionChanged = { count ->
                val isMulti = adapter.selectionMode
                layoutSelectionBar.visibility = if (isMulti) View.VISIBLE else View.GONE
                tvSelectionCount.text = "已选 $count 项"
                tvToolbarTitle.text = if (isMulti) "已选 $count 项" else "星流下载器"
            },
            onEnterSelectionMode = { taskId ->
                adapter.setSelectionMode(true, initialSelectedId = taskId)
                Toast.makeText(this, "已进入多选，点选任务后操作任意一项即可作用于整体", Toast.LENGTH_SHORT).show()
            }
        )
        rvDownloads.layoutManager = LinearLayoutManager(this)
        rvDownloads.adapter = adapter

        findViewById<View>(R.id.btn_toolbar_select).setOnClickListener {
            adapter.setSelectionMode(!adapter.selectionMode)
        }
        findViewById<View>(R.id.btn_sel_all).setOnClickListener {
            adapter.selectAllShown()
        }
        findViewById<View>(R.id.btn_sel_done).setOnClickListener {
            adapter.setSelectionMode(false)
        }
        findViewById<View>(R.id.btn_sel_settings).setOnClickListener {
            val targets = if (adapter.selectedIds.isNotEmpty()) adapter.selectedIds.toList()
            else TaskManager.getAllTasks().filter { it.status != TaskStatus.COMPLETED }.map { it.id }
            showTaskSettingsDialog(targets)
        }
        findViewById<View>(R.id.btn_sel_patrol).setOnClickListener {
            mainScope.launch(Dispatchers.IO) {
                val r = TaskManager.runPatrol(this@MainActivity, forceCleanup = true)
                withContext(Dispatchers.Main) {
                    if (!isFinishing) {
                        refreshList()
                        Toast.makeText(
                            this@MainActivity,
                            "巡检完成：修复 ${r.fixed} 项，清理分片 ${r.cleaned} 处，唤醒 ${r.kicked} 项",
                            Toast.LENGTH_SHORT
                        ).show()
                    }
                }
            }
        }

        findViewById<View>(R.id.btn_open_drawer).setOnClickListener {
            drawerLayout.openDrawer(GravityCompat.START)
        }
        findViewById<View>(R.id.btn_toolbar_browser).setOnClickListener {
            startActivity(Intent(this, BrowserActivity::class.java))
        }
        findViewById<View>(R.id.btn_toolbar_parser).setOnClickListener {
            startActivity(Intent(this, ParserActivity::class.java))
        }
        findViewById<View>(R.id.btn_toolbar_more).setOnClickListener {
            showMoreMenu()
        }

        tabAll.setOnClickListener { filterMode = 0; updateFilterTabs(); refreshList() }
        tabActive.setOnClickListener { filterMode = 1; updateFilterTabs(); refreshList() }
        tabDone.setOnClickListener { filterMode = 2; updateFilterTabs(); refreshList() }

        findViewById<FloatingActionButton>(R.id.fab_add_download).setOnClickListener {
            showAddDownloadDialog()
        }

        navView.setNavigationItemSelectedListener { item ->
            drawerLayout.closeDrawer(GravityCompat.START)
            when (item.itemId) {
                R.id.drawer_all -> { filterMode = 0; updateFilterTabs(); refreshList() }
                R.id.drawer_active -> { filterMode = 1; updateFilterTabs(); refreshList() }
                R.id.drawer_done -> { filterMode = 2; updateFilterTabs(); refreshList() }
                R.id.drawer_browser -> startActivity(Intent(this, BrowserActivity::class.java))
                R.id.drawer_parser -> startActivity(Intent(this, ParserActivity::class.java))
                R.id.drawer_settings -> startActivity(Intent(this, SettingsActivity::class.java))
                R.id.drawer_guide -> OnboardingDialog.showIfNeeded(this, force = true)
                R.id.drawer_check_update -> checkForUpdates()
                R.id.drawer_about -> showAboutDialog()
                R.id.drawer_share -> shareApp()
            }
            true
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (drawerLayout.isDrawerOpen(GravityCompat.START)) {
                    drawerLayout.closeDrawer(GravityCompat.START)
                } else if (adapter.selectionMode) {
                    adapter.setSelectionMode(false)
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        TaskManager.addListener(listener)
        updateFilterTabs()
        refreshList()
        requestNotificationPermissionIfNeeded()
        checkLastCrashLog()
        handleShareIntent(intent)

        ThemeManager.applyTheme(this, coordinator, navView)
        OnboardingDialog.showIfNeeded(this, force = false)
    }

    override fun onResume() {
        super.onResume()
        ThemeManager.applyTheme(this, findViewById(R.id.main_coordinator), findViewById(R.id.nav_view))
        refreshList()
    }

    override fun onDestroy() {
        mainScope.cancel()
        TaskManager.removeListener(listener)
        super.onDestroy()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleShareIntent(intent)
    }

    private fun handleShareIntent(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            val sharedText = intent.getStringExtra(Intent.EXTRA_TEXT)
            if (!sharedText.isNullOrBlank()) {
                startActivity(Intent(this, ParserActivity::class.java).putExtra("initial_url", sharedText))
            }
        }
    }

    private fun updateFilterTabs() {
        val tabs = listOf(tabAll to 0, tabActive to 1, tabDone to 2)
        tabs.forEach { (tv, m) ->
            val sel = filterMode == m
            tv.setTextColor(ContextCompat.getColor(this, if (sel) R.color.accent_blue else R.color.text_muted))
            tv.setTypeface(null, if (sel) android.graphics.Typeface.BOLD else android.graphics.Typeface.NORMAL)
        }
    }

    private fun refreshList() {
        val all = TaskManager.getAllTasks()
        val active = all.filter { it.status == TaskStatus.DOWNLOADING || it.status == TaskStatus.WAITING || it.status == TaskStatus.MUXING || it.status == TaskStatus.PAUSED }
        val done = all.filter { it.status == TaskStatus.COMPLETED }

        tabAll.text = "全部 (${all.size})"
        tabActive.text = "队列中 (${active.size})"
        tabDone.text = "已完成 (${done.size})"

        val shown = when (filterMode) {
            1 -> active
            2 -> done
            else -> all
        }
        adapter.updateData(shown)
        emptyView.visibility = if (shown.isEmpty()) View.VISIBLE else View.GONE
    }

    private fun checkForUpdates() {
        Toast.makeText(this, "正在连接 GitHub 检查最新版本...", Toast.LENGTH_SHORT).show()
        mainScope.launch(Dispatchers.IO) {
            var latestTag = ""
            var notes = ""
            var htmlUrl = "$REPO_URL/releases"
            var errMsg = ""
            try {
                val req = Request.Builder()
                    .url("https://api.github.com/repos/xuewexin/StarStream/releases/latest")
                    .header("User-Agent", "StarStream-Android/$CURRENT_VERSION")
                    .build()
                HttpClientProvider.getClient().newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val obj = JSONObject(resp.body?.string() ?: "{}")
                        latestTag = obj.optString("tag_name").trim()
                        notes = obj.optString("body").trim().take(600)
                        htmlUrl = obj.optString("html_url", htmlUrl)
                    } else if (resp.code == 404) {
                        latestTag = "v$CURRENT_VERSION"
                    } else {
                        errMsg = "HTTP ${resp.code}"
                    }
                }
            } catch (e: Exception) {
                errMsg = e.message ?: "网络请求超时"
            }

            withContext(Dispatchers.Main) {
                if (isFinishing) return@withContext
                if (errMsg.isNotEmpty()) {
                    ThemeManager.dialogBuilder(this@MainActivity)
                        .setTitle("检查更新失败")
                        .setMessage("当前版本：v$CURRENT_VERSION\n原因：$errMsg\n\n若 GitHub 访问受限，可在设置中心配置 HTTP 代理后重试。")
                        .setPositiveButton("前往发布页") { _, _ -> openUrlExternally(htmlUrl) }
                        .setNegativeButton("关闭", null)
                        .show()
                } else {
                    val cleanRemote = latestTag.removePrefix("v")
                    val hasNew = cleanRemote.isNotBlank() && cleanRemote != CURRENT_VERSION
                    val msg = if (hasNew) {
                        "当前版本：v$CURRENT_VERSION\n最新版本：$latestTag\n\n更新说明：\n${notes.ifBlank { "请前往 GitHub Releases 查看完整更新说明。" }}"
                    } else {
                        "当前版本：v$CURRENT_VERSION\n\n已是最新版本，感谢使用星流下载器！"
                    }
                    ThemeManager.dialogBuilder(this@MainActivity)
                        .setTitle(if (hasNew) "发现新版本 $latestTag" else "软件更新检查")
                        .setMessage(msg)
                        .setPositiveButton(if (hasNew) "前往下载更新" else "访问项目主页") { _, _ -> openUrlExternally(htmlUrl) }
                        .setNegativeButton("关闭", null)
                        .show()
                }
            }
        }
    }

    private fun showAboutDialog() {
        val msg = "星流媒体嗅探与下载器 (StarStream Pro)\n" +
            "当前版本：v$CURRENT_VERSION\n" +
            "开发作者：xuewexin\n\n" +
            "项目主页：\n$REPO_URL\n\n" +
            "作者联系方式：\n" +
            "· QQ 邮箱：2792893068@qq.com\n" +
            "· Gmail：lepa23216@gmail.com\n" +
            "· 问题与建议反馈：$ISSUES_URL"
        ThemeManager.dialogBuilder(this)
            .setTitle("项目地址与作者联系")
            .setMessage(msg)
            .setPositiveButton("打开项目主页") { _, _ -> openUrlExternally(REPO_URL) }
            .setNeutralButton("复制项目链接") { _, _ ->
                val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                cm.setPrimaryClip(ClipData.newPlainText("repo", REPO_URL))
                Toast.makeText(this, "已复制项目地址", Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton("关闭", null)
            .show()
    }

    private fun shareApp() {
        val shareText = "推荐「星流下载器 (StarStream v$CURRENT_VERSION)」\n" +
            "支持内置多内核浏览器媒体/文档全类型嗅探、同系列剧集一键连爬与原生无损音画混流：\n" +
            "$REPO_URL"
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, "星流下载器 StarStream v$CURRENT_VERSION")
            putExtra(Intent.EXTRA_TEXT, shareText)
        }
        startActivity(Intent.createChooser(intent, "分享星流下载器给好友"))
    }

    private fun openUrlExternally(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (_: Exception) {
            Toast.makeText(this, "无法打开浏览器，已为您显示地址：$url", Toast.LENGTH_LONG).show()
        }
    }

    private fun showAddDownloadDialog() {
        val input = EditText(this).apply {
            hint = "输入 M3U8 / MP4 / 文档直链或视频页面链接..."
            setPadding(40, 30, 40, 30)
        }
        ThemeManager.dialogBuilder(this)
            .setTitle("新建下载任务")
            .setView(input)
            .setPositiveButton("直链下载") { _, _ ->
                val u = input.text.toString().trim()
                if (!u.startsWith("http")) {
                    Toast.makeText(this, "请输入有效的 http/https 链接", Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }
                val lower = u.substringBefore("?").lowercase()
                val mType = when {
                    lower.endsWith(".m3u8") -> "m3u8"
                    lower.endsWith(".mp3") || lower.endsWith(".m4a") || lower.endsWith(".flac") || lower.endsWith(".aac") -> "audio"
                    lower.endsWith(".pdf") || lower.endsWith(".zip") || lower.endsWith(".rar") || lower.endsWith(".7z") || lower.endsWith(".apk") -> "file"
                    else -> "video"
                }
                TaskManager.addTask(
                    this,
                    DownloadTask(
                        id = UUID.randomUUID().toString().take(8),
                        title = "新建任务_${System.currentTimeMillis() % 10000}",
                        url = u,
                        mediaType = mType
                    ),
                    autoStart = true
                )
            }
            .setNeutralButton("全网深度解析") { _, _ ->
                val u = input.text.toString().trim()
                startActivity(Intent(this, ParserActivity::class.java).putExtra("initial_url", u))
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun showMoreMenu() {
        val items = mutableListOf(
            IconMenuItem(R.drawable.ic_info, if (adapter.selectionMode) "退出多选模式" else "多选任务", "勾选多个任务后操作任意一项即可作用于整体"),
            IconMenuItem(R.drawable.ic_refresh, "全部暂停", "暂停当前正在下载与等待队列"),
            IconMenuItem(R.drawable.ic_download, "全部继续", "恢复所有已暂停或失败任务"),
            IconMenuItem(R.drawable.ic_refresh, "队列巡检清理", "核查已完成任务状态并清理残余临时分片"),
            IconMenuItem(R.drawable.ic_close, "清理已完成记录", "仅移除记录，保留本地文件"),
            IconMenuItem(R.drawable.ic_guide, "新手引导教程", "查看内置浏览器、嗅探与设置说明"),
            IconMenuItem(R.drawable.ic_settings, "下载与存储设置", "并发任务数、多线程、自定义储存路径"),
            IconMenuItem(R.drawable.ic_update, "检查更新与关于", "查看最新版本及作者联系方式")
        )
        showIconMenuDialog(this, "任务与功能管理", items) { which ->
            when (which) {
                0 -> {
                    val enable = !adapter.selectionMode
                    adapter.setSelectionMode(enable)
                }
                1 -> TaskManager.getAllTasks().filter { it.status == TaskStatus.DOWNLOADING || it.status == TaskStatus.WAITING }.forEach { TaskManager.pauseTask(it.id, this) }
                2 -> TaskManager.getAllTasks().filter { it.status == TaskStatus.PAUSED || it.status == TaskStatus.ERROR }.forEach { TaskManager.startTask(this, it.id) }
                3 -> {
                    mainScope.launch(Dispatchers.IO) {
                        val r = TaskManager.runPatrol(this@MainActivity, forceCleanup = true)
                        withContext(Dispatchers.Main) {
                            if (!isFinishing) {
                                refreshList()
                                Toast.makeText(
                                    this@MainActivity,
                                    "巡检完成：修复 ${r.fixed} 项，清理分片 ${r.cleaned} 处，唤醒 ${r.kicked} 项",
                                    Toast.LENGTH_SHORT
                                ).show()
                            }
                        }
                    }
                }
                4 -> {
                    val done = TaskManager.getAllTasks().filter { it.status == TaskStatus.COMPLETED }
                    done.forEach { TaskManager.deleteTask(it.id, deleteFile = false, context = this) }
                    Toast.makeText(this, "已清理 ${done.size} 条记录", Toast.LENGTH_SHORT).show()
                }
                5 -> OnboardingDialog.showIfNeeded(this, force = true)
                6 -> startActivity(Intent(this, SettingsActivity::class.java))
                7 -> checkForUpdates()
            }
        }
    }

    private fun startWatchWhileDownloading(task: DownloadTask) {
        Toast.makeText(this, "正在启动边下边看流媒体缓冲...", Toast.LENGTH_SHORT).show()
        mainScope.launch(Dispatchers.IO) {
            val streamUrl = com.starstream.downloader.core.LocalStreamProxy.buildTaskStreamUrl(task)
            withContext(Dispatchers.Main) {
                if (!isFinishing) {
                    startActivity(
                        Intent(this@MainActivity, com.starstream.downloader.ui.PlayerActivity::class.java)
                            .putExtra("play_url", streamUrl)
                            .putExtra("title", task.title)
                    )
                }
            }
        }
    }

    private fun getActionTargets(clickedTask: DownloadTask): List<String> {
        return if (adapter.selectionMode && adapter.selectedIds.isNotEmpty()) {
            adapter.selectedIds.toList()
        } else {
            listOf(clickedTask.id)
        }
    }

    private fun handleTaskAction(t: DownloadTask) {
        val targets = getActionTargets(t)
        if (targets.size > 1) {
            when (t.status) {
                TaskStatus.DOWNLOADING, TaskStatus.WAITING, TaskStatus.MUXING -> {
                    targets.forEach { TaskManager.pauseTask(it, this) }
                    Toast.makeText(this, "已暂停选中的 ${targets.size} 个任务", Toast.LENGTH_SHORT).show()
                    return
                }
                TaskStatus.PAUSED -> {
                    targets.forEach { TaskManager.startTask(this, it) }
                    Toast.makeText(this, "已继续选中的 ${targets.size} 个任务", Toast.LENGTH_SHORT).show()
                    return
                }
                TaskStatus.ERROR -> {
                    targets.forEach { TaskManager.retryTask(this, it) }
                    Toast.makeText(this, "已重新尝试选中的 ${targets.size} 个任务", Toast.LENGTH_SHORT).show()
                    return
                }
                TaskStatus.COMPLETED -> {}
            }
        }

        when (t.status) {
            TaskStatus.DOWNLOADING, TaskStatus.WAITING, TaskStatus.MUXING -> TaskManager.pauseTask(t.id, this)
            TaskStatus.PAUSED -> TaskManager.startTask(this, t.id)
            TaskStatus.ERROR -> TaskManager.retryTask(this, t.id)
            TaskStatus.COMPLETED -> {
                val f = File(t.outputPath)
                if (!f.exists()) {
                    ThemeManager.dialogBuilder(this)
                        .setTitle("文件不存在")
                        .setMessage("本地文件可能已被移动或清理，是否重新尝试下载？")
                        .setPositiveButton("重新下载") { _, _ -> TaskManager.retryTask(this, t.id) }
                        .setNegativeButton("取消", null)
                        .show()
                    return
                }
                try {
                    val uri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", f)
                    val ext = f.extension.lowercase()
                    val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext)
                        ?: when (ext) {
                            "mp3", "m4a", "aac", "flac", "wav", "ogg", "opus" -> "audio/*"
                            "pdf" -> "application/pdf"
                            "zip", "rar", "7z" -> "application/octet-stream"
                            "apk" -> "application/vnd.android.package-archive"
                            else -> "video/*"
                        }
                    val intent = Intent(Intent.ACTION_VIEW).apply {
                        setDataAndType(uri, mime)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    startActivity(intent)
                } catch (e: Exception) {
                    Toast.makeText(this, "已保存: ${t.outputPath}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun promptDeleteTaskDialog(task: DownloadTask) {
        val targets = getActionTargets(task)
        if (targets.size > 1) {
            ThemeManager.dialogBuilder(this)
                .setTitle("删除选中的 ${targets.size} 个任务")
                .setMessage("当前多选已生效，操作将作用于全部选中的 ${targets.size} 个任务：\n· 仅删除记录：保留本地文件\n· 连带删除本地文件：同时清理视频与临时分片")
                .setPositiveButton("仅删除记录") { _, _ ->
                    targets.forEach { TaskManager.deleteTask(it, deleteFile = false, context = this) }
                    adapter.setSelectionMode(false)
                    Toast.makeText(this, "已删除 ${targets.size} 条任务记录", Toast.LENGTH_SHORT).show()
                }
                .setNegativeButton("连带删除本地文件") { _, _ ->
                    targets.forEach { TaskManager.deleteTask(it, deleteFile = true, context = this) }
                    adapter.setSelectionMode(false)
                    Toast.makeText(this, "已删除 ${targets.size} 个任务与本地文件", Toast.LENGTH_SHORT).show()
                }
                .setNeutralButton("取消", null)
                .show()
            return
        }

        val hasLocal = task.outputPath.isNotBlank() || task.exportedUri.isNotBlank()
        val msg = if (hasLocal) {
            "请选择对「${task.title}」的删除方式：\n· 仅删除记录：保留本地已下载文件\n· 连带删除文件：同时清除本地文件与临时分片"
        } else {
            "确定从下载列表中移除「${task.title}」吗？"
        }
        val builder = ThemeManager.dialogBuilder(this)
            .setTitle("删除下载任务")
            .setMessage(msg)
            .setNeutralButton("取消", null)
            .setPositiveButton("仅删除记录") { _, _ ->
                TaskManager.deleteTask(task.id, deleteFile = false, context = this)
                Toast.makeText(this, "已仅删除任务记录", Toast.LENGTH_SHORT).show()
            }
        if (hasLocal) {
            builder.setNegativeButton("连带删除本地文件") { _, _ ->
                TaskManager.deleteTask(task.id, deleteFile = true, context = this)
                Toast.makeText(this, "已删除任务记录与本地文件", Toast.LENGTH_SHORT).show()
            }
        }
        builder.show()
    }

    private fun promptRenameTaskDialog(task: DownloadTask) {
        val input = EditText(this).apply {
            setText(task.title)
            setSelection(text.length)
            hint = "输入新的任务与文件名称..."
            setPadding(44, 30, 44, 30)
        }
        ThemeManager.dialogBuilder(this)
            .setTitle("重命名任务 / 本地文件")
            .setView(input)
            .setPositiveButton("确定修改") { _, _ ->
                val newName = input.text.toString().trim()
                if (newName.isEmpty()) {
                    Toast.makeText(this, "名称不能为空", Toast.LENGTH_SHORT).show()
                } else if (TaskManager.renameTask(this, task.id, newName)) {
                    Toast.makeText(this, "已重命名为：$newName", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun showTaskMoreMenu(task: DownloadTask) {
        val targets = getActionTargets(task)
        val isMulti = targets.size > 1 || adapter.selectionMode
        val menuTitle = if (targets.size > 1) "作用于已选中的 ${targets.size} 个任务" else task.title

        val actions = mutableListOf<Pair<IconMenuItem, () -> Unit>>()
        if (targets.size <= 1) {
            actions += IconMenuItem(R.drawable.ic_info, "重命名任务与文件", "同步修改列表标题与已下载文件名") to {
                promptRenameTaskDialog(task)
            }
        }
        actions += IconMenuItem(
            R.drawable.ic_settings,
            if (targets.size > 1) "修改下载参数设置（作用于 ${targets.size} 项）" else "修改下载参数设置",
            "调整并发任务数、线程数、自动转封装 MP4 等"
        ) to {
            showTaskSettingsDialog(targets)
        }
        actions += IconMenuItem(R.drawable.ic_refresh, "刷新令牌并加速下载", "同步最新 Cookie/签名并重置限速链路") to {
            Toast.makeText(this, "正在为 ${targets.size} 项刷新令牌并提速...", Toast.LENGTH_SHORT).show()
            targets.forEach { tid ->
                TaskManager.boostTaskToken(this, tid) { _ -> }
            }
        }
        if (targets.size <= 1 && task.mediaType != "file" && task.url.startsWith("http")) {
            actions += IconMenuItem(R.drawable.ic_video, "边下边看 / 在线预览", "使用内置缓冲代理立即播放") to {
                startWatchWhileDownloading(task)
            }
        }
        actions += IconMenuItem(R.drawable.ic_download, "重新尝试下载", "清理残留缓存并重新拉取音视频流") to {
            targets.forEach { TaskManager.retryTask(this, it) }
            Toast.makeText(this, "已开始重新下载（${targets.size} 项）", Toast.LENGTH_SHORT).show()
        }
        if (isMulti) {
            actions += IconMenuItem(R.drawable.ic_info, "全选当前列表", "勾选全部可见任务") to {
                adapter.selectAllShown()
            }
            actions += IconMenuItem(R.drawable.ic_close, "退出多选模式", "返回普通单任务视图") to {
                adapter.setSelectionMode(false)
            }
        } else {
            actions += IconMenuItem(R.drawable.ic_info, "多选此任务", "开启多选勾选，后续操作将作用于所有选中项") to {
                adapter.setSelectionMode(true, initialSelectedId = task.id)
            }
        }
        actions += IconMenuItem(R.drawable.ic_close, "删除任务", "可选仅删除记录或连带删除本地文件") to {
            promptDeleteTaskDialog(task)
        }

        showIconMenuDialog(this, menuTitle, actions.map { it.first }) { idx ->
            actions.getOrNull(idx)?.second?.invoke()
        }
    }

    private fun showTaskSettingsDialog(targetIds: List<String>) {
        val container = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(52, 30, 52, 16)
        }
        val tvScope = TextView(this).apply {
            text = if (targetIds.size > 1) "修改将作用于选中的 ${targetIds.size} 个任务（并发上限全局生效）"
            else "修改当前选中任务的线程参数与全局队列调度设置"
            textSize = 12f
            setTextColor(ContextCompat.getColor(this@MainActivity, R.color.accent_cyan))
            setPadding(0, 0, 0, 18)
        }
        container.addView(tvScope)

        val tvConcurrentLabel = TextView(this).apply {
            text = "同时下载任务数上限：${AppConfig.maxConcurrentTasks} 个"
            setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_primary))
            textSize = 13f
        }
        var curConcurrent = AppConfig.maxConcurrentTasks
        val sbConcurrent = android.widget.SeekBar(this).apply {
            max = 5
            progress = (curConcurrent - 1).coerceIn(0, 5)
            setOnSeekBarChangeListener(object : android.widget.SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(s: android.widget.SeekBar?, p: Int, f: Boolean) {
                    curConcurrent = p + 1
                    tvConcurrentLabel.text = "同时下载任务数上限：$curConcurrent 个"
                }
                override fun onStartTrackingTouch(s: android.widget.SeekBar?) {}
                override fun onStopTrackingTouch(s: android.widget.SeekBar?) {}
            })
        }
        container.addView(tvConcurrentLabel)
        container.addView(sbConcurrent)

        val tvThreadLabel = TextView(this).apply {
            text = "单任务并发线程数：${AppConfig.threadCount} 线程"
            setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_primary))
            textSize = 13f
            setPadding(0, 16, 0, 0)
        }
        var curThreads = AppConfig.threadCount
        val sbThreads = android.widget.SeekBar(this).apply {
            max = 22
            progress = (curThreads - 2).coerceIn(0, 22)
            setOnSeekBarChangeListener(object : android.widget.SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(s: android.widget.SeekBar?, p: Int, f: Boolean) {
                    curThreads = p + 2
                    tvThreadLabel.text = "单任务并发线程数：$curThreads 线程"
                }
                override fun onStartTrackingTouch(s: android.widget.SeekBar?) {}
                override fun onStopTrackingTouch(s: android.widget.SeekBar?) {}
            })
        }
        container.addView(tvThreadLabel)
        container.addView(sbThreads)

        val cbAutoMp4 = android.widget.CheckBox(this).apply {
            text = "下载完成后自动封装为标准 MP4"
            isChecked = AppConfig.autoConvertMp4
            setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_primary))
        }
        val cbSaveGallery = android.widget.CheckBox(this).apply {
            text = "自动导出到系统存储位置 / 相册 (Download/StarStream)"
            isChecked = AppConfig.saveToGallery
            setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_primary))
        }
        val cbRestart = android.widget.CheckBox(this).apply {
            text = "立即对选中/队列中的任务应用并重建链路"
            isChecked = true
            setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_secondary))
        }
        container.addView(cbAutoMp4)
        container.addView(cbSaveGallery)
        container.addView(cbRestart)

        ThemeManager.dialogBuilder(this)
            .setTitle(if (targetIds.size > 1) "任务设置（已选 ${targetIds.size} 项）" else "任务下载设置")
            .setView(container)
            .setPositiveButton("保存并应用") { _, _ ->
                AppConfig.maxConcurrentTasks = curConcurrent
                AppConfig.threadCount = curThreads
                AppConfig.autoConvertMp4 = cbAutoMp4.isChecked
                AppConfig.saveToGallery = cbSaveGallery.isChecked
                val updated = TaskManager.batchUpdateTasks(this, targetIds, curThreads, cbRestart.isChecked)
                TaskManager.schedulePendingTasks(this)
                if (adapter.selectionMode) adapter.setSelectionMode(false)
                Toast.makeText(this, "设置已应用到 $updated 项任务（并发=$curConcurrent，线程=$curThreads）", Toast.LENGTH_SHORT).show()
            }
            .setNeutralButton("存储目录设置...") { _, _ ->
                startActivity(Intent(this, SettingsActivity::class.java))
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1001)
            }
        }
    }

    private fun checkLastCrashLog() {
        val crashFile = File(filesDir, "last_crash.txt")
        if (!crashFile.exists()) return
        val logText = crashFile.readText().take(2500)
        crashFile.delete()
        if (logText.isBlank()) return
        ThemeManager.dialogBuilder(this)
            .setTitle("上次运行捕获到异常")
            .setMessage(logText)
            .setPositiveButton("确定", null)
            .show()
    }
}

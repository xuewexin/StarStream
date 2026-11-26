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
    private val mainScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var filterMode = 0 // 0=全部, 1=队列中, 2=已完成

    companion object {
        private const val CURRENT_VERSION = "3.2.8"
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

        adapter = DownloadTaskAdapter(
            emptyList(),
            onAction = { task -> handleTaskAction(task) },
            onPreview = { task -> startWatchWhileDownloading(task) },
            onDelete = { task -> promptDeleteTaskDialog(task) },
            onMore = { task -> showTaskMoreMenu(task) }
        )
        rvDownloads.layoutManager = LinearLayoutManager(this)
        rvDownloads.adapter = adapter

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

        OnboardingDialog.showIfNeeded(this, force = false)
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
                    AlertDialog.Builder(this@MainActivity)
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
                    AlertDialog.Builder(this@MainActivity)
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
        AlertDialog.Builder(this)
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
        AlertDialog.Builder(this)
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
        val items = listOf(
            IconMenuItem(R.drawable.ic_refresh, "全部暂停", "暂停当前正在下载与等待队列"),
            IconMenuItem(R.drawable.ic_download, "全部继续", "恢复所有已暂停或失败任务"),
            IconMenuItem(R.drawable.ic_close, "清理已完成记录", "仅移除记录，保留本地文件"),
            IconMenuItem(R.drawable.ic_guide, "新手引导教程", "查看内置浏览器、嗅探与设置说明"),
            IconMenuItem(R.drawable.ic_settings, "下载与存储设置", "并发任务数、多线程、自定义储存路径"),
            IconMenuItem(R.drawable.ic_update, "检查更新与关于", "查看最新版本及作者联系方式")
        )
        showIconMenuDialog(this, "任务与功能管理", items) { which ->
            when (which) {
                0 -> TaskManager.getAllTasks().filter { it.status == TaskStatus.DOWNLOADING || it.status == TaskStatus.WAITING }.forEach { TaskManager.pauseTask(it.id, this) }
                1 -> TaskManager.getAllTasks().filter { it.status == TaskStatus.PAUSED || it.status == TaskStatus.ERROR }.forEach { TaskManager.startTask(this, it.id) }
                2 -> {
                    val done = TaskManager.getAllTasks().filter { it.status == TaskStatus.COMPLETED }
                    done.forEach { TaskManager.deleteTask(it.id, deleteFile = false, context = this) }
                    Toast.makeText(this, "已清理 ${done.size} 条记录", Toast.LENGTH_SHORT).show()
                }
                3 -> OnboardingDialog.showIfNeeded(this, force = true)
                4 -> startActivity(Intent(this, SettingsActivity::class.java))
                5 -> checkForUpdates()
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

    private fun handleTaskAction(t: DownloadTask) {
        when (t.status) {
            TaskStatus.DOWNLOADING, TaskStatus.WAITING, TaskStatus.MUXING -> TaskManager.pauseTask(t.id, this)
            TaskStatus.PAUSED -> TaskManager.startTask(this, t.id)
            TaskStatus.ERROR -> TaskManager.retryTask(this, t.id)
            TaskStatus.COMPLETED -> {
                val f = File(t.outputPath)
                if (!f.exists()) {
                    AlertDialog.Builder(this)
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
        val hasLocal = task.outputPath.isNotBlank() || task.exportedUri.isNotBlank()
        val msg = if (hasLocal) {
            "请选择对「${task.title}」的删除方式：\n· 仅删除记录：保留本地已下载文件\n· 连带删除文件：同时清除本地文件与临时分片"
        } else {
            "确定从下载列表中移除「${task.title}」吗？"
        }
        val builder = AlertDialog.Builder(this)
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
        AlertDialog.Builder(this)
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
        val items = mutableListOf(
            IconMenuItem(R.drawable.ic_info, "重命名任务与文件", "同步修改列表标题与已下载文件名"),
            IconMenuItem(R.drawable.ic_refresh, "刷新令牌并加速下载", "同步最新 Cookie/签名地址并重置限速链路"),
            IconMenuItem(R.drawable.ic_download, "重新尝试下载", "清理残留缓存并重新拉取音视频流"),
            IconMenuItem(R.drawable.ic_close, "删除任务", "可选仅删除记录或连带删除本地文件")
        )
        if (task.mediaType != "file" && task.url.startsWith("http")) {
            items.add(2, IconMenuItem(R.drawable.ic_video, "边下边看 / 在线预览", "使用内置缓冲代理立即播放"))
        }
        showIconMenuDialog(this, task.title, items) { idx ->
            val hasPreview = task.mediaType != "file" && task.url.startsWith("http")
            when {
                idx == 0 -> promptRenameTaskDialog(task)
                idx == 1 -> {
                    Toast.makeText(this, "正在刷新下载令牌并尝试提速...", Toast.LENGTH_SHORT).show()
                    TaskManager.boostTaskToken(this, task.id) { ok ->
                        val msg = if (ok) "令牌刷新成功，已应用极速重连" else "已刷新请求指纹并重连"
                        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
                    }
                }
                hasPreview && idx == 2 -> startWatchWhileDownloading(task)
                (hasPreview && idx == 3) || (!hasPreview && idx == 2) -> {
                    TaskManager.retryTask(this, task.id)
                    Toast.makeText(this, "已开始重新下载：${task.title}", Toast.LENGTH_SHORT).show()
                }
                else -> promptDeleteTaskDialog(task)
            }
        }
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
        AlertDialog.Builder(this)
            .setTitle("上次运行捕获到异常")
            .setMessage(logText)
            .setPositiveButton("确定", null)
            .show()
    }
}

package com.starstream.downloader.core

import android.content.Context
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList

object TaskManager {
    private val tasks = CopyOnWriteArrayList<DownloadTask>()
    private val runners = ConcurrentHashMap<String, DownloadRunner>()
    private val listeners = CopyOnWriteArrayList<() -> Unit>()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    @Volatile
    private var appContext: Context? = null

    @Volatile
    private var initialized = false

    @Volatile
    private var patrolStarted = false

    fun init(context: Context) {
        if (!initialized) {
            synchronized(this) {
                if (!initialized) {
                    appContext = context.applicationContext
                    loadTasksLocked()
                    initialized = true
                }
            }
        }
        startPatrolLoopIfNeeded()
    }

    private fun ensureInit(context: Context?) {
        if (!initialized && context != null) init(context)
    }

    private fun loadTasksLocked() {
        val ctx = appContext ?: return
        val file = File(ctx.filesDir, "tasks_v1.json")
        if (!file.exists()) return
        try {
            val arr = JSONArray(file.readText())
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                val statusStr = o.optString("status", TaskStatus.PAUSED.name)
                var st = try { TaskStatus.valueOf(statusStr) } catch (_: Exception) { TaskStatus.PAUSED }
                val prog = o.optInt("progress", 0)
                var outPath = o.optString("outputPath")
                val hMap = mutableMapOf<String, String>()
                o.optJSONObject("headers")?.let { ho ->
                    val keys = ho.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        hMap[k] = ho.optString(k)
                    }
                }
                val taskObj = DownloadTask(
                    id = o.optString("id"),
                    title = o.optString("title", "未命名任务"),
                    url = o.optString("url"),
                    audioUrl = o.optString("audioUrl"),
                    pageUrl = o.optString("pageUrl"),
                    mediaType = o.optString("mediaType", "video"),
                    resolution = o.optString("resolution"),
                    durationSec = o.optInt("durationSec", 0),
                    subDir = o.optString("subDir"),
                    headers = hMap,
                    status = st,
                    progress = prog,
                    downloadedBytes = o.optLong("downloadedBytes", 0L),
                    totalBytes = o.optLong("totalBytes", 0L),
                    speedText = o.optString("speedText"),
                    outputPath = outPath,
                    exportedUri = o.optString("exportedUri"),
                    errorMsg = o.optString("errorMsg"),
                    threadOverride = o.optInt("threadOverride", 0)
                )

                // 启动自愈核查：若历史任务已达 98%+ 或本地已存在有效输出文件，直接标为已完成
                if (st in listOf(TaskStatus.DOWNLOADING, TaskStatus.WAITING, TaskStatus.MUXING, TaskStatus.PAUSED)) {
                    val found = if (prog >= 98 || outPath.isNotBlank()) findValidCompletedFile(ctx, taskObj) else null
                    if (found != null) {
                        taskObj.status = TaskStatus.COMPLETED
                        taskObj.progress = 100
                        taskObj.outputPath = found.absolutePath
                        taskObj.totalBytes = found.length()
                        taskObj.downloadedBytes = found.length()
                        taskObj.speedText = "完成"
                        cleanupTempDirs(ctx, taskObj.id)
                    } else if (st in listOf(TaskStatus.DOWNLOADING, TaskStatus.WAITING, TaskStatus.MUXING)) {
                        taskObj.status = TaskStatus.PAUSED
                        taskObj.speedText = "已暂停"
                    }
                }
                tasks.add(taskObj)
            }
        } catch (_: Exception) {}
    }

    private fun startPatrolLoopIfNeeded() {
        if (patrolStarted) return
        patrolStarted = true
        scope.launch(Dispatchers.IO) {
            delay(2000)
            while (true) {
                try {
                    val ctx = appContext
                    if (ctx != null) runPatrol(ctx, forceCleanup = true)
                } catch (_: Throwable) {}
                delay(4000)
            }
        }
    }

    private fun isValidOutputFile(f: File): Boolean {
        if (!f.exists() || !f.isFile || f.length() < 4096L) return false
        return !AndroidMediaMuxer.isHtmlOrInvalidFile(f)
    }

    private fun findValidCompletedFile(ctx: Context, task: DownloadTask): File? {
        if (task.outputPath.isNotBlank()) {
            val f = File(task.outputPath)
            if (isValidOutputFile(f)) return f
        }
        val workRoot = File(ctx.getExternalFilesDir(null), "downloads")
        val outDir = if (task.subDir.isNotBlank()) File(workRoot, task.subDir) else workRoot
        if (!outDir.exists()) return null
        val safeName = task.title.replace(Regex("[\\\\/*?:\"<>|]"), "_").trim()
        if (safeName.isBlank()) return null
        val base = safeName.substringBeforeLast('.').ifBlank { safeName }
        val exts = listOf("mp4", "mkv", "ts", "flv", "mov", "webm", "m4a", "mp3", "aac", "pdf", "zip", "rar", "7z", "apk")
        for (ext in exts) {
            val cand = File(outDir, "$base.$ext")
            if (isValidOutputFile(cand)) return cand
        }
        val exact = File(outDir, safeName)
        if (isValidOutputFile(exact)) return exact
        return null
    }

    data class PatrolReport(val fixed: Int, val cleaned: Int, val kicked: Int)

    /**
     * 队列巡检与状态自愈系统：
     * 1. 清理已经退出的僵尸 Runner，防止占用并发槽位；
     * 2. 核查进度 >= 98% 或本地已有完整文件却卡在等待中/下载中的任务并转正为 COMPLETED；
     * 3. 清理已完成或孤儿任务的临时分片目录 (seg_*, dash_*, .parts_*)；
     * 4. 若队列存在空闲并发槽位，自动拉起 waiting 任务。
     */
    @Synchronized
    fun runPatrol(context: Context, forceCleanup: Boolean = true): PatrolReport {
        ensureInit(context)
        val ctx = context.applicationContext
        var fixed = 0
        var cleaned = 0
        var kicked = 0
        var changed = false

        // 1. 清理死亡 Runner
        val deadIds = runners.entries.filter { !it.value.isAlive() }.map { it.key }
        for (id in deadIds) {
            runners.remove(id)
            val t = tasks.find { it.id == id }
            if (t != null && t.status in listOf(TaskStatus.DOWNLOADING, TaskStatus.WAITING, TaskStatus.MUXING)) {
                val found = findValidCompletedFile(ctx, t)
                if (found != null) {
                    promoteTaskCompleted(ctx, t, found)
                    fixed++
                } else {
                    t.status = TaskStatus.WAITING
                    t.speedText = "巡检重新排队..."
                    kicked++
                }
                changed = true
            }
        }

        // 2. 核查卡在 WAITING / DOWNLOADING / MUXING 的已完成或掉线任务
        for (t in tasks) {
            if (t.status == TaskStatus.COMPLETED) {
                if (forceCleanup) cleaned += cleanupTempDirs(ctx, t.id)
                continue
            }
            if (runners.containsKey(t.id)) continue

            val looksDone = t.progress >= 98 ||
                (t.totalBytes > 4096L && t.downloadedBytes >= (t.totalBytes * 0.99).toLong()) ||
                t.outputPath.isNotBlank()
            if (t.status in listOf(TaskStatus.WAITING, TaskStatus.DOWNLOADING, TaskStatus.MUXING) && looksDone) {
                val found = findValidCompletedFile(ctx, t)
                if (found != null) {
                    promoteTaskCompleted(ctx, t, found)
                    fixed++
                    cleaned += cleanupTempDirs(ctx, t.id)
                    changed = true
                    continue
                }
            }

            if (t.status in listOf(TaskStatus.DOWNLOADING, TaskStatus.MUXING) && !runners.containsKey(t.id)) {
                t.status = TaskStatus.WAITING
                t.speedText = "等待队列恢复..."
                kicked++
                changed = true
            }
        }

        // 3. 清理已完成或失效孤儿分片目录
        if (forceCleanup) {
            val nowMs = System.currentTimeMillis()
            ctx.cacheDir.listFiles()?.forEach { f ->
                if (f.isDirectory && (f.name.startsWith("seg_") || f.name.startsWith("dash_"))) {
                    val tid = f.name.substringAfter('_')
                    val owner = tasks.find { it.id == tid }
                    if ((owner == null && nowMs - f.lastModified() > 45_000L) || owner?.status == TaskStatus.COMPLETED) {
                        if (f.deleteRecursively()) cleaned++
                    }
                }
            }
            val dlRoot = File(ctx.getExternalFilesDir(null), "downloads")
            if (dlRoot.exists()) {
                dlRoot.walkTopDown().maxDepth(3).filter { it.isDirectory && it.name.startsWith(".parts_") }.toList().forEach { pf ->
                    val targetName = pf.name.removePrefix(".parts_")
                    val parentOut = File(pf.parentFile, targetName)
                    if (isValidOutputFile(parentOut) || (nowMs - pf.lastModified() > 120_000L && runners.isEmpty())) {
                        if (pf.deleteRecursively()) cleaned++
                    }
                }
            }
        }

        if (changed) notifyChanged()
        schedulePendingTasks(ctx)
        return PatrolReport(fixed, cleaned, kicked)
    }

    private fun promoteTaskCompleted(ctx: Context, task: DownloadTask, outFile: File) {
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.outputPath = outFile.absolutePath
        task.totalBytes = outFile.length()
        task.downloadedBytes = outFile.length()
        task.speedText = "完成"
        if (task.exportedUri.isBlank() && (AppConfig.saveToGallery || AppConfig.customSaveUri.isNotBlank())) {
            try {
                task.exportedUri = AndroidMediaMuxer.exportToPublicDownloads(ctx, outFile, task.subDir)
            } catch (_: Throwable) {}
        }
        cleanupTempDirs(ctx, task.id)
    }

    private fun saveTasksAsync() {
        val ctx = appContext ?: return
        val snapshot = tasks.take(200)
        scope.launch(Dispatchers.IO) {
            try {
                val arr = JSONArray()
                snapshot.forEach { t ->
                    arr.put(JSONObject().apply {
                        put("id", t.id)
                        put("title", t.title)
                        put("url", t.url)
                        put("audioUrl", t.audioUrl)
                        put("pageUrl", t.pageUrl)
                        put("mediaType", t.mediaType)
                        put("resolution", t.resolution)
                        put("durationSec", t.durationSec)
                        put("subDir", t.subDir)
                        put("headers", JSONObject(t.headers as Map<*, *>))
                        put("status", t.status.name)
                        put("progress", t.progress)
                        put("downloadedBytes", t.downloadedBytes)
                        put("totalBytes", t.totalBytes)
                        put("speedText", t.speedText)
                        put("outputPath", t.outputPath)
                        put("exportedUri", t.exportedUri)
                        put("errorMsg", t.errorMsg)
                        put("threadOverride", t.threadOverride)
                    })
                }
                File(ctx.filesDir, "tasks_v1.json").writeText(arr.toString())
            } catch (_: Exception) {}
        }
    }

    fun addListener(cb: () -> Unit) {
        if (!listeners.contains(cb)) listeners.add(cb)
    }

    fun removeListener(cb: () -> Unit) {
        listeners.remove(cb)
    }

    private fun notifyChanged(persist: Boolean = true) {
        if (persist) saveTasksAsync()
        scope.launch {
            listeners.forEach { it() }
        }
    }

    fun getAllTasks(): List<DownloadTask> = tasks.toList()

    fun addTask(context: Context, task: DownloadTask, autoStart: Boolean = true): DownloadTask {
        ensureInit(context)
        tasks.add(0, task)
        notifyChanged()
        if (autoStart) startTask(context, task.id)
        return task
    }

    fun addFromSniffed(context: Context, m: SniffedMedia, subDir: String = ""): DownloadTask {
        val t = DownloadTask(
            id = UUID.randomUUID().toString().take(8),
            title = m.title,
            url = m.url,
            audioUrl = m.audioUrl,
            pageUrl = m.pageUrl,
            mediaType = if (m.audioUrl.isNotBlank()) (if (m.mediaType == "bili_dash") "bili_dash" else "dual_dash") else m.mediaType,
            resolution = m.resolution,
            durationSec = m.durationSec,
            subDir = subDir,
            headers = HashMap(m.headers)
        )
        return addTask(context, t, autoStart = true)
    }

    @Synchronized
    fun schedulePendingTasks(context: Context) {
        ensureInit(context)
        val ctx = context.applicationContext
        val limit = AppConfig.maxConcurrentTasks
        for (t in tasks) {
            if (runners.size >= limit) break
            if (t.status == TaskStatus.WAITING && !runners.containsKey(t.id)) {
                if (t.progress >= 98 || t.outputPath.isNotBlank()) {
                    val found = findValidCompletedFile(ctx, t)
                    if (found != null) {
                        promoteTaskCompleted(ctx, t, found)
                        continue
                    }
                }
                launchRunner(ctx, t)
            }
        }
    }

    fun batchUpdateTasks(context: Context, taskIds: Collection<String>, threadOverride: Int?, restartActive: Boolean): Int {
        ensureInit(context)
        val ctx = context.applicationContext
        var cnt = 0
        val toRestart = mutableListOf<String>()
        for (t in tasks) {
            if (t.id !in taskIds) continue
            if (threadOverride != null) {
                t.threadOverride = threadOverride
            }
            cnt++
            if (restartActive && t.status in listOf(TaskStatus.DOWNLOADING, TaskStatus.WAITING, TaskStatus.PAUSED, TaskStatus.ERROR)) {
                toRestart.add(t.id)
            }
        }
        notifyChanged()
        if (restartActive) {
            toRestart.forEach { id ->
                runners.remove(id)?.cancel()
                val obj = tasks.find { it.id == id }
                if (obj != null && obj.status != TaskStatus.COMPLETED) {
                    obj.status = TaskStatus.WAITING
                }
            }
            schedulePendingTasks(ctx)
        }
        return cnt
    }

    private fun launchRunner(appCtx: Context, task: DownloadTask) {
        if (runners.containsKey(task.id)) return
        val runner = DownloadRunner(appCtx, task) {
            notifyChanged(persist = false)
        }
        runners[task.id] = runner
        runner.start(scope) { _, _ ->
            runners.remove(task.id)
            notifyChanged(persist = true)
            schedulePendingTasks(appCtx)
        }
    }

    fun startTask(context: Context, taskId: String) {
        ensureInit(context)
        val task = tasks.find { it.id == taskId } ?: return
        if (task.status == TaskStatus.DOWNLOADING || task.status == TaskStatus.MUXING) return
        runners.remove(taskId)?.cancel()

        val appCtx = context.applicationContext
        if (runners.size >= AppConfig.maxConcurrentTasks) {
            task.status = TaskStatus.WAITING
            task.speedText = "排队等待 (上限 ${AppConfig.maxConcurrentTasks})"
            notifyChanged()
            return
        }
        launchRunner(appCtx, task)
    }

    fun pauseTask(taskId: String, context: Context? = null) {
        ensureInit(context)
        runners.remove(taskId)?.cancel()
        tasks.find { it.id == taskId }?.let {
            if (it.status == TaskStatus.DOWNLOADING || it.status == TaskStatus.WAITING) {
                it.status = TaskStatus.PAUSED
                it.speedText = "已暂停"
                notifyChanged()
            }
        }
        if (context != null) schedulePendingTasks(context)
    }

    /**
     * 重新尝试下载（清除旧失败/残缺缓存，自动刷新源站令牌并重新入队下载）
     */
    fun retryTask(context: Context, taskId: String) {
        ensureInit(context)
        val task = tasks.find { it.id == taskId } ?: return
        runners.remove(taskId)?.cancel()
        cleanupTempDirs(context.applicationContext, taskId)
        task.status = TaskStatus.WAITING
        task.progress = 0
        task.downloadedBytes = 0L
        task.errorMsg = ""
        task.speedText = "正在刷新令牌并重试..."
        notifyChanged()

        val appCtx = context.applicationContext
        scope.launch(Dispatchers.IO) {
            CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
            withContext(Dispatchers.Main) {
                if (runners.size >= AppConfig.maxConcurrentTasks) {
                    task.status = TaskStatus.WAITING
                    task.speedText = "排队等待 (上限 ${AppConfig.maxConcurrentTasks})"
                    notifyChanged()
                } else {
                    launchRunner(appCtx, task)
                }
            }
        }
    }

    /**
     * 下载列表重命名（同步重命名任务标题与本地/已导出文件）
     */
    fun renameTask(context: Context, taskId: String, newTitle: String): Boolean {
        ensureInit(context)
        val cleanTitle = newTitle.trim()
        if (cleanTitle.isEmpty()) return false
        val task = tasks.find { it.id == taskId } ?: return false
        task.title = cleanTitle

        val safeBase = cleanTitle.replace(Regex("[\\\\/*?:\"<>|]"), "_").trim()
        if (safeBase.isNotEmpty() && task.outputPath.isNotBlank()) {
            val oldFile = File(task.outputPath)
            if (oldFile.exists()) {
                val ext = oldFile.extension.ifBlank { "mp4" }
                val newNameWithExt = "$safeBase.$ext"
                val newFile = File(oldFile.parentFile, newNameWithExt)
                if (oldFile.renameTo(newFile)) {
                    task.outputPath = newFile.absolutePath
                }
                if (task.exportedUri.isNotBlank()) {
                    task.exportedUri = AndroidMediaMuxer.renameExportedFile(context, task.exportedUri, newNameWithExt)
                }
            }
        }
        notifyChanged()
        return true
    }

    /**
     * 刷新全部未完成/队列/失败任务的下载令牌，并对正在下载的任务触发主动重建链路提速
     */
    suspend fun refreshAllTaskTokens(context: Context): Int = withContext(Dispatchers.IO) {
        ensureInit(context)
        val targets = tasks.filter { it.status != TaskStatus.COMPLETED && it.url.startsWith("http") }
        var count = 0
        for (t in targets) {
            try {
                CredentialRefresher.refreshTaskCredentials(t, rotateUa = true)
                runners[t.id]?.requestTokenBoost()
                if (t.status == TaskStatus.ERROR) {
                    t.errorMsg = ""
                    t.speedText = "令牌已刷新，点击重试可继续"
                } else if (t.status == TaskStatus.PAUSED || t.status == TaskStatus.WAITING) {
                    t.speedText = "令牌已刷新"
                }
                count++
            } catch (_: Exception) {}
        }
        notifyChanged()
        runPatrol(context, forceCleanup = true)
        count
    }

    fun boostTaskToken(context: Context, taskId: String, onDone: (Boolean) -> Unit) {
        ensureInit(context)
        val task = tasks.find { it.id == taskId } ?: return
        scope.launch(Dispatchers.IO) {
            val ok = CredentialRefresher.refreshTaskCredentials(task, rotateUa = true)
            runners[taskId]?.requestTokenBoost()
            notifyChanged()
            withContext(Dispatchers.Main) {
                if (task.status == TaskStatus.PAUSED || task.status == TaskStatus.ERROR) {
                    startTask(context, taskId)
                }
                onDone(ok)
            }
        }
    }

    fun deleteTask(taskId: String, deleteFile: Boolean = false, context: Context? = null) {
        ensureInit(context)
        runners.remove(taskId)?.cancel()
        val task = tasks.find { it.id == taskId } ?: return
        val ctx = context?.applicationContext ?: appContext
        if (deleteFile) {
            if (task.outputPath.isNotBlank()) {
                try { File(task.outputPath).delete() } catch (_: Exception) {}
            }
            if (task.exportedUri.isNotBlank() && ctx != null) {
                AndroidMediaMuxer.deleteExportedFile(ctx, task.exportedUri)
            }
        }
        if (ctx != null) cleanupTempDirs(ctx, taskId)
        tasks.remove(task)
        notifyChanged()
        if (ctx != null) schedulePendingTasks(ctx)
    }

    private fun cleanupTempDirs(appCtx: Context, taskId: String): Int {
        var count = 0
        try {
            val seg = File(appCtx.cacheDir, "seg_$taskId")
            if (seg.exists() && seg.deleteRecursively()) count++
        } catch (_: Exception) {}
        try {
            val dash = File(appCtx.cacheDir, "dash_$taskId")
            if (dash.exists() && dash.deleteRecursively()) count++
        } catch (_: Exception) {}
        return count
    }
}

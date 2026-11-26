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

    fun init(context: Context) {
        if (initialized) return
        synchronized(this) {
            if (initialized) return
            appContext = context.applicationContext
            loadTasksLocked()
            initialized = true
        }
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
                if (st == TaskStatus.DOWNLOADING || st == TaskStatus.WAITING || st == TaskStatus.MUXING) {
                    st = TaskStatus.PAUSED
                }
                val hMap = mutableMapOf<String, String>()
                o.optJSONObject("headers")?.let { ho ->
                    val keys = ho.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        hMap[k] = ho.optString(k)
                    }
                }
                tasks.add(
                    DownloadTask(
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
                        progress = o.optInt("progress", 0),
                        downloadedBytes = o.optLong("downloadedBytes", 0L),
                        totalBytes = o.optLong("totalBytes", 0L),
                        speedText = if (st == TaskStatus.PAUSED) "已暂停" else o.optString("speedText"),
                        outputPath = o.optString("outputPath"),
                        exportedUri = o.optString("exportedUri"),
                        errorMsg = o.optString("errorMsg")
                    )
                )
            }
        } catch (_: Exception) {}
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
        val limit = AppConfig.maxConcurrentTasks
        for (t in tasks) {
            if (runners.size >= limit) break
            if (t.status == TaskStatus.WAITING && !runners.containsKey(t.id)) {
                launchRunner(context.applicationContext, t)
            }
        }
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

    private fun cleanupTempDirs(appCtx: Context, taskId: String) {
        try { File(appCtx.cacheDir, "seg_$taskId").deleteRecursively() } catch (_: Exception) {}
        try { File(appCtx.cacheDir, "dash_$taskId").deleteRecursively() } catch (_: Exception) {}
    }
}

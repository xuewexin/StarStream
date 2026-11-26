package com.starstream.downloader.core

import android.content.Context
import kotlinx.coroutines.*
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList

object TaskManager {
    private val tasks = CopyOnWriteArrayList<DownloadTask>()
    private val runners = ConcurrentHashMap<String, DownloadRunner>()
    private val listeners = CopyOnWriteArrayList<() -> Unit>()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    fun addListener(cb: () -> Unit) {
        if (!listeners.contains(cb)) listeners.add(cb)
    }

    fun removeListener(cb: () -> Unit) {
        listeners.remove(cb)
    }

    private fun notifyChanged() {
        scope.launch {
            listeners.forEach { it() }
        }
    }

    fun getAllTasks(): List<DownloadTask> = tasks.toList()

    fun addTask(context: Context, task: DownloadTask, autoStart: Boolean = true): DownloadTask {
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
            mediaType = if (m.audioUrl.isNotBlank()) "bili_dash" else m.mediaType,
            resolution = m.resolution,
            durationSec = m.durationSec,
            subDir = subDir,
            headers = HashMap(m.headers)
        )
        return addTask(context, t, autoStart = true)
    }

    @Synchronized
    fun schedulePendingTasks(context: Context) {
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
            notifyChanged()
        }
        runners[task.id] = runner
        runner.start(scope) { _, _ ->
            runners.remove(task.id)
            notifyChanged()
            schedulePendingTasks(appCtx)
        }
    }

    fun startTask(context: Context, taskId: String) {
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

    fun deleteTask(taskId: String, deleteFile: Boolean = false, context: Context? = null) {
        runners.remove(taskId)?.cancel()
        val task = tasks.find { it.id == taskId } ?: return
        if (deleteFile && task.outputPath.isNotBlank()) {
            try { File(task.outputPath).delete() } catch (_: Exception) {}
        }
        tasks.remove(task)
        notifyChanged()
        if (context != null) schedulePendingTasks(context)
    }
}

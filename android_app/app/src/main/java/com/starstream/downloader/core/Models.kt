package com.starstream.downloader.core

import android.content.Context
import android.content.SharedPreferences

enum class TaskStatus {
    WAITING, DOWNLOADING, MUXING, COMPLETED, PAUSED, ERROR
}

data class DownloadTask(
    val id: String,
    var title: String,
    var url: String,
    var audioUrl: String = "",
    var pageUrl: String = "",
    var mediaType: String = "video", // m3u8, video, audio, bili_dash, file
    var resolution: String = "",
    var durationSec: Int = 0,
    var subDir: String = "",
    var headers: MutableMap<String, String> = mutableMapOf(),
    var status: TaskStatus = TaskStatus.WAITING,
    var progress: Int = 0,
    var downloadedBytes: Long = 0L,
    var totalBytes: Long = 0L,
    var speedText: String = "",
    var outputPath: String = "",
    var exportedUri: String = "",
    var errorMsg: String = "",
    var logSummary: String = ""
)

data class SniffedMedia(
    val id: String,
    var title: String,
    val url: String,
    var audioUrl: String = "",
    var mediaType: String = "video",
    var resolution: String = "",
    var durationSec: Int = 0,
    var contentLength: Long = 0L,
    var fileExt: String = "",
    var codecHint: String = "",
    val pageUrl: String = "",
    val headers: MutableMap<String, String> = mutableMapOf(),
    val timestamp: Long = System.currentTimeMillis()
)

data class SeriesEpisode(
    val index: Int,
    val title: String,
    val pageUrl: String,
    val durationSec: Int = 0,
    val bvid: String = "",
    val cid: Long = 0L,
    val epId: Long = 0L,
    val isPgc: Boolean = false,
    val audioSid: Long = 0L,
    val mediaType: String = "video",
    var selected: Boolean = true
)

data class SeriesInfo(
    val seriesTitle: String,
    val seriesType: String,
    val total: Int,
    val currentIndex: Int = 0,
    val pageUrl: String = "",
    val episodes: List<SeriesEpisode> = emptyList()
)

data class ParseResult(
    val success: Boolean,
    val title: String = "",
    val url: String = "",
    val audioUrl: String = "",
    val mediaType: String = "video",
    val durationSec: Int = 0,
    val resolution: String = "",
    val coverUrl: String = "",
    val headers: MutableMap<String, String> = mutableMapOf(),
    val series: SeriesInfo? = null,
    val error: String = ""
)

object AppConfig {
    private const val PREF_NAME = "starstream_prefs"
    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        if (!::prefs.isInitialized) {
            prefs = context.applicationContext.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        }
    }

    var hasSeenGuide: Boolean
        get() = prefs.getBoolean("has_seen_guide_v327", false)
        set(v) = prefs.edit().putBoolean("has_seen_guide_v327", v).apply()

    var threadCount: Int
        get() = prefs.getInt("thread_count", 8).coerceIn(2, 24)
        set(v) = prefs.edit().putInt("thread_count", v.coerceIn(2, 24)).apply()

    var maxConcurrentTasks: Int
        get() = prefs.getInt("max_concurrent_tasks", 2).coerceIn(1, 6)
        set(v) = prefs.edit().putInt("max_concurrent_tasks", v.coerceIn(1, 6)).apply()

    var customSaveUri: String
        get() = prefs.getString("custom_save_uri", "") ?: ""
        set(v) = prefs.edit().putString("custom_save_uri", v.trim()).apply()

    var customSaveLabel: String
        get() = prefs.getString("custom_save_label", "") ?: ""
        set(v) = prefs.edit().putString("custom_save_label", v.trim()).apply()

    var bookmarksExpanded: Boolean
        get() = prefs.getBoolean("bookmarks_expanded", true)
        set(v) = prefs.edit().putBoolean("bookmarks_expanded", v).apply()

    var historyExpanded: Boolean
        get() = prefs.getBoolean("history_expanded", true)
        set(v) = prefs.edit().putBoolean("history_expanded", v).apply()

    var uaBuildSeed: Int
        get() = prefs.getInt("ua_build_seed", 0)
        set(v) = prefs.edit().putInt("ua_build_seed", v).apply()

    var autoConvertMp4: Boolean
        get() = prefs.getBoolean("auto_convert_mp4", true)
        set(v) = prefs.edit().putBoolean("auto_convert_mp4", v).apply()

    var saveToGallery: Boolean
        get() = prefs.getBoolean("save_to_gallery", true)
        set(v) = prefs.edit().putBoolean("save_to_gallery", v).apply()

    var proxyHost: String
        get() = prefs.getString("proxy_host", "") ?: ""
        set(v) = prefs.edit().putString("proxy_host", v.trim()).apply()

    var proxyPort: Int
        get() = prefs.getInt("proxy_port", 7890)
        set(v) = prefs.edit().putInt("proxy_port", v).apply()

    var useProxy: Boolean
        get() = prefs.getBoolean("use_proxy", false)
        set(v) = prefs.edit().putBoolean("use_proxy", v).apply()

    var homeUrl: String
        get() = prefs.getString("home_url", "") ?: ""
        set(v) = prefs.edit().putString("home_url", v.trim()).apply()

    var searchEngine: String
        get() = prefs.getString("search_engine", "baidu") ?: "baidu"
        set(v) = prefs.edit().putString("search_engine", v).apply()

    var uaProfile: String
        get() = prefs.getString("ua_profile", "chrome_pc") ?: "chrome_pc"
        set(v) = prefs.edit().putString("ua_profile", v).apply()

    var adBlockEnabled: Boolean
        get() = prefs.getBoolean("ad_block_enabled", true)
        set(v) = prefs.edit().putBoolean("ad_block_enabled", v).apply()

    var sniffVideo: Boolean
        get() = prefs.getBoolean("sniff_video", true)
        set(v) = prefs.edit().putBoolean("sniff_video", v).apply()

    var sniffAudio: Boolean
        get() = prefs.getBoolean("sniff_audio", true)
        set(v) = prefs.edit().putBoolean("sniff_audio", v).apply()

    var sniffDocs: Boolean
        get() = prefs.getBoolean("sniff_docs", true)
        set(v) = prefs.edit().putBoolean("sniff_docs", v).apply()

    private val defaultSniffExtensions = listOf(
        "mp4", "m3u8", "mpd", "flv", "mkv", "webm", "mov", "avi", "m4s",
        "mp3", "m4a", "aac", "flac", "wav", "ogg", "opus",
        "pdf", "zip", "rar", "7z", "apk", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "epub", "iso"
    )

    fun getSniffExtensions(): MutableList<String> {
        val raw = prefs.getString("sniff_extensions_json", null)
        if (raw.isNullOrBlank()) {
            return defaultSniffExtensions.toMutableList()
        }
        val list = mutableListOf<String>()
        try {
            val arr = org.json.JSONArray(raw)
            for (i in 0 until arr.length()) {
                val ext = arr.optString(i).trim().lowercase().trimStart('.')
                if (ext.isNotEmpty() && !list.contains(ext)) list.add(ext)
            }
        } catch (_: Exception) {}
        return list
    }

    fun saveSniffExtensions(exts: List<String>) {
        val clean = exts.map { it.trim().lowercase().trimStart('.') }.filter { it.isNotEmpty() }.distinct()
        val arr = org.json.JSONArray()
        clean.forEach { arr.put(it) }
        prefs.edit().putString("sniff_extensions_json", arr.toString()).apply()
    }

    fun addSniffExtensions(rawInput: String): Int {
        val current = getSniffExtensions()
        val tokens = rawInput.split(Regex("[,，\\s;；|]+"))
            .map { it.trim().lowercase().trimStart('.') }
            .filter { it.matches(Regex("[a-z0-9]{1,12}")) }
        var added = 0
        for (t in tokens) {
            if (!current.contains(t)) {
                current.add(t)
                added++
            }
        }
        if (added > 0) saveSniffExtensions(current)
        return added
    }

    fun removeSniffExtension(ext: String) {
        val clean = ext.trim().lowercase().trimStart('.')
        val current = getSniffExtensions()
        if (current.removeAll { it == clean }) {
            saveSniffExtensions(current)
        }
    }

    fun resetSniffExtensions() {
        saveSniffExtensions(defaultSniffExtensions)
    }

    fun getUserAgentString(): String {
        val patch = 110 + (uaBuildSeed % 89)
        val chromeVer = "126.0.6478.$patch"
        return when (uaProfile) {
            "chrome_mobile" -> "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/$chromeVer Mobile Safari/537.36"
            "edge_pc" -> "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/$chromeVer Safari/537.36 Edg/126.0.2592.$patch"
            "safari_ios" -> "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.${5 + (uaBuildSeed % 2)} Mobile/15E148 Safari/604.1"
            "firefox_pc" -> "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:${128 + (uaBuildSeed % 3)}.0) Gecko/20100101 Firefox/${128 + (uaBuildSeed % 3)}.0"
            else -> "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/$chromeVer Safari/537.36"
        }
    }

    fun rotateIdentity(): String {
        uaBuildSeed += 1
        return getUserAgentString()
    }

    fun getUaLabel(): String {
        return when (uaProfile) {
            "chrome_mobile" -> "Chrome 手机"
            "edge_pc" -> "Edge 桌面"
            "safari_ios" -> "Safari iOS"
            "firefox_pc" -> "Firefox 桌面"
            else -> "Chrome 桌面"
        }
    }

    fun buildSearchUrl(query: String): String {
        val q = android.net.Uri.encode(query.trim())
        return when (searchEngine) {
            "google" -> "https://www.google.com/search?q=$q"
            "bing" -> "https://www.bing.com/search?q=$q"
            "duckduckgo" -> "https://duckduckgo.com/?q=$q"
            "yandex" -> "https://yandex.com/search/?text=$q"
            else -> "https://www.baidu.com/s?wd=$q"
        }
    }

    fun getSearchEngineLabel(): String {
        return when (searchEngine) {
            "google" -> "Google"
            "bing" -> "Bing"
            "duckduckgo" -> "DuckDuckGo"
            "yandex" -> "Yandex"
            else -> "百度"
        }
    }

    // ---------- 浏览器收藏文件夹与书签持久化 ----------
    data class BookmarkEntry(val title: String, val url: String, val folder: String = "默认收藏")

    fun getBookmarkFolders(): MutableList<String> {
        val raw = prefs.getString("bookmark_folders_json", "[]") ?: "[]"
        val folders = mutableListOf<String>()
        try {
            val arr = org.json.JSONArray(raw)
            for (i in 0 until arr.length()) {
                val f = arr.optString(i).trim()
                if (f.isNotEmpty() && !folders.contains(f)) folders.add(f)
            }
        } catch (_: Exception) {}
        if (!folders.contains("默认收藏")) folders.add(0, "默认收藏")
        // Ensure any folders referenced by existing bookmarks are also present
        getBookmarks().forEach { b ->
            if (b.folder.isNotBlank() && !folders.contains(b.folder)) folders.add(b.folder)
        }
        return folders
    }

    private fun saveBookmarkFolders(folders: List<String>) {
        val clean = folders.map { it.trim() }.filter { it.isNotEmpty() }.distinct().toMutableList()
        if (!clean.contains("默认收藏")) clean.add(0, "默认收藏")
        val arr = org.json.JSONArray()
        clean.forEach { arr.put(it) }
        prefs.edit().putString("bookmark_folders_json", arr.toString()).apply()
    }

    fun createBookmarkFolder(name: String): Boolean {
        val clean = name.trim()
        if (clean.isEmpty()) return false
        val folders = getBookmarkFolders()
        if (folders.contains(clean)) return false
        folders.add(clean)
        saveBookmarkFolders(folders)
        return true
    }

    fun deleteBookmarkFolder(name: String) {
        val clean = name.trim()
        if (clean.isEmpty() || clean == "默认收藏") return
        val folders = getBookmarkFolders().filter { it != clean }
        saveBookmarkFolders(folders)
        val bms = getBookmarks().map {
            if (it.folder == clean) it.copy(folder = "默认收藏") else it
        }
        saveBookmarks(bms)
    }

    fun getBookmarks(): MutableList<BookmarkEntry> {
        val raw = prefs.getString("bookmarks_json", "[]") ?: "[]"
        val list = mutableListOf<BookmarkEntry>()
        try {
            val arr = org.json.JSONArray(raw)
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val t = obj.optString("title")
                val u = obj.optString("url")
                val f = obj.optString("folder", "默认收藏").ifBlank { "默认收藏" }
                if (u.startsWith("http")) list.add(BookmarkEntry(t.ifBlank { u }, u, f))
            }
        } catch (_: Exception) {}
        return list
    }

    private fun saveBookmarks(list: List<BookmarkEntry>) {
        val arr = org.json.JSONArray()
        list.forEach { b ->
            arr.put(org.json.JSONObject().apply {
                put("title", b.title)
                put("url", b.url)
                put("folder", b.folder.ifBlank { "默认收藏" })
            })
        }
        prefs.edit().putString("bookmarks_json", arr.toString()).apply()
    }

    fun isBookmarked(url: String): Boolean {
        val clean = url.trim()
        return getBookmarks().any { it.url == clean }
    }

    fun addBookmarkToFolder(title: String, url: String, folder: String) {
        val clean = url.trim()
        if (!clean.startsWith("http")) return
        val targetFolder = folder.trim().ifBlank { "默认收藏" }
        createBookmarkFolder(targetFolder)
        val list = getBookmarks()
        list.removeAll { it.url == clean }
        list.add(0, BookmarkEntry(title.ifBlank { clean }, clean, targetFolder))
        saveBookmarks(list)
    }

    fun toggleBookmark(title: String, url: String, folder: String = "默认收藏"): Boolean {
        val clean = url.trim()
        if (!clean.startsWith("http")) return false
        val list = getBookmarks()
        val idx = list.indexOfFirst { it.url == clean }
        return if (idx >= 0) {
            list.removeAt(idx)
            saveBookmarks(list)
            false
        } else {
            addBookmarkToFolder(title, clean, folder)
            true
        }
    }

    fun removeBookmark(url: String) {
        val list = getBookmarks()
        list.removeAll { it.url == url }
        saveBookmarks(list)
    }

    // ---------- 浏览器访问历史记录持久化 ----------
    data class HistoryEntry(val title: String, val url: String, val timestamp: Long)

    fun getHistory(): MutableList<HistoryEntry> {
        val raw = prefs.getString("browser_history_json", "[]") ?: "[]"
        val list = mutableListOf<HistoryEntry>()
        try {
            val arr = org.json.JSONArray(raw)
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                val u = o.optString("url")
                if (u.startsWith("http")) {
                    list.add(
                        HistoryEntry(
                            title = o.optString("title").ifBlank { u },
                            url = u,
                            timestamp = o.optLong("ts", System.currentTimeMillis())
                        )
                    )
                }
            }
        } catch (_: Exception) {}
        return list
    }

    private fun saveHistory(list: List<HistoryEntry>) {
        val arr = org.json.JSONArray()
        list.take(200).forEach { e ->
            arr.put(org.json.JSONObject().apply {
                put("title", e.title)
                put("url", e.url)
                put("ts", e.timestamp)
            })
        }
        prefs.edit().putString("browser_history_json", arr.toString()).apply()
    }

    fun recordHistory(title: String, url: String) {
        val clean = url.trim()
        if (!clean.startsWith("http")) return
        val list = getHistory()
        // Deduplicate consecutive or existing same URL cleanly so latest visit stays at top
        list.removeAll { it.url == clean }
        list.add(0, HistoryEntry(title.ifBlank { clean }, clean, System.currentTimeMillis()))
        saveHistory(list)
    }

    fun deleteHistoryItem(url: String) {
        val list = getHistory()
        list.removeAll { it.url == url }
        saveHistory(list)
    }

    fun clearHistory() {
        prefs.edit().putString("browser_history_json", "[]").apply()
    }

    // ---------- 浏览器打开标签页与当前页面持久化 ----------
    data class SavedTabState(
        val id: String,
        val currentUrl: String,
        val currentTitle: String,
        val isStartPage: Boolean
    )

    var savedActiveTabIndex: Int
        get() = prefs.getInt("saved_active_tab_index", 0)
        set(v) = prefs.edit().putInt("saved_active_tab_index", v).apply()

    fun saveTabsState(tabs: List<SavedTabState>, activeIdx: Int) {
        val arr = org.json.JSONArray()
        tabs.take(30).forEach { t ->
            arr.put(org.json.JSONObject().apply {
                put("id", t.id)
                put("url", t.currentUrl)
                put("title", t.currentTitle)
                put("isStartPage", t.isStartPage)
            })
        }
        prefs.edit()
            .putString("saved_browser_tabs_json", arr.toString())
            .putInt("saved_active_tab_index", activeIdx)
            .apply()
    }

    fun getSavedTabs(): List<SavedTabState> {
        val raw = prefs.getString("saved_browser_tabs_json", "[]") ?: "[]"
        val list = mutableListOf<SavedTabState>()
        try {
            val arr = org.json.JSONArray(raw)
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                val url = o.optString("url", "")
                val isStart = o.optBoolean("isStartPage", !url.startsWith("http"))
                list.add(
                    SavedTabState(
                        id = o.optString("id").ifBlank { java.util.UUID.randomUUID().toString().take(8) },
                        currentUrl = url,
                        currentTitle = o.optString("title", if (isStart) "极简起始页" else url),
                        isStartPage = isStart
                    )
                )
            }
        } catch (_: Exception) {}
        return list
    }
}

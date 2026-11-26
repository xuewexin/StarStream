package com.starstream.downloader.ui

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.documentfile.provider.DocumentFile
import com.starstream.downloader.R
import com.starstream.downloader.core.AppConfig

class SettingsActivity : AppCompatActivity() {

    private val uaOptions = listOf(
        "chrome_pc" to "Chrome 桌面",
        "chrome_mobile" to "Chrome 手机",
        "edge_pc" to "Edge 桌面",
        "safari_ios" to "Safari iOS",
        "firefox_pc" to "Firefox 桌面"
    )

    private val engineOptions = listOf(
        "baidu" to "百度",
        "google" to "Google",
        "bing" to "Bing",
        "duckduckgo" to "DuckDuckGo",
        "yandex" to "Yandex"
    )

    private lateinit var tvStoragePath: TextView

    private val pickFolderLauncher = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            try {
                contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                )
            } catch (_: Exception) {}
            val doc = DocumentFile.fromTreeUri(this, uri)
            val label = doc?.name?.takeIf { it.isNotBlank() } ?: uri.lastPathSegment ?: "已选自定义目录"
            AppConfig.customSaveUri = uri.toString()
            AppConfig.customSaveLabel = label
            tvStoragePath.text = "自定义目录：$label"
            Toast.makeText(this, "已选定存储目录：$label", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AppConfig.init(this)
        setContentView(R.layout.activity_settings)

        val root = findViewById<View>(R.id.root_settings_container)
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, windowInsets ->
            val insets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(insets.left, insets.top, insets.right, insets.bottom)
            windowInsets
        }

        findViewById<View>(R.id.btn_settings_back).setOnClickListener { finish() }

        val tvUa = findViewById<TextView>(R.id.tv_setting_ua)
        val tvEngine = findViewById<TextView>(R.id.tv_setting_engine)
        val swAdBlock = findViewById<Switch>(R.id.sw_ad_block)

        val swSniffVideo = findViewById<Switch>(R.id.sw_sniff_video)
        val swSniffAudio = findViewById<Switch>(R.id.sw_sniff_audio)
        val swSniffDocs = findViewById<Switch>(R.id.sw_sniff_docs)

        val swAutoMp4 = findViewById<Switch>(R.id.sw_auto_mp4)
        val swGallery = findViewById<Switch>(R.id.sw_save_gallery)
        tvStoragePath = findViewById(R.id.tv_storage_path)
        val tvConcurrent = findViewById<TextView>(R.id.tv_concurrent_label)
        val sbConcurrent = findViewById<SeekBar>(R.id.sb_concurrent)
        val tvThreads = findViewById<TextView>(R.id.tv_threads_label)
        val sbThreads = findViewById<SeekBar>(R.id.sb_threads)
        val swProxy = findViewById<Switch>(R.id.sw_use_proxy)
        val etHost = findViewById<EditText>(R.id.et_proxy_host)
        val etPort = findViewById<EditText>(R.id.et_proxy_port)

        var selectedUa = AppConfig.uaProfile
        var selectedEngine = AppConfig.searchEngine
        tvUa.text = AppConfig.getUaLabel()
        tvEngine.text = AppConfig.getSearchEngineLabel()
        tvStoragePath.text = if (AppConfig.customSaveUri.isNotBlank()) {
            "自定义目录：${AppConfig.customSaveLabel.ifBlank { "已选目录" }}"
        } else {
            "默认 (相册 Movies / 系统 Downloads)"
        }

        findViewById<View>(R.id.row_pick_ua).setOnClickListener {
            val names = uaOptions.map { it.second }.toTypedArray()
            val cur = uaOptions.indexOfFirst { it.first == selectedUa }.coerceAtLeast(0)
            AlertDialog.Builder(this)
                .setTitle("默认内置浏览器内核")
                .setSingleChoiceItems(names, cur) { dlg, w ->
                    selectedUa = uaOptions[w].first
                    tvUa.text = uaOptions[w].second
                    dlg.dismiss()
                }
                .show()
        }

        findViewById<View>(R.id.row_pick_engine).setOnClickListener {
            val names = engineOptions.map { it.second }.toTypedArray()
            val cur = engineOptions.indexOfFirst { it.first == selectedEngine }.coerceAtLeast(0)
            AlertDialog.Builder(this)
                .setTitle("默认搜索引擎")
                .setSingleChoiceItems(names, cur) { dlg, w ->
                    selectedEngine = engineOptions[w].first
                    tvEngine.text = engineOptions[w].second
                    dlg.dismiss()
                }
                .show()
        }

        findViewById<View>(R.id.row_pick_storage).setOnClickListener {
            pickFolderLauncher.launch(null)
        }
        findViewById<View>(R.id.btn_reset_storage).setOnClickListener {
            AppConfig.customSaveUri = ""
            AppConfig.customSaveLabel = ""
            tvStoragePath.text = "默认 (相册 Movies / 系统 Downloads)"
            Toast.makeText(this, "已恢复默认存储位置", Toast.LENGTH_SHORT).show()
        }

        swAdBlock.isChecked = AppConfig.adBlockEnabled
        swSniffVideo.isChecked = AppConfig.sniffVideo
        swSniffAudio.isChecked = AppConfig.sniffAudio
        swSniffDocs.isChecked = AppConfig.sniffDocs

        swAutoMp4.isChecked = AppConfig.autoConvertMp4
        swGallery.isChecked = AppConfig.saveToGallery

        sbConcurrent.progress = (AppConfig.maxConcurrentTasks - 1).coerceIn(0, 5)
        tvConcurrent.text = "同时下载任务数上限: ${AppConfig.maxConcurrentTasks}"
        sbConcurrent.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                tvConcurrent.text = "同时下载任务数上限: ${progress + 1}"
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })

        sbThreads.progress = (AppConfig.threadCount - 2).coerceIn(0, 22)
        tvThreads.text = "多线程下载并发线程数 (HLS/直链): ${AppConfig.threadCount}"
        sbThreads.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                tvThreads.text = "多线程下载并发线程数 (HLS/直链): ${progress + 2}"
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })

        swProxy.isChecked = AppConfig.useProxy
        etHost.setText(AppConfig.proxyHost)
        etPort.setText(AppConfig.proxyPort.toString())

        findViewById<Button>(R.id.btn_save_settings).setOnClickListener {
            AppConfig.uaProfile = selectedUa
            AppConfig.searchEngine = selectedEngine
            AppConfig.adBlockEnabled = swAdBlock.isChecked
            AppConfig.sniffVideo = swSniffVideo.isChecked
            AppConfig.sniffAudio = swSniffAudio.isChecked
            AppConfig.sniffDocs = swSniffDocs.isChecked
            AppConfig.autoConvertMp4 = swAutoMp4.isChecked
            AppConfig.saveToGallery = swGallery.isChecked
            AppConfig.maxConcurrentTasks = sbConcurrent.progress + 1
            AppConfig.threadCount = sbThreads.progress + 2
            AppConfig.useProxy = swProxy.isChecked
            AppConfig.proxyHost = etHost.text.toString().trim()
            AppConfig.proxyPort = etPort.text.toString().toIntOrNull() ?: 7890
            Toast.makeText(this, "全部设置已保存并立即生效", Toast.LENGTH_SHORT).show()
            finish()
        }

        findViewById<Button>(R.id.btn_replay_guide).setOnClickListener {
            OnboardingDialog.showIfNeeded(this, force = true)
        }
    }
}

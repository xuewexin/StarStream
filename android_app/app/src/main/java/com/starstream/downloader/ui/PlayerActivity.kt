package com.starstream.downloader.ui

import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.MediaController
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import android.widget.VideoView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.starstream.downloader.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 极速边下边看内置播放器：通过 LocalStreamProxy 边下载边缓冲起播，支持一键调用外部软件在线预览
 */
class PlayerActivity : AppCompatActivity() {

    private lateinit var videoView: VideoView
    private lateinit var progressBar: ProgressBar
    private var playUrl: String = ""
    private var videoTitle: String = ""
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        playUrl = intent?.getStringExtra("play_url") ?: ""
        videoTitle = intent?.getStringExtra("title") ?: "边下边看"
        if (playUrl.isBlank()) {
            finish()
            return
        }

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.BLACK)
        }
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, wi ->
            val insets = wi.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            v.setPadding(insets.left, insets.top, insets.right, insets.bottom)
            wi
        }

        // 顶部栏：返回 + 标题 + 调用外部软件播放
        val topBar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(ContextCompat.getColor(this@PlayerActivity, R.color.bg_panel))
            setPadding(16, 16, 24, 16)
        }
        topBar.addView(ImageButton(this).apply {
            setImageResource(R.drawable.ic_back)
            setColorFilter(Color.WHITE)
            background = null
            setPadding(16, 16, 16, 16)
            setOnClickListener { finish() }
        })
        topBar.addView(TextView(this).apply {
            text = videoTitle
            setTextColor(Color.WHITE)
            textSize = 15f
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        })
        topBar.addView(TextView(this).apply {
            text = "外部播放器打开"
            setTextColor(ContextCompat.getColor(this@PlayerActivity, R.color.accent_cyan))
            textSize = 12.5f
            setBackgroundResource(R.drawable.bg_input)
            setPadding(24, 12, 24, 12)
            setOnClickListener { openInExternalPlayer() }
        })
        root.addView(topBar)

        val videoBox = android.widget.FrameLayout(this).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
        }
        videoView = VideoView(this).apply {
            layoutParams = android.widget.FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
                Gravity.CENTER
            )
        }
        progressBar = ProgressBar(this).apply {
            layoutParams = android.widget.FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER
            )
        }
        videoBox.addView(videoView)
        videoBox.addView(progressBar)
        root.addView(videoBox)
        setContentView(root)

        val mc = MediaController(this)
        mc.setAnchorView(videoView)
        videoView.setMediaController(mc)

        videoView.setOnPreparedListener { mp ->
            progressBar.visibility = View.GONE
            mp.start()
        }
        videoView.setOnErrorListener { _, _, _ ->
            progressBar.visibility = View.GONE
            Toast.makeText(this, "当前编码建议使用外部播放器（如 VLC / MX Player）在线播放", Toast.LENGTH_LONG).show()
            true
        }

        scope.launch {
            val resolved = withContext(Dispatchers.IO) { playUrl }
            videoView.setVideoURI(Uri.parse(resolved))
            videoView.requestFocus()
        }
    }

    private fun openInExternalPlayer() {
        try {
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(Uri.parse(playUrl), "video/*")
            }
            startActivity(Intent.createChooser(intent, "选择外部播放器在线播放"))
        } catch (_: Throwable) {
            Toast.makeText(this, "未找到可用的外部视频播放器", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onDestroy() {
        scope.cancel()
        try {
            videoView.stopPlayback()
        } catch (_: Throwable) {}
        super.onDestroy()
    }
}

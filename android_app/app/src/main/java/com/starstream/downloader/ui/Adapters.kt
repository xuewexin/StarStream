package com.starstream.downloader.ui

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.ImageView
import android.widget.ProgressBar
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.starstream.downloader.R
import com.starstream.downloader.core.DownloadTask
import com.starstream.downloader.core.SeriesEpisode
import com.starstream.downloader.core.SniffedMedia
import com.starstream.downloader.core.TaskStatus

class SniffedAdapter(
    private val items: MutableList<SniffedMedia>,
    private val onInspect: (SniffedMedia) -> Unit,
    private val onPreview: (SniffedMedia) -> Unit,
    private val onDownload: (SniffedMedia) -> Unit
) : RecyclerView.Adapter<SniffedAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val icon: ImageView = v.findViewById(R.id.iv_sniff_type)
        val title: TextView = v.findViewById(R.id.tv_sniff_title)
        val tag: TextView = v.findViewById(R.id.tv_sniff_tag)
        val url: TextView = v.findViewById(R.id.tv_sniff_url)
        val btnPreview: Button = v.findViewById(R.id.btn_sniff_preview)
        val btn: Button = v.findViewById(R.id.btn_sniff_dl)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_sniffed_media, parent, false)
        return VH(v)
    }

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val m = items[position]
        val ctx = holder.itemView.context
        holder.title.text = m.title

        val (iconRes, tintRes, typeLabel) = when {
            m.audioUrl.isNotBlank() || m.mediaType == "bili_dash" || m.mediaType == "dual_dash" ->
                Triple(R.drawable.ic_video, R.color.accent_purple, "音画合一 · 一键合并")
            m.mediaType == "m3u8" ->
                Triple(R.drawable.ic_video, R.color.accent_cyan, "M3U8 流媒体")
            m.mediaType == "audio" ->
                Triple(R.drawable.ic_audio, R.color.accent_green, "音频 ${m.fileExt.uppercase().ifBlank { "AUDIO" }}")
            m.mediaType == "file" ->
                Triple(R.drawable.ic_file, R.color.accent_amber, "文件 ${m.fileExt.uppercase().ifBlank { "FILE" }}")
            else ->
                Triple(R.drawable.ic_video, R.color.accent_blue, "视频 ${m.fileExt.uppercase().ifBlank { "MP4" }}")
        }
        holder.icon.setImageResource(iconRes)
        holder.icon.setColorFilter(ContextCompat.getColor(ctx, tintRes))

        val parts = mutableListOf(typeLabel)
        if (m.resolution.isNotBlank()) parts.add(m.resolution)
        if (m.durationSec > 0) parts.add(formatDuration(m.durationSec))
        if (m.contentLength > 0) parts.add(formatBytes(m.contentLength))
        holder.tag.text = parts.joinToString(" · ")

        holder.url.text = m.url
        holder.itemView.setOnClickListener { onInspect(m) }
        holder.btnPreview.visibility = if (m.mediaType == "file") View.GONE else View.VISIBLE
        holder.btnPreview.setOnClickListener { onPreview(m) }
        holder.btn.text = if (m.audioUrl.isNotBlank() || m.mediaType == "bili_dash" || m.mediaType == "dual_dash") "合并下载" else "下载"
        holder.btn.setOnClickListener { onDownload(m) }
        ThemeManager.applyThemeToViewTree(ctx, holder.itemView)
    }

    companion object {
        fun formatDuration(sec: Int): String {
            if (sec <= 0) return "--:--"
            val h = sec / 3600
            val m = (sec % 3600) / 60
            val s = sec % 60
            return if (h > 0) String.format("%d:%02d:%02d", h, m, s) else String.format("%02d:%02d", m, s)
        }

        fun formatBytes(b: Long): String {
            if (b <= 0) return "未知"
            return when {
                b >= 1024L * 1024 * 1024 -> String.format("%.2f GB", b / (1024.0 * 1024.0 * 1024.0))
                b >= 1024L * 1024 -> String.format("%.1f MB", b / (1024.0 * 1024.0))
                b >= 1024L -> String.format("%.1f KB", b / 1024.0)
                else -> "$b B"
            }
        }
    }
}

class SeriesAdapter(
    private val items: List<SeriesEpisode>,
    private val onSelectionChanged: () -> Unit
) : RecyclerView.Adapter<SeriesAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val cb: CheckBox = v.findViewById(R.id.cb_episode)
        val title: TextView = v.findViewById(R.id.tv_ep_title)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_series_episode, parent, false)
        return VH(v)
    }

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val ep = items[position]
        val durStr = if (ep.durationSec > 0) String.format(" [%02d:%02d]", ep.durationSec / 60, ep.durationSec % 60) else ""
        holder.title.text = String.format("%02d. %s%s", ep.index, ep.title, durStr)
        holder.cb.setOnCheckedChangeListener(null)
        holder.cb.isChecked = ep.selected
        holder.cb.setOnCheckedChangeListener { _, checked ->
            ep.selected = checked
            onSelectionChanged()
        }
        holder.itemView.setOnClickListener {
            ep.selected = !ep.selected
            holder.cb.isChecked = ep.selected
            onSelectionChanged()
        }
    }
}

class DownloadTaskAdapter(
    private var items: List<DownloadTask>,
    private val onAction: (DownloadTask) -> Unit,
    private val onPreview: (DownloadTask) -> Unit,
    private val onDelete: (DownloadTask) -> Unit,
    private val onMore: (DownloadTask) -> Unit,
    private val onSelectionChanged: ((Int) -> Unit)? = null,
    private val onEnterSelectionMode: ((String) -> Unit)? = null
) : RecyclerView.Adapter<DownloadTaskAdapter.VH>() {

    var selectionMode: Boolean = false
        private set
    val selectedIds = linkedSetOf<String>()

    fun setSelectionMode(enabled: Boolean, initialSelectedId: String? = null) {
        selectionMode = enabled
        selectedIds.clear()
        if (enabled && !initialSelectedId.isNullOrBlank()) {
            selectedIds.add(initialSelectedId)
        }
        notifyDataSetChanged()
        onSelectionChanged?.invoke(selectedIds.size)
    }

    fun selectAllShown() {
        selectedIds.clear()
        items.forEach { selectedIds.add(it.id) }
        notifyDataSetChanged()
        onSelectionChanged?.invoke(selectedIds.size)
    }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val cbSelect: CheckBox = v.findViewById(R.id.cb_task_select)
        val title: TextView = v.findViewById(R.id.tv_task_title)
        val status: TextView = v.findViewById(R.id.tv_task_status)
        val pb: ProgressBar = v.findViewById(R.id.pb_task)
        val meta: TextView = v.findViewById(R.id.tv_task_meta)
        val btnPreview: Button = v.findViewById(R.id.btn_task_preview)
        val btnAction: Button = v.findViewById(R.id.btn_task_action)
        val btnDel: Button = v.findViewById(R.id.btn_task_del)
        val btnMore: android.widget.ImageButton = v.findViewById(R.id.btn_task_more)
    }

    fun updateData(newList: List<DownloadTask>) {
        items = newList
        val validIds = newList.map { it.id }.toSet()
        selectedIds.retainAll(validIds)
        notifyDataSetChanged()
        onSelectionChanged?.invoke(selectedIds.size)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_download_task, parent, false)
        return VH(v)
    }

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val t = items[position]
        holder.title.text = t.title
        holder.pb.progress = t.progress

        holder.cbSelect.setOnCheckedChangeListener(null)
        holder.cbSelect.visibility = if (selectionMode) View.VISIBLE else View.GONE
        holder.cbSelect.isChecked = selectedIds.contains(t.id)
        holder.cbSelect.setOnCheckedChangeListener { _, checked ->
            if (checked) selectedIds.add(t.id) else selectedIds.remove(t.id)
            onSelectionChanged?.invoke(selectedIds.size)
        }
        holder.itemView.setOnClickListener {
            if (selectionMode) {
                val nowChecked = !selectedIds.contains(t.id)
                if (nowChecked) selectedIds.add(t.id) else selectedIds.remove(t.id)
                holder.cbSelect.isChecked = nowChecked
                onSelectionChanged?.invoke(selectedIds.size)
            }
        }

        val (statusStr, btnText) = when (t.status) {
            TaskStatus.WAITING -> "等待中" to "暂停"
            TaskStatus.DOWNLOADING -> "下载中 ${t.progress}%" to "暂停"
            TaskStatus.MUXING -> "FFmpeg混流" to "处理中"
            TaskStatus.COMPLETED -> "已完成" to "打开"
            TaskStatus.PAUSED -> "已暂停" to "继续"
            TaskStatus.ERROR -> "失败" to "重试"
        }
        holder.status.text = statusStr
        holder.btnAction.text = btnText
        holder.btnAction.isEnabled = t.status != TaskStatus.MUXING

        val canWatchLive = t.mediaType != "file" && t.url.startsWith("http") &&
            (t.status == TaskStatus.DOWNLOADING || t.status == TaskStatus.PAUSED || t.status == TaskStatus.WAITING)
        holder.btnPreview.visibility = if (canWatchLive) View.VISIBLE else View.GONE
        holder.btnPreview.setOnClickListener { onPreview(t) }

        val szStr = SniffedAdapter.formatBytes(t.downloadedBytes).replace("未知", "0 B")
        holder.meta.text = when {
            t.status == TaskStatus.ERROR && t.errorMsg.isNotBlank() -> t.errorMsg
            t.speedText.isNotBlank() -> "$szStr · ${t.speedText}"
            else -> szStr
        }

        holder.btnAction.setOnClickListener { onAction(t) }
        holder.btnDel.setOnClickListener { onDelete(t) }
        holder.btnMore.setOnClickListener { onMore(t) }
        holder.itemView.setOnLongClickListener {
            if (!selectionMode) {
                onEnterSelectionMode?.invoke(t.id)
            } else {
                onMore(t)
            }
            true
        }
        ThemeManager.applyThemeToViewTree(holder.itemView.context, holder.itemView)
    }
}

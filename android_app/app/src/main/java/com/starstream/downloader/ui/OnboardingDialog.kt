package com.starstream.downloader.ui

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.annotation.DrawableRes
import androidx.appcompat.app.AlertDialog
import androidx.core.content.ContextCompat
import com.starstream.downloader.R
import com.starstream.downloader.core.AppConfig

/**
 * 新手引导弹窗与带矢量图标的菜单辅助类 (全矢量图标, 零 Emoji)
 */
object OnboardingDialog {

    private data class GuideStep(
        @DrawableRes val iconRes: Int,
        val tintRes: Int,
        val title: String,
        val subtitle: String,
        val body: String
    )

    fun showIfNeeded(context: Context, force: Boolean = false) {
        if (!force && AppConfig.hasSeenGuide) return

        val steps = listOf(
            GuideStep(
                iconRes = R.drawable.ic_browser,
                tintRes = R.color.accent_cyan,
                title = "多内核内置浏览器与下拉刷新",
                subtitle = "步骤 1 / 4 · 极简启动页 & 多浏览内核",
                body = "点击主界面右上角「浏览器」进入纯净启动页，可自由切换搜索引\n" +
                    "擎与内置浏览器内核 (Chrome 桌面/手机、Edge、Safari、Firefox)。\n" +
                    "网页与下载列表均支持下拉刷新，左右滑分别管理多标签与收藏夹。"
            ),
            GuideStep(
                iconRes = R.drawable.ic_download,
                tintRes = R.color.accent_blue,
                title = "多类型文件全网嗅探与详情查看",
                subtitle = "步骤 2 / 4 · 视频 · 音频 · 文档与安装包",
                body = "浏览网页或播放视频时，右上角下载徽标会实时累计捕获结果，\n" +
                    "支持 M3U8/MPD/MP4 等视频流、MP3/M4A/FLAC 音频以及 PDF/\n" +
                    "ZIP/APK 等常规文件。\n\n" +
                    "点击任意嗅探条目可查看完整详情：时长、类型格式、分辨率与文件\n" +
                    "大小，再决定直接下载或深度解析。"
            ),
            GuideStep(
                iconRes = R.drawable.ic_bolt,
                tintRes = R.color.accent_purple,
                title = "同系列合集连爬 & 音画双流混流",
                subtitle = "步骤 3 / 4 · 一键批量解析",
                body = "在浏览器底部点击「同系列」或「深解析」，可自动识别 B站多P\n" +
                    "合集与泛影视选集列表，勾选举集即可批量下载；支持安卓原生硬\n" +
                    "件 MediaMuxer 音视频无损封装输出标准 MP4。"
            ),
            GuideStep(
                iconRes = R.drawable.ic_settings,
                tintRes = R.color.accent_green,
                title = "完全可自定义的设置中心",
                subtitle = "步骤 4 / 4 · 自由掌控偏好",
                body = "在侧边栏「下载与偏好设置」中可随时调整：\n" +
                    "· 默认搜索引擎与内置浏览器内核 UA\n" +
                    "· 广告拦截开关与嗅探文件类型过滤 (视频 / 音频 / 文档压缩包)\n" +
                    "· HLS 并发线程数、HTTP 代理与导出相册/Downloads 目录"
            )
        )

        var currentStep = 0

        val pal = ThemeManager.current()
        val card = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            background = ThemeManager.makeRoundedBg(pal.bgPanel, 16f, pal.border, 1f, context)
            setPadding(56, 52, 56, 44)
        }

        val iconCircle = LinearLayout(context).apply {
            gravity = Gravity.CENTER
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(pal.bgInput)
                setStroke(2, pal.border)
            }
            layoutParams = LinearLayout.LayoutParams(148, 148).apply {
                gravity = Gravity.CENTER_HORIZONTAL
                bottomMargin = 28
            }
        }
        val ivIcon = ImageView(context).apply {
            layoutParams = LinearLayout.LayoutParams(76, 76)
        }
        iconCircle.addView(ivIcon)
        card.addView(iconCircle)

        val tvSubtitle = TextView(context).apply {
            textSize = 12f
            gravity = Gravity.CENTER
            setTextColor(pal.accent)
        }
        card.addView(tvSubtitle)

        val tvTitle = TextView(context).apply {
            textSize = 18f
            gravity = Gravity.CENTER
            setTypeface(null, android.graphics.Typeface.BOLD)
            setTextColor(pal.textPrimary)
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                topMargin = 10
                bottomMargin = 20
            }
        }
        card.addView(tvTitle)

        val tvBody = TextView(context).apply {
            textSize = 13f
            setLineSpacing(6f, 1.15f)
            setTextColor(pal.textSecondary)
            background = ThemeManager.makeRoundedBg(pal.bgCard, 12f, pal.border, 1f, context)
            setPadding(34, 30, 34, 30)
            minLines = 6
        }
        card.addView(tvBody)

        val dotsRow = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                topMargin = 28
                bottomMargin = 24
            }
        }
        val dots = steps.map {
            View(context).apply {
                layoutParams = LinearLayout.LayoutParams(18, 18).apply { marginEnd = 14 }
            }
        }
        dots.forEach { dotsRow.addView(it) }
        card.addView(dotsRow)

        val btnRow = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val btnSkip = Button(context).apply {
            text = "跳过"
            textSize = 13f
            setTextColor(pal.textPrimary)
            background = ThemeManager.makeRoundedBg(pal.bgInput, 8f, pal.border, 1f, context)
            layoutParams = LinearLayout.LayoutParams(0, 108, 1f).apply { marginEnd = 16 }
        }
        val btnNext = Button(context).apply {
            textSize = 13.5f
            setTypeface(null, android.graphics.Typeface.BOLD)
            setTextColor(Color.WHITE)
            background = ThemeManager.makeRoundedBg(pal.accent, 8f, 0, 0f, context)
            layoutParams = LinearLayout.LayoutParams(0, 108, 1.6f)
        }
        btnRow.addView(btnSkip)
        btnRow.addView(btnNext)
        card.addView(btnRow)

        val dialog = ThemeManager.dialogBuilder(context)
            .setView(card)
            .setCancelable(force)
            .create()

        fun renderStep() {
            val s = steps[currentStep]
            ivIcon.setImageResource(s.iconRes)
            ivIcon.setColorFilter(ContextCompat.getColor(context, s.tintRes))
            tvSubtitle.text = s.subtitle
            tvTitle.text = s.title
            tvBody.text = s.body

            dots.forEachIndexed { idx, v ->
                val active = idx == currentStep
                v.background = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(
                        ContextCompat.getColor(
                            context,
                            if (active) R.color.accent_cyan else R.color.border_subtle
                        )
                    )
                }
            }

            btnSkip.text = if (currentStep == 0) "跳过引导" else "上一步"
            btnNext.text = if (currentStep == steps.lastIndex) "立即体验" else "下一步"
        }

        btnSkip.setOnClickListener {
            if (currentStep == 0) {
                AppConfig.hasSeenGuide = true
                dialog.dismiss()
            } else {
                currentStep--
                renderStep()
            }
        }

        btnNext.setOnClickListener {
            if (currentStep < steps.lastIndex) {
                currentStep++
                renderStep()
            } else {
                AppConfig.hasSeenGuide = true
                dialog.dismiss()
            }
        }

        renderStep()
        dialog.show()
    }
}

data class IconMenuItem(
    @DrawableRes val iconRes: Int,
    val title: String,
    val subtitle: String = ""
)

fun showIconMenuDialog(
    context: Context,
    title: String,
    items: List<IconMenuItem>,
    onSelect: (Int) -> Unit
) {
    val pal = ThemeManager.current()
    val adapter = object : ArrayAdapter<IconMenuItem>(context, 0, items) {
        override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
            val row = (convertView as? LinearLayout) ?: LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(44, 28, 44, 28)
            }
            row.removeAllViews()
            val item = items[position]

            val iv = ImageView(context).apply {
                setImageResource(item.iconRes)
                setColorFilter(pal.accent)
                layoutParams = LinearLayout.LayoutParams(50, 50).apply { marginEnd = 30 }
            }
            row.addView(iv)

            val col = LinearLayout(context).apply {
                orientation = LinearLayout.VERTICAL
                layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            }
            col.addView(TextView(context).apply {
                text = item.title
                textSize = 14.5f
                setTextColor(pal.textPrimary)
            })
            if (item.subtitle.isNotBlank()) {
                col.addView(TextView(context).apply {
                    text = item.subtitle
                    textSize = 11.5f
                    setTextColor(pal.textMuted)
                })
            }
            row.addView(col)
            return row
        }
    }

    ThemeManager.dialogBuilder(context)
        .setTitle(title)
        .setAdapter(adapter) { _, which -> onSelect(which) }
        .setNegativeButton("取消", null)
        .show()
}

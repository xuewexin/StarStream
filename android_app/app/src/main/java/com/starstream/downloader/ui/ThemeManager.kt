package com.starstream.downloader.ui

import android.app.Activity
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.drawable.BitmapDrawable
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.core.view.WindowCompat
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.navigation.NavigationView
import com.starstream.downloader.core.AppConfig
import java.io.File

data class ThemePalette(
    val key: String,
    val label: String,
    val isLight: Boolean,
    val bgMain: Int,
    val bgPanel: Int,
    val bgCard: Int,
    val bgInput: Int,
    val border: Int,
    val accent: Int,
    val textPrimary: Int,
    val textSecondary: Int,
    val textMuted: Int
)

object ThemeManager {

    val PRESETS = listOf(
        ThemePalette(
            key = "obsidian",
            label = "极夜黑曜 (默认深色)",
            isLight = false,
            bgMain = Color.parseColor("#0D1117"),
            bgPanel = Color.parseColor("#161B24"),
            bgCard = Color.parseColor("#1D2432"),
            bgInput = Color.parseColor("#273042"),
            border = Color.parseColor("#334056"),
            accent = Color.parseColor("#3B82F6"),
            textPrimary = Color.parseColor("#F4F7FB"),
            textSecondary = Color.parseColor("#CBD5E1"),
            textMuted = Color.parseColor("#8A96A8")
        ),
        ThemePalette(
            key = "ocean",
            label = "深海午夜 (藏青护眼)",
            isLight = false,
            bgMain = Color.parseColor("#081224"),
            bgPanel = Color.parseColor("#0F1E38"),
            bgCard = Color.parseColor("#152747"),
            bgInput = Color.parseColor("#1D335B"),
            border = Color.parseColor("#2A4678"),
            accent = Color.parseColor("#38BDF8"),
            textPrimary = Color.parseColor("#F0F7FF"),
            textSecondary = Color.parseColor("#C7DAF0"),
            textMuted = Color.parseColor("#88A3C7")
        ),
        ThemePalette(
            key = "nebula",
            label = "星云暮紫 (静谧紫调)",
            isLight = false,
            bgMain = Color.parseColor("#120F22"),
            bgPanel = Color.parseColor("#1A1630"),
            bgCard = Color.parseColor("#231E40"),
            bgInput = Color.parseColor("#2E2852"),
            border = Color.parseColor("#413970"),
            accent = Color.parseColor("#A78BFA"),
            textPrimary = Color.parseColor("#F5F3FF"),
            textSecondary = Color.parseColor("#DDD6FE"),
            textMuted = Color.parseColor("#9F96C9")
        ),
        ThemePalette(
            key = "graphite",
            label = "素灰工业 (中性碳灰)",
            isLight = false,
            bgMain = Color.parseColor("#16181D"),
            bgPanel = Color.parseColor("#1F2229"),
            bgCard = Color.parseColor("#272B34"),
            bgInput = Color.parseColor("#323742"),
            border = Color.parseColor("#424957"),
            accent = Color.parseColor("#60A5FA"),
            textPrimary = Color.parseColor("#F3F4F6"),
            textSecondary = Color.parseColor("#D1D5DB"),
            textMuted = Color.parseColor("#9CA3AF")
        ),
        ThemePalette(
            key = "daylight",
            label = "晴空浅白 (明亮浅色)",
            isLight = true,
            bgMain = Color.parseColor("#F1F5FA"),
            bgPanel = Color.parseColor("#FFFFFF"),
            bgCard = Color.parseColor("#FFFFFF"),
            bgInput = Color.parseColor("#E6EDF6"),
            border = Color.parseColor("#CFD9E8"),
            accent = Color.parseColor("#2563EB"),
            textPrimary = Color.parseColor("#0F172A"),
            textSecondary = Color.parseColor("#334155"),
            textMuted = Color.parseColor("#64748B")
        )
    )

    fun current(): ThemePalette {
        val key = AppConfig.themeKey
        return PRESETS.find { it.key == key } ?: PRESETS[0]
    }

    private val roleCache = java.util.WeakHashMap<View, String>()

    private fun resolveRole(context: Context, view: View): String {
        roleCache[view]?.let { return it }
        val role = when (view) {
            is Button -> {
                val cs = view.background?.constantState
                if (cs != null && cs == context.getDrawable(com.starstream.downloader.R.drawable.bg_btn_primary)?.constantState) {
                    "primary_btn"
                } else {
                    "secondary_btn"
                }
            }
            is EditText -> {
                val bg = view.background
                if (bg !is ColorDrawable || bg.color != Color.TRANSPARENT) "input" else "transparent_edit"
            }
            else -> {
                val bg = view.background
                if (bg is ColorDrawable) {
                    when (bg.color) {
                        Color.parseColor("#1B1E26") -> "panel"
                        Color.parseColor("#121418") -> "main_bg"
                        Color.parseColor("#303646") -> "divider"
                        else -> if (view.id == com.starstream.downloader.R.id.layout_selection_bar) "panel" else "none"
                    }
                } else {
                    val cs = bg?.constantState
                    when (cs) {
                        context.getDrawable(com.starstream.downloader.R.drawable.bg_card)?.constantState -> "card"
                        context.getDrawable(com.starstream.downloader.R.drawable.bg_input)?.constantState -> "input"
                        else -> "none"
                    }
                }
            }
        }
        roleCache[view] = role
        return role
    }

    fun hasCustomBackground(): Boolean {
        val p = AppConfig.customBgPath
        return p.isNotBlank() && File(p).exists()
    }

    fun dp(context: Context, value: Float): Int {
        return TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP,
            value,
            context.resources.displayMetrics
        ).toInt()
    }

    fun makeRoundedBg(fillColor: Int, radiusDp: Float, strokeColor: Int = 0, strokeDp: Float = 1f, context: Context): GradientDrawable {
        return GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dp(context, radiusDp).toFloat()
            setColor(fillColor)
            if (strokeColor != 0 && strokeDp > 0f) {
                setStroke(dp(context, strokeDp).coerceAtLeast(1), strokeColor)
            }
        }
    }

    private fun withAlpha(color: Int, alpha01: Float): Int {
        val a = (alpha01.coerceIn(0f, 1f) * 255).toInt()
        return Color.argb(a, Color.red(color), Color.green(color), Color.blue(color))
    }

    private fun buildBackgroundDrawable(context: Context, p: ThemePalette): Drawable {
        val bgPath = AppConfig.customBgPath
        if (bgPath.isNotBlank()) {
            val f = File(bgPath)
            if (f.exists()) {
                try {
                    val dm = context.resources.displayMetrics
                    val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                    BitmapFactory.decodeFile(f.absolutePath, opts)
                    var sample = 1
                    while (opts.outWidth / sample > dm.widthPixels * 2 && opts.outHeight / sample > dm.heightPixels * 2) {
                        sample *= 2
                    }
                    val loadOpts = BitmapFactory.Options().apply { inSampleSize = sample }
                    val rawBmp = BitmapFactory.decodeFile(f.absolutePath, loadOpts)
                    if (rawBmp != null) {
                        val w = dm.widthPixels.coerceAtLeast(360)
                        val h = dm.heightPixels.coerceAtLeast(640)
                        val outBmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
                        val canvas = Canvas(outBmp)
                        val scale = maxOf(w.toFloat() / rawBmp.width, h.toFloat() / rawBmp.height)
                        val drawW = rawBmp.width * scale
                        val drawH = rawBmp.height * scale
                        val left = (w - drawW) / 2f
                        val top = (h - drawH) / 2f
                        val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
                        canvas.drawBitmap(rawBmp, null, android.graphics.RectF(left, top, left + drawW, top + drawH), paint)
                        if (!rawBmp.isRecycled) rawBmp.recycle()

                        val dimAlpha = AppConfig.bgDimPercent / 100f
                        val overlayColor = withAlpha(p.bgMain, dimAlpha)
                        canvas.drawColor(overlayColor)
                        return BitmapDrawable(context.resources, outBmp)
                    }
                } catch (_: Throwable) {}
            }
        }
        return ColorDrawable(p.bgMain)
    }

    fun applyTheme(activity: Activity, rootView: View? = null, navView: NavigationView? = null) {
        val p = current()
        try {
            activity.window.statusBarColor = p.bgPanel
            activity.window.navigationBarColor = p.bgPanel
            val wic = WindowCompat.getInsetsController(activity.window, activity.window.decorView)
            wic.isAppearanceLightStatusBars = p.isLight
            wic.isAppearanceLightNavigationBars = p.isLight
        } catch (_: Throwable) {}

        val hasBgImg = hasCustomBackground()
        val windowBg = buildBackgroundDrawable(activity, p)
        activity.window.setBackgroundDrawable(windowBg)

        if (rootView != null) {
            if (hasBgImg) {
                rootView.setBackgroundColor(Color.TRANSPARENT)
            } else {
                rootView.setBackgroundColor(p.bgMain)
            }
            applyThemeToViewTree(activity, rootView, p, hasBgImg)
        }

        if (navView != null) {
            navView.setBackgroundColor(p.bgPanel)
            navView.itemTextColor = ColorStateList.valueOf(p.textPrimary)
            navView.itemIconTintList = ColorStateList.valueOf(p.accent)
            if (navView.headerCount > 0) {
                val hdr = navView.getHeaderView(0)
                hdr.setBackgroundColor(p.bgCard)
                applyThemeToViewTree(activity, hdr, p, false)
            }
        }
    }

    fun applyThemeToViewTree(context: Context, view: View, p: ThemePalette = current(), hasCustomBg: Boolean = hasCustomBackground()) {
        val cardFill = if (hasCustomBg) withAlpha(p.bgCard, 0.85f) else p.bgCard
        val panelFill = if (hasCustomBg) withAlpha(p.bgPanel, 0.90f) else p.bgPanel
        val inputFill = if (hasCustomBg) withAlpha(p.bgInput, 0.90f) else p.bgInput
        val role = resolveRole(context, view)

        when (view) {
            is Button -> {
                if (role == "primary_btn") {
                    view.background = makeRoundedBg(p.accent, 8f, 0, 0f, context)
                    view.setTextColor(Color.WHITE)
                } else {
                    view.background = makeRoundedBg(inputFill, 8f, p.border, 1f, context)
                    val curColor = view.currentTextColor
                    val isDanger = curColor == Color.parseColor("#FF5252") || curColor == Color.parseColor("#EF4444") || view.text.toString().contains("删")
                    view.setTextColor(if (isDanger) Color.parseColor("#EF4444") else p.textPrimary)
                }
            }
            is EditText -> {
                if (role == "input") {
                    view.background = makeRoundedBg(inputFill, 8f, p.border, 1f, context)
                }
                view.setTextColor(p.textPrimary)
                view.setHintTextColor(p.textMuted)
            }
            is CheckBox -> {
                view.setTextColor(p.textPrimary)
                view.buttonTintList = ColorStateList.valueOf(p.accent)
            }
            is Switch -> {
                view.setTextColor(p.textPrimary)
            }
            is TextView -> {
                val cur = view.currentTextColor
                val lum = (0.299 * Color.red(cur) + 0.587 * Color.green(cur) + 0.114 * Color.blue(cur))
                if (p.isLight && lum > 175 && cur != Color.WHITE && role != "primary_btn") {
                    view.setTextColor(p.textPrimary)
                } else if (!p.isLight && lum < 80) {
                    view.setTextColor(p.textPrimary)
                }
                if (role == "input") {
                    view.background = makeRoundedBg(inputFill, 8f, p.border, 1f, context)
                }
            }
            is ImageButton -> {
                if (role == "input") {
                    view.background = makeRoundedBg(inputFill, 8f, p.border, 1f, context)
                }
            }
        }

        if (view is ViewGroup) {
            when (role) {
                "panel" -> view.setBackgroundColor(panelFill)
                "main_bg" -> view.setBackgroundColor(if (hasCustomBg) Color.TRANSPARENT else p.bgMain)
                "divider" -> view.setBackgroundColor(p.border)
                "card" -> view.background = makeRoundedBg(cardFill, 12f, p.border, 1f, context)
                "input" -> view.background = makeRoundedBg(inputFill, 8f, p.border, 1f, context)
            }

            for (i in 0 until view.childCount) {
                applyThemeToViewTree(context, view.getChildAt(i), p, hasCustomBg)
            }
        }
    }

    /**
     * 统一构建并美化匹配当前主题配色的圆角弹窗
     */
    fun dialogBuilder(context: Context): ThemedDialogBuilder {
        return ThemedDialogBuilder(context)
    }

    fun styleAlertDialog(dialog: AlertDialog, context: Context) {
        val p = current()
        dialog.window?.setBackgroundDrawable(makeRoundedBg(p.bgPanel, 16f, p.border, 1.2f, context))

        val decor = dialog.window?.decorView
        if (decor != null) {
            applyThemeToDialogTree(context, decor, p)
        }

        // 美化底部 Positive / Negative / Neutral 按钮
        val posBtn = dialog.getButton(AlertDialog.BUTTON_POSITIVE)
        val negBtn = dialog.getButton(AlertDialog.BUTTON_NEGATIVE)
        val neuBtn = dialog.getButton(AlertDialog.BUTTON_NEUTRAL)

        posBtn?.let { b ->
            b.isAllCaps = false
            b.setTextColor(Color.WHITE)
            b.background = makeRoundedBg(p.accent, 8f, 0, 0f, context)
            val padH = dp(context, 14f)
            val padV = dp(context, 6f)
            b.setPadding(padH, padV, padH, padV)
        }
        negBtn?.let { b ->
            b.isAllCaps = false
            val isDanger = b.text.toString().contains("连带删除") || b.text.toString().contains("彻底")
            b.setTextColor(if (isDanger) Color.parseColor("#EF4444") else p.textPrimary)
            b.background = makeRoundedBg(p.bgInput, 8f, p.border, 1f, context)
            val padH = dp(context, 12f)
            val padV = dp(context, 6f)
            b.setPadding(padH, padV, padH, padV)
        }
        neuBtn?.let { b ->
            b.isAllCaps = false
            b.setTextColor(p.textSecondary)
            b.background = makeRoundedBg(Color.TRANSPARENT, 8f, 0, 0f, context)
        }
    }

    fun styleBottomSheet(sheet: BottomSheetDialog, context: Context) {
        val p = current()
        sheet.setOnShowListener {
            val container = sheet.findViewById<View>(com.google.android.material.R.id.design_bottom_sheet)
            if (container != null) {
                val gd = GradientDrawable().apply {
                    shape = GradientDrawable.RECTANGLE
                    val r = dp(context, 18f).toFloat()
                    cornerRadii = floatArrayOf(r, r, r, r, 0f, 0f, 0f, 0f)
                    setColor(p.bgPanel)
                    setStroke(dp(context, 1f).coerceAtLeast(1), p.border)
                }
                container.background = gd
                applyThemeToViewTree(context, container, p, false)
            }
        }
    }

    private fun applyThemeToDialogTree(context: Context, view: View, p: ThemePalette) {
        when (view) {
            is Button -> return // 底部标准 DialogButton 单独美化
            is EditText -> {
                view.background = makeRoundedBg(p.bgInput, 8f, p.border, 1f, context)
                view.setTextColor(p.textPrimary)
                view.setHintTextColor(p.textMuted)
                val pad = dp(context, 10f)
                view.setPadding(pad, pad, pad, pad)
            }
            is CheckBox -> {
                view.setTextColor(p.textPrimary)
                view.buttonTintList = ColorStateList.valueOf(p.accent)
            }
            is TextView -> {
                val idName = try {
                    if (view.id != View.NO_ID) context.resources.getResourceEntryName(view.id) else ""
                } catch (_: Exception) { "" }
                when {
                    idName.contains("alertTitle") -> view.setTextColor(p.textPrimary)
                    idName == "message" -> view.setTextColor(p.textSecondary)
                    else -> {
                        val cur = view.currentTextColor
                        val lum = (0.299 * Color.red(cur) + 0.587 * Color.green(cur) + 0.114 * Color.blue(cur))
                        if (p.isLight && lum > 175 && cur != Color.WHITE) {
                            view.setTextColor(p.textPrimary)
                        } else if (!p.isLight && lum < 90) {
                            view.setTextColor(p.textPrimary)
                        }
                    }
                }
            }
            is ImageView -> {
                // 保持功能矢量图标强调色
            }
        }
        if (view is ViewGroup) {
            for (i in 0 until view.childCount) {
                applyThemeToDialogTree(context, view.getChildAt(i), p)
            }
        }
    }
}

class ThemedDialogBuilder(private val ctx: Context) : AlertDialog.Builder(ctx) {
    override fun create(): AlertDialog {
        val dlg = super.create()
        dlg.setOnShowListener {
            ThemeManager.styleAlertDialog(dlg, ctx)
        }
        return dlg
    }

    override fun show(): AlertDialog {
        val dlg = create()
        dlg.show()
        return dlg
    }
}

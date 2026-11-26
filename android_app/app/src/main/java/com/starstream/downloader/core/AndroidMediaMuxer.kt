package com.starstream.downloader.core

import android.content.ContentValues
import android.content.Context
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMuxer
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.documentfile.provider.DocumentFile
import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.FFprobeKit
import com.arthenica.ffmpegkit.ReturnCode
import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer

/**
 * 移植自 PC 端 ffmpeg_engine.py + download_file.py 的移动端 FFmpeg 无损音画混流与封装引擎
 * 优先调用真 FFmpegKit（-map 0:v:0 -map 1:a:0 -c copy +aac 降级 + aac_adtstoasc），
 * 并在合并后校验输出文件是否同时包含画面与声音，彻底消除安卓无画面/无声音或 B站 DASH 混流失败。
 */
object AndroidMediaMuxer {

    fun isHtmlOrInvalidFile(file: File): Boolean {
        if (!file.exists() || file.length() < 128) return true
        return try {
            val head = ByteArray(256)
            val n = FileInputStream(file).use { it.read(head) }
            val prefix = String(head, 0, n.coerceAtLeast(0), Charsets.UTF_8).trimStart().lowercase()
            prefix.startsWith("<!doctype") || prefix.startsWith("<html") ||
                prefix.startsWith("{\"code\":") || prefix.startsWith("{\"message\":")
        } catch (_: Exception) {
            false
        }
    }

    fun probeStreamPresence(file: File): Pair<Boolean, Boolean> {
        if (!file.exists() || file.length() == 0L) return false to false
        try {
            val infoSession = FFprobeKit.getMediaInformation(file.absolutePath)
            val streams = infoSession?.mediaInformation?.streams
            if (!streams.isNullOrEmpty()) {
                var hasV = false
                var hasA = false
                for (s in streams) {
                    val t = s.type?.lowercase() ?: ""
                    if (t == "video") hasV = true
                    if (t == "audio") hasA = true
                }
                if (hasV || hasA) return hasV to hasA
            }
        } catch (_: Throwable) {}

        val extractor = MediaExtractor()
        return try {
            extractor.setDataSource(file.absolutePath)
            var hasV = false
            var hasA = false
            for (i in 0 until extractor.trackCount) {
                val mime = extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME) ?: ""
                if (mime.startsWith("video/")) hasV = true
                if (mime.startsWith("audio/")) hasA = true
            }
            hasV to hasA
        } catch (_: Throwable) {
            false to false
        } finally {
            try { extractor.release() } catch (_: Exception) {}
        }
    }

    private fun runFfmpeg(args: Array<String>): Boolean {
        return try {
            val session = FFmpegKit.executeWithArguments(args)
            ReturnCode.isSuccess(session.returnCode)
        } catch (_: Throwable) {
            false
        }
    }

    /**
     * 移植 PC 端 download_file.py:_download_dual_stream 混流策略：
     * 1) 无损直出: -i video -i audio -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy -movflags +faststart
     * 2) 音频转 AAC 兼容混流: -c:v copy -c:a aac -b:a 192k (兼容 Opus/Vorbis/FLAC/E-AC-3 等)
     * 3) 兜底原生 MediaExtractor+MediaMuxer
     */
    fun muxVideoAndAudio(videoFile: File, audioFile: File, outputMp4: File): Boolean {
        if (isHtmlOrInvalidFile(videoFile) || isHtmlOrInvalidFile(audioFile)) return false

        val vIn = probeStreamPresence(videoFile)
        val aIn = probeStreamPresence(audioFile)
        val expectVideo = vIn.first || !vIn.second
        val expectAudio = aIn.second || audioFile.length() > 1024

        // 策略 1: PC 端同款无损 stream copy 混流
        if (outputMp4.exists()) outputMp4.delete()
        val copyCmd = arrayOf(
            "-y",
            "-fflags", "+genpts",
            "-i", videoFile.absolutePath,
            "-i", audioFile.absolutePath,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-movflags", "+faststart",
            outputMp4.absolutePath
        )
        if (runFfmpeg(copyCmd) && outputMp4.exists() && outputMp4.length() > 1024) {
            val outStreams = probeStreamPresence(outputMp4)
            if ((!expectVideo || outStreams.first) && (!expectAudio || outStreams.second)) {
                return true
            }
        }

        // 策略 2: PC 端同款降级 AAC 高清转码混流
        if (outputMp4.exists()) outputMp4.delete()
        val aacCmd = arrayOf(
            "-y",
            "-fflags", "+genpts",
            "-i", videoFile.absolutePath,
            "-i", audioFile.absolutePath,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            outputMp4.absolutePath
        )
        if (runFfmpeg(aacCmd) && outputMp4.exists() && outputMp4.length() > 1024) {
            val outStreams = probeStreamPresence(outputMp4)
            if ((!expectVideo || outStreams.first) && (!expectAudio || outStreams.second)) {
                return true
            }
        }

        // 策略 3: 安卓原生硬件级 MediaMuxer 兜底
        return muxVideoAndAudioNative(videoFile, audioFile, outputMp4)
    }

    /**
     * 移植 PC 端 check_auto_convert_mp4:
     * 使用 FFmpeg 将 HLS TS / fMP4 / FLV 等容器无损重封装为带 +faststart 的标准 MP4，
     * 并严格校验输出音画流完整性。
     */
    fun remuxTsToMp4(inputFile: File, outputMp4: File): Boolean {
        if (isHtmlOrInvalidFile(inputFile)) return false
        val inStreams = probeStreamPresence(inputFile)

        // 尝试 1: TS ADTS->ASC +genpts 无损重封装
        if (outputMp4.exists()) outputMp4.delete()
        val tsBsfCmd = arrayOf(
            "-y",
            "-fflags", "+genpts+discardcorrupt",
            "-i", inputFile.absolutePath,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "+faststart",
            outputMp4.absolutePath
        )
        if (runFfmpeg(tsBsfCmd) && verifyOutputStreams(outputMp4, inStreams)) return true

        // 尝试 2: 通用无损封装 (针对 fMP4 / FLV / 已有 ASC 头的流)
        if (outputMp4.exists()) outputMp4.delete()
        val plainCmd = arrayOf(
            "-y",
            "-fflags", "+genpts",
            "-i", inputFile.absolutePath,
            "-c", "copy",
            "-movflags", "+faststart",
            outputMp4.absolutePath
        )
        if (runFfmpeg(plainCmd) && verifyOutputStreams(outputMp4, inStreams)) return true

        // 尝试 3: 视频无损 copy + 非标音频转 AAC
        if (inStreams.second) {
            if (outputMp4.exists()) outputMp4.delete()
            val aacFallback = arrayOf(
                "-y",
                "-fflags", "+genpts",
                "-i", inputFile.absolutePath,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                outputMp4.absolutePath
            )
            if (runFfmpeg(aacFallback) && verifyOutputStreams(outputMp4, inStreams)) return true
        }

        // 尝试 4: 原生 MediaMuxer 兜底
        return remuxTsToMp4Native(inputFile, outputMp4)
    }

    private fun verifyOutputStreams(outFile: File, inStreams: Pair<Boolean, Boolean>): Boolean {
        if (!outFile.exists() || outFile.length() < 1024) return false
        val outStreams = probeStreamPresence(outFile)
        if (inStreams.first && !outStreams.first) return false
        if (inStreams.second && !outStreams.second) return false
        return outStreams.first || outStreams.second
    }

    private fun muxVideoAndAudioNative(videoFile: File, audioFile: File, outputMp4: File): Boolean {
        var muxer: MediaMuxer? = null
        val vExtractor = MediaExtractor()
        val aExtractor = MediaExtractor()
        return try {
            if (outputMp4.exists()) outputMp4.delete()
            vExtractor.setDataSource(videoFile.absolutePath)
            aExtractor.setDataSource(audioFile.absolutePath)

            val vTrackIdx = findTrackIndex(vExtractor, "video/")
            val aTrackIdx = findTrackIndex(aExtractor, "audio/")
            if (vTrackIdx < 0) return false

            muxer = MediaMuxer(outputMp4.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
            vExtractor.selectTrack(vTrackIdx)
            val muxVideoTrack = muxer.addTrack(vExtractor.getTrackFormat(vTrackIdx))

            var muxAudioTrack = -1
            if (aTrackIdx >= 0) {
                aExtractor.selectTrack(aTrackIdx)
                try {
                    muxAudioTrack = muxer.addTrack(aExtractor.getTrackFormat(aTrackIdx))
                } catch (_: Exception) {
                    muxAudioTrack = -1
                }
            }
            if (muxAudioTrack < 0 && audioFile.length() > 1024) return false

            muxer.start()
            copyTrackSamples(vExtractor, muxer, muxVideoTrack)
            if (muxAudioTrack >= 0) {
                copyTrackSamples(aExtractor, muxer, muxAudioTrack)
            }
            outputMp4.exists() && outputMp4.length() > 1024
        } catch (_: Exception) {
            false
        } finally {
            try { vExtractor.release() } catch (_: Exception) {}
            try { aExtractor.release() } catch (_: Exception) {}
            try { muxer?.stop() } catch (_: Exception) {}
            try { muxer?.release() } catch (_: Exception) {}
        }
    }

    private fun remuxTsToMp4Native(tsFile: File, outputMp4: File): Boolean {
        var muxer: MediaMuxer? = null
        val extractor = MediaExtractor()
        return try {
            if (outputMp4.exists()) outputMp4.delete()
            extractor.setDataSource(tsFile.absolutePath)
            val trackCount = extractor.trackCount
            if (trackCount <= 0) return false

            muxer = MediaMuxer(outputMp4.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
            val trackMap = mutableMapOf<Int, Int>()
            var hadInputAudio = false
            var keptAudioTrack = false
            for (i in 0 until trackCount) {
                val fmt = extractor.getTrackFormat(i)
                val mime = fmt.getString(MediaFormat.KEY_MIME) ?: continue
                if (mime.startsWith("audio/")) hadInputAudio = true
                if (mime.startsWith("video/") || mime.startsWith("audio/")) {
                    try {
                        val added = muxer.addTrack(fmt)
                        extractor.selectTrack(i)
                        trackMap[i] = added
                        if (mime.startsWith("audio/")) keptAudioTrack = true
                    } catch (_: Exception) {}
                }
            }
            if (trackMap.isEmpty()) return false
            if (hadInputAudio && !keptAudioTrack) return false

            muxer.start()
            val buffer = ByteBuffer.allocate(1024 * 1024)
            val bufferInfo = MediaCodec.BufferInfo()
            val lastPtsByTrack = mutableMapOf<Int, Long>()

            while (true) {
                val sampleTrack = extractor.sampleTrackIndex
                if (sampleTrack < 0) break
                val targetTrack = trackMap[sampleTrack]
                if (targetTrack == null) {
                    extractor.advance()
                    continue
                }
                buffer.clear()
                val sampleSize = extractor.readSampleData(buffer, 0)
                if (sampleSize < 0) break

                val prevPts = lastPtsByTrack[sampleTrack] ?: -1L
                var pts = extractor.sampleTime
                if (pts < 0L) pts = if (prevPts >= 0L) prevPts + 1L else 0L
                if (pts <= prevPts) pts = prevPts + 1L
                lastPtsByTrack[sampleTrack] = pts

                bufferInfo.offset = 0
                bufferInfo.size = sampleSize
                bufferInfo.presentationTimeUs = pts
                bufferInfo.flags = extractor.sampleFlags
                try {
                    muxer.writeSampleData(targetTrack, buffer, bufferInfo)
                } catch (_: Exception) {}
                extractor.advance()
            }
            outputMp4.exists() && outputMp4.length() > 1024
        } catch (_: Exception) {
            false
        } finally {
            try { extractor.release() } catch (_: Exception) {}
            try { muxer?.stop() } catch (_: Exception) {}
            try { muxer?.release() } catch (_: Exception) {}
        }
    }

    private fun findTrackIndex(extractor: MediaExtractor, prefix: String): Int {
        for (i in 0 until extractor.trackCount) {
            val mime = extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME) ?: ""
            if (mime.startsWith(prefix)) return i
        }
        return -1
    }

    private fun copyTrackSamples(extractor: MediaExtractor, muxer: MediaMuxer, dstTrack: Int) {
        val buffer = ByteBuffer.allocate(1024 * 1024)
        val info = MediaCodec.BufferInfo()
        var lastPts = -1L
        while (true) {
            buffer.clear()
            val size = extractor.readSampleData(buffer, 0)
            if (size < 0) break
            var pts = extractor.sampleTime
            if (pts < 0L) pts = if (lastPts >= 0L) lastPts + 1L else 0L
            if (pts <= lastPts) pts = lastPts + 1L
            lastPts = pts
            info.offset = 0
            info.size = size
            info.presentationTimeUs = pts
            info.flags = extractor.sampleFlags
            try {
                muxer.writeSampleData(dstTrack, buffer, info)
            } catch (_: Exception) {}
            extractor.advance()
        }
    }

    fun exportToPublicDownloads(context: Context, sourceFile: File, subFolder: String): String {
        if (!sourceFile.exists()) return ""
        val ext = sourceFile.extension.lowercase()
        val isAudio = ext in listOf("mp3", "m4a", "aac", "flac", "wav", "ogg", "opus")
        val isVideo = ext in listOf("mp4", "ts", "mkv", "webm", "flv", "mov", "avi")
        val mime = when (ext) {
            "mp4" -> "video/mp4"
            "mkv" -> "video/x-matroska"
            "webm" -> "video/webm"
            "ts" -> "video/mp2t"
            "m4a", "aac" -> "audio/mp4"
            "mp3" -> "audio/mpeg"
            "flac" -> "audio/flac"
            "pdf" -> "application/pdf"
            "zip" -> "application/zip"
            "apk" -> "application/vnd.android.package-archive"
            else -> if (isAudio) "audio/*" else if (isVideo) "video/*" else "application/octet-stream"
        }

        val customUriStr = AppConfig.customSaveUri
        if (customUriStr.isNotBlank()) {
            try {
                val treeUri = Uri.parse(customUriStr)
                var targetDir = DocumentFile.fromTreeUri(context, treeUri)
                if (targetDir != null && targetDir.canWrite()) {
                    if (subFolder.isNotBlank()) {
                        val existing = targetDir.findFile(subFolder)
                        targetDir = if (existing != null && existing.isDirectory) existing
                        else targetDir.createDirectory(subFolder) ?: targetDir
                    }
                    targetDir.findFile(sourceFile.name)?.delete()
                    val docFile = targetDir.createFile(mime, sourceFile.name)
                    if (docFile != null) {
                        context.contentResolver.openOutputStream(docFile.uri)?.use { out ->
                            FileInputStream(sourceFile).use { inp -> inp.copyTo(out) }
                        }
                        return docFile.uri.toString()
                    }
                }
            } catch (_: Exception) {}
        }

        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val baseDir = when {
                    isAudio -> Environment.DIRECTORY_MUSIC
                    isVideo -> Environment.DIRECTORY_MOVIES
                    else -> Environment.DIRECTORY_DOWNLOADS
                }
                val relPath = if (subFolder.isNotBlank()) "$baseDir/StarStream/$subFolder" else "$baseDir/StarStream"
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, sourceFile.name)
                    put(MediaStore.MediaColumns.MIME_TYPE, mime)
                    put(MediaStore.MediaColumns.RELATIVE_PATH, relPath)
                    put(MediaStore.MediaColumns.IS_PENDING, 1)
                }
                val collection = when {
                    isAudio -> MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
                    isVideo -> MediaStore.Video.Media.EXTERNAL_CONTENT_URI
                    else -> MediaStore.Downloads.EXTERNAL_CONTENT_URI
                }
                val uri = context.contentResolver.insert(collection, values) ?: return ""
                context.contentResolver.openOutputStream(uri)?.use { out ->
                    FileInputStream(sourceFile).use { inp -> inp.copyTo(out) }
                }
                values.clear()
                values.put(MediaStore.MediaColumns.IS_PENDING, 0)
                context.contentResolver.update(uri, values, null, null)
                uri.toString()
            } else {
                val root = Environment.getExternalStoragePublicDirectory(
                    if (isAudio) Environment.DIRECTORY_MUSIC else Environment.DIRECTORY_MOVIES
                )
                val destDir = if (subFolder.isNotBlank()) File(root, "StarStream/$subFolder") else File(root, "StarStream")
                destDir.mkdirs()
                val destFile = File(destDir, sourceFile.name)
                sourceFile.copyTo(destFile, overwrite = true)
                destFile.absolutePath
            }
        } catch (_: Exception) {
            ""
        }
    }

    fun deleteExportedFile(context: Context, exportedUriOrPath: String) {
        if (exportedUriOrPath.isBlank()) return
        try {
            if (exportedUriOrPath.startsWith("content://")) {
                val uri = Uri.parse(exportedUriOrPath)
                val doc = DocumentFile.fromSingleUri(context, uri)
                if (doc != null && doc.exists() && doc.delete()) return
                context.contentResolver.delete(uri, null, null)
            } else {
                File(exportedUriOrPath).delete()
            }
        } catch (_: Exception) {}
    }

    fun renameExportedFile(context: Context, exportedUriOrPath: String, newFileNameWithExt: String): String {
        if (exportedUriOrPath.isBlank()) return ""
        try {
            if (exportedUriOrPath.startsWith("content://")) {
                val uri = Uri.parse(exportedUriOrPath)
                val doc = DocumentFile.fromSingleUri(context, uri)
                if (doc != null && doc.renameTo(newFileNameWithExt)) {
                    return doc.uri.toString()
                }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    val cv = ContentValues().apply {
                        put(MediaStore.MediaColumns.DISPLAY_NAME, newFileNameWithExt)
                    }
                    context.contentResolver.update(uri, cv, null, null)
                    return exportedUriOrPath
                }
            } else {
                val oldF = File(exportedUriOrPath)
                if (oldF.exists()) {
                    val newF = File(oldF.parentFile, newFileNameWithExt)
                    if (oldF.renameTo(newF)) return newF.absolutePath
                }
            }
        } catch (_: Exception) {}
        return exportedUriOrPath
    }
}

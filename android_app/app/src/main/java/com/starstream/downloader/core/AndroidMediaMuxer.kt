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
import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer

/**
 * 安卓原生硬件级媒体处理引擎 (MediaExtractor + MediaMuxer)
 * 修复要点：
 * 1. TS -> MP4 按音视频轨分别维持单调递增 PTS，避免分片边界 PTS 回跳丢音轨
 * 2. 若输入 TS 含音频但输出未能兼容封装音轨，返回 false 回退保留原 TS 保证有声音
 * 3. 支持导出到用户自定义的 SAF 文件夹，或系统公共 Movies/Music/Downloads
 */
object AndroidMediaMuxer {

    fun muxVideoAndAudio(videoFile: File, audioFile: File, outputMp4: File): Boolean {
        if (!videoFile.exists() || !audioFile.exists()) return false
        var muxer: MediaMuxer? = null
        val vExtractor = MediaExtractor()
        val aExtractor = MediaExtractor()
        return try {
            vExtractor.setDataSource(videoFile.absolutePath)
            aExtractor.setDataSource(audioFile.absolutePath)

            val vTrackIdx = findTrackIndex(vExtractor, "video/")
            val aTrackIdx = findTrackIndex(aExtractor, "audio/")
            if (vTrackIdx < 0) return false

            muxer = MediaMuxer(outputMp4.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
            vExtractor.selectTrack(vTrackIdx)
            val vFormat = vExtractor.getTrackFormat(vTrackIdx)
            val muxVideoTrack = muxer.addTrack(vFormat)

            var muxAudioTrack = -1
            if (aTrackIdx >= 0) {
                aExtractor.selectTrack(aTrackIdx)
                val aFormat = aExtractor.getTrackFormat(aTrackIdx)
                try {
                    muxAudioTrack = muxer.addTrack(aFormat)
                } catch (_: Exception) {
                    muxAudioTrack = -1
                }
            }
            if (muxAudioTrack < 0 && audioFile.length() > 1024) {
                // 避免输出纯无声视频，返回 false 让上层保留可用反馈或报错
                return false
            }

            muxer.start()
            copyTrackSamples(vExtractor, muxer, muxVideoTrack)
            if (muxAudioTrack >= 0) {
                copyTrackSamples(aExtractor, muxer, muxAudioTrack)
            }
            outputMp4.exists() && outputMp4.length() > 1024
        } catch (e: Exception) {
            e.printStackTrace()
            false
        } finally {
            try { vExtractor.release() } catch (_: Exception) {}
            try { aExtractor.release() } catch (_: Exception) {}
            try { muxer?.stop() } catch (_: Exception) {}
            try { muxer?.release() } catch (_: Exception) {}
        }
    }

    fun remuxTsToMp4(tsFile: File, outputMp4: File): Boolean {
        if (!tsFile.exists() || tsFile.length() == 0L) return false
        var muxer: MediaMuxer? = null
        val extractor = MediaExtractor()
        return try {
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
            // 若原流有声音但 MediaMuxer 无法封装其音频编码，宁愿保留原 .ts 也不产出静音 MP4
            if (hadInputAudio && !keptAudioTrack) return false

            muxer.start()
            val bufferSize = 1024 * 1024
            val buffer = ByteBuffer.allocate(bufferSize)
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
        } catch (e: Exception) {
            e.printStackTrace()
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
            muxer.writeSampleData(dstTrack, buffer, info)
            extractor.advance()
        }
    }

    fun exportToPublicDownloads(context: Context, sourceFile: File, subFolder: String): String {
        if (!sourceFile.exists()) return sourceFile.absolutePath
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

        // 1. 优先导出到用户自定义的 SAF 存储目录
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

        // 2. 回退到系统标准 MediaStore 目录
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
                val uri = context.contentResolver.insert(collection, values) ?: return sourceFile.absolutePath
                context.contentResolver.openOutputStream(uri)?.use { out ->
                    FileInputStream(sourceFile).use { inp -> inp.copyTo(out) }
                }
                values.clear()
                values.put(MediaStore.MediaColumns.IS_PENDING, 0)
                context.contentResolver.update(uri, values, null, null)
                "$relPath/${sourceFile.name}"
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
            sourceFile.absolutePath
        }
    }
}

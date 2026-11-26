package com.starstream.downloader

import android.app.Application
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter

class StarStreamApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                val sw = StringWriter()
                throwable.printStackTrace(PrintWriter(sw))
                val crashFile = File(filesDir, "last_crash.txt")
                crashFile.writeText("${throwable.javaClass.simpleName}: ${throwable.message}\n\n$sw")
            } catch (_: Throwable) {
            }
            defaultHandler?.uncaughtException(thread, throwable)
        }
    }
}

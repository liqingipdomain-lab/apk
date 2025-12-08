package com.yurap.securedataapp

import android.app.Application
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

class SecureApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val request = PeriodicWorkRequestBuilder<SyncWorker>(12, TimeUnit.HOURS).build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork("secure_sync", ExistingPeriodicWorkPolicy.UPDATE, request)
    }
}

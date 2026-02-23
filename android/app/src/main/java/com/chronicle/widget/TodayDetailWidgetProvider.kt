package com.chronicle.widget

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context

class TodayDetailWidgetProvider : AppWidgetProvider() {
    override fun onEnabled(context: Context) {
        super.onEnabled(context)
        WidgetScheduler.schedulePeriodic(context)
        WidgetScheduler.enqueueOnDemandRefresh(context)
    }

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
    ) {
        WidgetRenderService.render(context, PlanTodayRepository.getCached(context))
        WidgetScheduler.enqueueOnDemandRefresh(context)
    }
}

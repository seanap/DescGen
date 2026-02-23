package com.chronicle.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.view.View
import android.widget.RemoteViews
import java.text.DecimalFormat

object WidgetRenderService {
    private val milesFormat = DecimalFormat("0.#")

    fun render(context: Context, model: PlanToday?) {
        renderMilesWidget(context, model)
        renderDetailWidget(context, model)
    }

    private fun renderMilesWidget(context: Context, model: PlanToday?) {
        val manager = AppWidgetManager.getInstance(context)
        val ids = manager.getAppWidgetIds(ComponentName(context, MilesWidgetProvider::class.java))
        if (ids.isEmpty()) return

        val milesText = model?.let { milesFormat.format(it.miles) } ?: "--"
        val views = RemoteViews(context.packageName, R.layout.widget_miles)
        views.setTextViewText(R.id.miles_value_halo, milesText)
        views.setTextViewText(R.id.miles_value, milesText)
        views.setOnClickPendingIntent(R.id.widget_miles_root, openPlanPendingIntent(context))
        manager.updateAppWidget(ids, views)
    }

    private fun renderDetailWidget(context: Context, model: PlanToday?) {
        val manager = AppWidgetManager.getInstance(context)
        val ids = manager.getAppWidgetIds(ComponentName(context, TodayDetailWidgetProvider::class.java))
        if (ids.isEmpty()) return

        val views = RemoteViews(context.packageName, R.layout.widget_plan_today)
        views.setTextViewText(R.id.detail_miles_value, model?.let { milesFormat.format(it.miles) } ?: "--")
        views.setTextViewText(R.id.detail_run_type_value, model?.runType?.ifBlank { "--" } ?: "--")
        val workout = model?.workoutShorthand.orEmpty().trim()
        if (workout.isEmpty()) {
            views.setViewVisibility(R.id.detail_workout_row, View.GONE)
        } else {
            views.setViewVisibility(R.id.detail_workout_row, View.VISIBLE)
            views.setTextViewText(R.id.detail_workout_value, workout)
        }

        views.setOnClickPendingIntent(R.id.widget_detail_root, openPlanPendingIntent(context))
        views.setOnClickPendingIntent(R.id.detail_refresh_button, refreshPendingIntent(context))
        manager.updateAppWidget(ids, views)
    }

    private fun openPlanPendingIntent(context: Context): PendingIntent {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(ConfigStore.planPageUrl(context)))
        return PendingIntent.getActivity(
            context,
            2001,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun refreshPendingIntent(context: Context): PendingIntent {
        val intent = Intent(context, WidgetActionReceiver::class.java).apply {
            action = Constants.ACTION_REFRESH
        }
        return PendingIntent.getBroadcast(
            context,
            2002,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }
}

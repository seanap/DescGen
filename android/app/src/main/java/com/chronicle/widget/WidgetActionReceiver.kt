package com.chronicle.widget

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class WidgetActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Constants.ACTION_REFRESH) {
            WidgetScheduler.enqueueOnDemandRefresh(context)
        }
    }
}

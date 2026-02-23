package com.chronicle.widget

object Constants {
    const val PREFS_NAME = "chronicle_widget_prefs"
    const val KEY_BASE_URL = "base_url"
    const val KEY_LAST_JSON = "last_plan_today_json"
    const val KEY_LAST_SYNC_MS = "last_sync_ms"

    const val DEFAULT_BASE_URL = "http://10.0.2.2:8777"

    const val ACTION_REFRESH = "com.chronicle.widget.action.REFRESH"

    const val UNIQUE_PERIODIC_WORK = "chronicle_widget_periodic_refresh"
    const val UNIQUE_ON_DEMAND_WORK = "chronicle_widget_on_demand_refresh"
}

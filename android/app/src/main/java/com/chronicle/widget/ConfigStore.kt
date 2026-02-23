package com.chronicle.widget

import android.content.Context

object ConfigStore {
    private fun prefs(context: Context) =
        context.getSharedPreferences(Constants.PREFS_NAME, Context.MODE_PRIVATE)

    fun getBaseUrl(context: Context): String {
        val raw = prefs(context).getString(Constants.KEY_BASE_URL, Constants.DEFAULT_BASE_URL)
        return sanitizeBaseUrl(raw)
    }

    fun setBaseUrl(context: Context, value: String) {
        prefs(context).edit().putString(Constants.KEY_BASE_URL, sanitizeBaseUrl(value)).apply()
    }

    fun planPageUrl(context: Context): String = getBaseUrl(context).trimEnd('/') + "/plan"

    fun planTodayUrl(context: Context): String = getBaseUrl(context).trimEnd('/') + "/plan/today.json"

    private fun sanitizeBaseUrl(value: String?): String {
        val trimmed = value?.trim().orEmpty()
        if (trimmed.isEmpty()) return Constants.DEFAULT_BASE_URL
        val withScheme = if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            trimmed
        } else {
            "http://$trimmed"
        }
        return withScheme.trimEnd('/')
    }
}

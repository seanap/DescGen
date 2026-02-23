package com.chronicle.widget

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.time.LocalDate

object PlanTodayRepository {
    private val client = OkHttpClient()

    private fun prefs(context: Context) =
        context.getSharedPreferences(Constants.PREFS_NAME, Context.MODE_PRIVATE)

    fun getCached(context: Context): PlanToday? {
        val raw = prefs(context).getString(Constants.KEY_LAST_JSON, null) ?: return null
        return parse(raw)
    }

    suspend fun refresh(context: Context): Result<PlanToday> = withContext(Dispatchers.IO) {
        runCatching {
            val request = Request.Builder()
                .url(ConfigStore.planTodayUrl(context))
                .get()
                .build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    error("HTTP ${response.code}")
                }
                val body = response.body?.string()?.trim().orEmpty()
                if (body.isEmpty()) {
                    error("Empty response body")
                }
                val model = parse(body) ?: error("Invalid /plan/today.json payload")
                prefs(context).edit()
                    .putString(Constants.KEY_LAST_JSON, body)
                    .putLong(Constants.KEY_LAST_SYNC_MS, System.currentTimeMillis())
                    .apply()
                model
            }
        }
    }

    private fun parse(raw: String): PlanToday? {
        return runCatching {
            val obj = JSONObject(raw)
            val dateLocal = obj.optString("date_local").takeIf { it.isNotBlank() }
                ?: LocalDate.now().toString()
            val runType = obj.optString("run_type", "")
            val miles = when {
                obj.has("miles") -> obj.optDouble("miles", 0.0)
                else -> 0.0
            }
            val workout = obj.optString("workout_shorthand", "").trim().ifBlank { null }
            PlanToday(
                dateLocal = dateLocal,
                runType = runType,
                miles = if (miles.isFinite()) miles else 0.0,
                workoutShorthand = workout,
            )
        }.getOrNull()
    }
}

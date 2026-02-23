package com.chronicle.widget

data class PlanToday(
    val dateLocal: String,
    val runType: String,
    val miles: Double,
    val workoutShorthand: String?,
)

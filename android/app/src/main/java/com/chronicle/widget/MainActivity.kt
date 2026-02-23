package com.chronicle.widget

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        WidgetScheduler.schedulePeriodic(this)

        val baseUrlInput = findViewById<EditText>(R.id.base_url_input)
        val saveButton = findViewById<Button>(R.id.save_base_url_button)
        val refreshButton = findViewById<Button>(R.id.refresh_now_button)
        val openPlanButton = findViewById<Button>(R.id.open_plan_button)

        baseUrlInput.setText(ConfigStore.getBaseUrl(this))

        saveButton.setOnClickListener {
            ConfigStore.setBaseUrl(this, baseUrlInput.text?.toString().orEmpty())
            WidgetScheduler.enqueueOnDemandRefresh(this)
            Toast.makeText(this, R.string.settings_saved, Toast.LENGTH_SHORT).show()
        }

        refreshButton.setOnClickListener {
            WidgetScheduler.enqueueOnDemandRefresh(this)
            Toast.makeText(this, R.string.refresh_queued, Toast.LENGTH_SHORT).show()
        }

        openPlanButton.setOnClickListener {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(ConfigStore.planPageUrl(this)))
            startActivity(intent)
        }
    }
}

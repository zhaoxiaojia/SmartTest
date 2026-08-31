package com.smarttest.mobile

import android.content.Intent
import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.appcompat.app.AppCompatActivity
import com.smarttest.mobile.runner.SmartTestRunStore
import com.smarttest.mobile.settings.AppSettingsStore
import com.smarttest.mobile.ui.screens.SmartTestPrototypeApp

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        AppSettingsStore.initialize(this)
        AppSettingsStore.applyStoredLanguage()
        SmartTestRunStore.initialize(this)
        super.onCreate(savedInstanceState)
        setContent {
            SmartTestPrototypeApp()
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
    }
}

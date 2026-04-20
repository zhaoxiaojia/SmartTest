package com.smarttest.mobile

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.appcompat.app.AppCompatActivity
import com.smarttest.mobile.settings.AppSettingsStore
import com.smarttest.mobile.ui.screens.SmartTestPrototypeApp

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        AppSettingsStore.initialize(this)
        AppSettingsStore.applyStoredLanguage()
        super.onCreate(savedInstanceState)
        setContent {
            SmartTestPrototypeApp()
        }
    }
}

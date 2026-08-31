package com.smarttest.mobile.settings

import android.content.Context
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

enum class ThemePreference {
    System,
    Light,
    Dark,
}

enum class LanguagePreference(
    val languageTag: String,
) {
    System(""),
    English("en"),
    SimplifiedChinese("zh-CN"),
}

data class AppSettingsState(
    val themePreference: ThemePreference = ThemePreference.System,
    val languagePreference: LanguagePreference = LanguagePreference.System,
)

object AppSettingsStore {
    private const val PREF_NAME = "smarttest_app_settings"
    private const val KEY_THEME = "theme"
    private const val KEY_LANGUAGE = "language"

    private val mutableState = MutableStateFlow(AppSettingsState())
    val state: StateFlow<AppSettingsState> = mutableState.asStateFlow()

    fun initialize(context: Context) {
        val preferences = context.applicationContext.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        mutableState.value = AppSettingsState(
            themePreference = preferences.getString(KEY_THEME, null).toThemePreference(),
            languagePreference = preferences.getString(KEY_LANGUAGE, null).toLanguagePreference(),
        )
    }

    fun updateTheme(context: Context, themePreference: ThemePreference) {
        persist(
            context = context,
            key = KEY_THEME,
            value = themePreference.name,
        )
        mutableState.update { it.copy(themePreference = themePreference) }
    }

    fun updateLanguage(context: Context, languagePreference: LanguagePreference) {
        persist(
            context = context,
            key = KEY_LANGUAGE,
            value = languagePreference.name,
        )
        mutableState.update { it.copy(languagePreference = languagePreference) }
        applyLanguage(languagePreference)
    }

    fun applyStoredLanguage() {
        applyLanguage(mutableState.value.languagePreference)
    }

    private fun persist(
        context: Context,
        key: String,
        value: String,
    ) {
        context.applicationContext
            .getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(key, value)
            .apply()
    }

    private fun applyLanguage(languagePreference: LanguagePreference) {
        val locales = if (languagePreference == LanguagePreference.System) {
            LocaleListCompat.getEmptyLocaleList()
        } else {
            LocaleListCompat.forLanguageTags(languagePreference.languageTag)
        }
        AppCompatDelegate.setApplicationLocales(locales)
    }
}

private fun String?.toThemePreference(): ThemePreference {
    return ThemePreference.entries.firstOrNull { it.name == this } ?: ThemePreference.System
}

private fun String?.toLanguagePreference(): LanguagePreference {
    return LanguagePreference.entries.firstOrNull { it.name == this } ?: LanguagePreference.System
}

package com.smarttest.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.microsoft.fluentui.theme.token.controlTokens.ButtonStyle
import com.microsoft.fluentui.theme.token.controlTokens.CardType
import com.microsoft.fluentui.tokenized.controls.BasicCard
import com.microsoft.fluentui.tokenized.controls.Button
import com.smarttest.mobile.R
import com.smarttest.mobile.settings.LanguagePreference
import com.smarttest.mobile.settings.ThemePreference

@Composable
fun SettingsPanel(
    modifier: Modifier = Modifier,
    themePreference: ThemePreference,
    languagePreference: LanguagePreference,
    onThemeChange: (ThemePreference) -> Unit,
    onLanguageChange: (LanguagePreference) -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxHeight()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        SettingsOptionCard(
            title = stringResource(R.string.settings_theme_title),
            summary = stringResource(R.string.settings_theme_summary),
            options = listOf(
                ThemePreference.System to stringResource(R.string.theme_system),
                ThemePreference.Light to stringResource(R.string.theme_light),
                ThemePreference.Dark to stringResource(R.string.theme_dark),
            ),
            selected = themePreference,
            onSelect = onThemeChange,
        )
        SettingsOptionCard(
            title = stringResource(R.string.settings_language_title),
            summary = stringResource(R.string.settings_language_summary),
            options = listOf(
                LanguagePreference.System to stringResource(R.string.language_system),
                LanguagePreference.English to stringResource(R.string.language_english),
                LanguagePreference.SimplifiedChinese to stringResource(R.string.language_simplified_chinese),
            ),
            selected = languagePreference,
            onSelect = onLanguageChange,
        )
    }
}

@Composable
private fun <T> SettingsOptionCard(
    title: String,
    summary: String,
    options: List<Pair<T, String>>,
    selected: T,
    onSelect: (T) -> Unit,
) {
    BasicCard(
        modifier = Modifier.fillMaxWidth(),
        cardType = CardType.Elevated,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = summary,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                options.forEach { (value, label) ->
                    Button(
                        onClick = { onSelect(value) },
                        text = label,
                        modifier = Modifier.weight(1f),
                        style = if (value == selected) ButtonStyle.Button else ButtonStyle.OutlinedButton,
                    )
                }
            }
        }
    }
}

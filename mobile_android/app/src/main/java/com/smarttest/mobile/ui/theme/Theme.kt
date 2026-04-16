package com.smarttest.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = SmartBlue,
    onPrimary = Grey10,
    primaryContainer = SmartBlueLight.copy(alpha = 0.24f),
    background = Grey10,
    surface = androidx.compose.ui.graphics.Color.White,
    onSurface = Grey160,
    onSurfaceVariant = Grey120,
)

private val DarkColors = darkColorScheme(
    primary = SmartBlueLight,
    onPrimary = Grey190,
    primaryContainer = SmartBlueDark,
    background = Grey190,
    surface = Grey160,
    onSurface = Grey10,
    onSurfaceVariant = Grey30,
)

@Composable
fun SmartTestMobileTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors

    MaterialTheme(
        colorScheme = colors,
        typography = SmartTypography,
        shapes = SmartShapes,
        content = content,
    )
}


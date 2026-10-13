package au.mainspring.nativeapp.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.TextStyle
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.Color

/**
 * Atelier theme: ink navy on a pale blue-grey ground with one blue accent, white 24dp cards,
 * 14dp controls. [AppAppearance.WARM] is the Atelier light palette (kept as the enum name so stored
 * preferences and tests keep working); NIGHT is the same palette in a dark workshop mode.
 */
@Composable
fun MainspringTheme(darkTheme: Boolean? = null, content: @Composable () -> Unit) {
    val appearance by DesignPreferences.appearance.collectAsState()
    val night = darkTheme ?: (appearance == AppAppearance.NIGHT)
    var colors = if (night) darkColorScheme(
        primary = Color(0xFF7FA2FF), onPrimary = Color(0xFF0A1530),
        background = Color(0xFF0E141D), surface = Color(0xFF18212D), onSurface = Color(0xFFEDF1F8),
        onBackground = Color(0xFFEDF1F8), secondary = Color(0xFF243247), onSecondary = Color(0xFFEDF1F8),
        primaryContainer = Color(0xFF1D2F5C), onPrimaryContainer = Color(0xFFD9E3FF),
        secondaryContainer = Color(0xFF2A3546), onSecondaryContainer = Color(0xFFE3E8F2),
        surfaceVariant = Color(0xFF263041), onSurfaceVariant = Color(0xFFA8B4C7),
        surfaceContainerLowest = Color(0xFF0B1118), surfaceContainerLow = Color(0xFF141C27),
        surfaceContainer = Color(0xFF18212D), surfaceContainerHigh = Color(0xFF202B3A), surfaceContainerHighest = Color(0xFF283446),
        outline = Color(0xFF6F7C90), outlineVariant = Color(0xFF2A3546),
        error = Color(0xFFFFB4AB), errorContainer = Color(0xFF4A1F1B), onErrorContainer = Color(0xFFFFDAD6))
    else lightColorScheme(
        primary = Color(0xFF2453D4), onPrimary = Color.White,
        background = Color(0xFFF1F4F9), surface = Color.White, onSurface = Color(0xFF17202C),
        onBackground = Color(0xFF17202C), secondary = Color(0xFF17202C), onSecondary = Color(0xFFF1F4F9),
        primaryContainer = Color(0xFFE3EBFC), onPrimaryContainer = Color(0xFF15307A),
        secondaryContainer = Color(0xFFE4E9F2), onSecondaryContainer = Color(0xFF17202C),
        surfaceVariant = Color(0xFFE8EDF5), onSurfaceVariant = Color(0xFF566479),
        surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFF7F9FC),
        surfaceContainer = Color(0xFFF1F4F9), surfaceContainerHigh = Color(0xFFE8EDF5), surfaceContainerHighest = Color.White,
        outline = Color(0xFF8793A6), outlineVariant = Color(0xFFDDE3EE),
        error = Color(0xFFB3261E), errorContainer = Color(0xFFFCE4E1), onErrorContainer = Color(0xFF601410))
    if(!night) colors = when(appearance) {
        AppAppearance.STEEL -> colors.copy(primary = Color(0xFFB67519), background = Color(0xFFF2F3F3), secondaryContainer = Color(0xFFE1E5E7))
        AppAppearance.MINIT -> colors.copy(primary = Color(0xFFE9143C), background = Color(0xFFF5F5F6), secondary = Color(0xFF26368E))
        else -> colors
    }
    val baseline = Typography()
    fun style(base: TextStyle, size: Int, line: Int, weight: FontWeight, spacing: Double = 0.0) =
        base.copy(fontSize = size.sp, lineHeight = line.sp, fontWeight = weight, letterSpacing = spacing.sp)
    MaterialTheme(
        colorScheme = colors,
        typography = baseline.copy(
            headlineLarge = style(baseline.headlineLarge, 34, 41, FontWeight.Bold),
            headlineMedium = style(baseline.headlineMedium, 28, 34, FontWeight.Bold),
            headlineSmall = style(baseline.headlineSmall, 24, 29, FontWeight.SemiBold),
            titleLarge = style(baseline.titleLarge, 22, 28, FontWeight.SemiBold),
            titleMedium = style(baseline.titleMedium, 17, 22, FontWeight.SemiBold),
            titleSmall = style(baseline.titleSmall, 15, 20, FontWeight.SemiBold),
            bodyLarge = style(baseline.bodyLarge, 16, 22, FontWeight.Normal),
            bodyMedium = style(baseline.bodyMedium, 15, 21, FontWeight.Normal),
            bodySmall = style(baseline.bodySmall, 13, 18, FontWeight.Normal),
            labelLarge = style(baseline.labelLarge, 15, 20, FontWeight.SemiBold),
            labelMedium = style(baseline.labelMedium, 12, 17, FontWeight.Medium),
            labelSmall = style(baseline.labelSmall, 11, 15, FontWeight.Medium, 0.6),
        ),
        shapes = Shapes(
            extraSmall = RoundedCornerShape(10.dp), small = RoundedCornerShape(14.dp),
            medium = RoundedCornerShape(24.dp), large = RoundedCornerShape(24.dp),
            extraLarge = RoundedCornerShape(28.dp),
        ),
        content = content,
    )
}

package au.mainspring.nativeapp.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.Color

@Composable
fun MainspringTheme(darkTheme: Boolean? = null, content: @Composable () -> Unit) {
    val appearance by DesignPreferences.appearance.collectAsState()
    val night = darkTheme ?: (appearance == AppAppearance.NIGHT)
    var colors = if (night) darkColorScheme(
        primary = Color(0xFFFF5638), onPrimary = Color(0xFF121110),
        background = Color(0xFF121110), surface = Color(0xFF1C1A18), onSurface = Color(0xFFF0EAE0),
        onBackground = Color(0xFFF0EAE0), secondary = Color(0xFFD2C6B4),
        primaryContainer = Color(0xFF5C2018), onPrimaryContainer = Color(0xFFFFDAD2),
        secondaryContainer = Color(0xFF303038), onSecondaryContainer = Color(0xFFE3E4E9),
        surfaceVariant = Color(0xFF37322E), onSurfaceVariant = Color(0xFFCCC5BE),
        surfaceContainerLowest = Color(0xFF100E0D), surfaceContainerLow = Color(0xFF201D1A),
        surfaceContainer = Color(0xFF27231F), surfaceContainerHigh = Color(0xFF302B26), surfaceContainerHighest = Color(0xFF3B352F),
        outline = Color(0xFF938B84), outlineVariant = Color(0xFF514B45))
    else lightColorScheme(primary = Color(0xFFD92E12), onPrimary = Color.White,
        background = Color(0xFFF1EEE7), surface = Color.White, onSurface = Color(0xFF171715),
        onBackground = Color(0xFF171715), secondary = Color(0xFF242420),
        primaryContainer = Color(0xFFFFE7E1), onPrimaryContainer = Color(0xFF641A0E),
        secondaryContainer = Color(0xFFE9E5DD), onSecondaryContainer = Color(0xFF242420),
        surfaceVariant = Color(0xFFECE8E0), onSurfaceVariant = Color(0xFF6B6A63),
        surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFF8F6F1),
        surfaceContainer = Color(0xFFF1EEE7), surfaceContainerHigh = Color(0xFFECE8E0), surfaceContainerHighest = Color.White,
        outline = Color(0xFF807E76), outlineVariant = Color(0xFFDEDAD1))
    if(!night) colors = when(appearance) {
        AppAppearance.STEEL -> colors.copy(primary = Color(0xFFB67519), onPrimary = Color.White,
            background = Color(0xFFF2F3F3), secondaryContainer = Color(0xFFE1E5E7))
        AppAppearance.MINIT -> colors.copy(primary = Color(0xFFE9143C), onPrimary = Color.White,
            background = Color(0xFFF5F5F6), secondary = Color(0xFF26368E))
        else -> colors
    }
    val baseline = Typography()
    MaterialTheme(
        colorScheme = colors,
        typography = baseline.copy(
            headlineLarge = baseline.headlineLarge.copy(fontFamily = FontFamily.Serif),
            headlineMedium = baseline.headlineMedium.copy(fontFamily = FontFamily.Serif),
            headlineSmall = baseline.headlineSmall.copy(fontFamily = FontFamily.Serif, lineHeight = 30.sp),
            bodyMedium = baseline.bodyMedium.copy(lineHeight = 22.sp),
            bodySmall = baseline.bodySmall.copy(lineHeight = 19.sp),
            labelSmall = baseline.labelSmall.copy(letterSpacing = 0.5.sp),
            labelLarge = baseline.labelLarge.copy(fontWeight = FontWeight.SemiBold),
        ),
        shapes = Shapes(
            extraSmall = RoundedCornerShape(2.dp), small = RoundedCornerShape(2.dp),
            medium = RoundedCornerShape(4.dp), large = RoundedCornerShape(6.dp),
            extraLarge = RoundedCornerShape(12.dp),
        ),
        content = content,
    )
}

package au.mainspring.nativeapp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Light-mode (background, text) pairs; every pair is at least 7:1, well above WCAG AA. */
private val lightPairs = listOf(
    Color(0xFFE6EFE9) to Color(0xFF1F3D2F), // forest mint
    Color(0xFFDDE8DA) to Color(0xFF2B4A2E), // sage
    Color(0xFFEFE6D6) to Color(0xFF5A4318), // sand
    Color(0xFFF0DDD3) to Color(0xFF6B3A24), // clay
    Color(0xFFE4E8D0) to Color(0xFF3F4A17), // moss
    Color(0xFFE3E6E3) to Color(0xFF3A403B), // stone
)
private val darkPairs = listOf(
    Color(0xFF24382C) to Color(0xFFCFE6D8),
    Color(0xFF2A3A27) to Color(0xFFD3E6CF),
    Color(0xFF3A3222) to Color(0xFFEBDDBF),
    Color(0xFF3F2C23) to Color(0xFFF0D6C8),
    Color(0xFF343A1E) to Color(0xFFDFE5B8),
    Color(0xFF2E332F) to Color(0xFFDDE2DE),
)

/** "Sam Meyer" -> "SM"; "?" when the name is blank. */
fun initialsOf(name: String): String = name.split(' ').filter { it.isNotBlank() }.take(2).joinToString("") { it.take(1).uppercase() }.ifBlank { "?" }

/** Decorative initials circle tinted from a small green/earth palette by name hash; the name is always shown beside it, so it is hidden from TalkBack. */
@Composable fun InitialsAvatar(name: String, modifier: Modifier = Modifier, size: Dp = 44.dp) {
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val pairs = LocalCalibrePalette.current.avatars ?: if(dark) darkPairs else lightPairs
    val (bg, fg) = pairs[(name.trim().lowercase().hashCode() and Int.MAX_VALUE) % pairs.size]
    Box(modifier.size(size).clip(CircleShape).background(bg).clearAndSetSemantics { }, contentAlignment = Alignment.Center) {
        Text(initialsOf(name), style = MaterialTheme.typography.titleMedium.copy(fontSize = (size.value * 0.36f).sp, fontWeight = FontWeight.SemiBold), color = fg, maxLines = 1)
    }
}

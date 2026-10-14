package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import au.mainspring.nativeapp.R

/** True while the "Atelier / Calibre" appearance (white, forest green, hairlines, mono labels) is active. */
val LocalCalibre = staticCompositionLocalOf { false }

/** IBM Plex Mono (SIL OFL), used only for small uppercase labels and numbers in the Calibre appearance. */
val CalibreMono = FontFamily(Font(R.font.plexmono_regular, FontWeight.Normal), Font(R.font.plexmono_medium, FontWeight.Medium))

object Calibre {
    val Forest = Color(0xFF294D3C)
    val ForestMint = Color(0xFFE6EFE9)
    val Grey = Color(0xFFF3F3F3)
    val Hairline = Color(0xFFDADADA)
    val Ink = Color(0xFF1B1B1B)
    val Muted = Color(0xFF6A6A6A)
    val label = TextStyle(fontFamily = CalibreMono, fontWeight = FontWeight.Normal, fontSize = 11.sp, lineHeight = 15.sp, letterSpacing = 0.6.sp)
}

/** Small uppercase monospace caption, e.g. "REPAIR HISTORY / 4 VISITS". */
@Composable fun MonoLabel(text: String, modifier: Modifier = Modifier, color: Color = MaterialTheme.colorScheme.onSurfaceVariant) {
    Text(text.uppercase(), modifier, style = Calibre.label, color = color, maxLines = 2)
}

/** Three forest bars plus "atelier / calibre": the Calibre wordmark, with the shop name as a mono tag on the right. */
@Composable fun CalibreWordmark(shop: String?, modifier: Modifier = Modifier, trailing: (@Composable () -> Unit)? = null) {
    Row(modifier.fillMaxWidth().statusBarsPadding().padding(start = 20.dp, end = 20.dp, top = 14.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        androidx.compose.foundation.Canvas(Modifier.size(width = 20.dp, height = 22.dp)) {
            val bar = 3.dp.toPx(); val gap = 5.dp.toPx(); val c = Calibre.Forest
            drawRect(c, androidx.compose.ui.geometry.Offset(0f, size.height * 0.15f), androidx.compose.ui.geometry.Size(bar, size.height * 0.7f))
            drawRect(c, androidx.compose.ui.geometry.Offset(bar + gap, 0f), androidx.compose.ui.geometry.Size(bar, size.height))
            drawRect(c, androidx.compose.ui.geometry.Offset((bar + gap) * 2, size.height * 0.25f), androidx.compose.ui.geometry.Size(bar, size.height * 0.5f))
        }
        Spacer(Modifier.width(10.dp))
        Text("atelier / calibre", style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold), color = MaterialTheme.colorScheme.onSurface)
        Spacer(Modifier.weight(1f))
        if(shop != null) MonoLabel(shop.take(22))
        trailing?.invoke()
    }
}

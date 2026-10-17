package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.unit.Dp
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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

/** DM Serif Display (SIL OFL): warmer display face for Calibre titles and big numbers only. */
val CalibreDisplay = FontFamily(Font(R.font.dmserifdisplay_regular, FontWeight.Normal))

/** Instrument Serif (SIL OFL): the web display face, used for Mainspring titles and big numbers. */
val MainspringDisplay = FontFamily(Font(R.font.instrumentserif_regular, FontWeight.Normal))

/** Plus Jakarta Sans (SIL OFL, variable weight): the web body face for the Mainspring appearance. */
@OptIn(androidx.compose.ui.text.ExperimentalTextApi::class)
val MainspringBody = FontFamily(listOf(FontWeight.Normal, FontWeight.Medium, FontWeight.SemiBold, FontWeight.Bold).map {
    Font(R.font.plusjakartasans_variable, it, variationSettings = FontVariation.Settings(FontVariation.weight(it.weight)))
})

/** Status pill colours per tone (see [toneColors]). */
class TonePalette(val waiting: ToneColors, val ready: ToneColors, val progress: ToneColors, val late: ToneColors, val neutral: ToneColors)

/**
 * Colours and shape values that differ between Calibre-family appearances and are not expressible as Material roles.
 * [tones] and [avatars] null means "use the built-in Calibre defaults".
 */
class CalibrePalette(
    val appearance: AppAppearance,
    val dark: Boolean,
    val card: Color,
    val placeholder: Color,
    val displayFont: FontFamily,
    val cardRadius: Dp,
    val cardElevation: Dp,
    val wordmark: String,
    val tones: TonePalette? = null,
    val avatars: List<Pair<Color, Color>>? = null,
)

/** Pure palette selection: Mainspring is the web look (always light); Calibre is the green look and follows [dark]. */
fun calibrePaletteFor(appearance: AppAppearance, dark: Boolean): CalibrePalette = when(appearance) {
    AppAppearance.MAINSPRING -> CalibrePalette(appearance, false, card = Mainspring.Surface, placeholder = Mainspring.AccentLight,
        displayFont = MainspringDisplay, cardRadius = 6.dp, cardElevation = 0.dp, wordmark = "Mainspring",
        tones = TonePalette(
            waiting = ToneColors(Color(0xFFFFF4DB), Color(0xFF7A4A00), Color(0xFFD9930D)),
            ready = ToneColors(Color(0xFFE3F2E8), Color(0xFF1E5A33), Color(0xFF2E8B57)),
            progress = ToneColors(Color(0xFFE3EAF1), Color(0xFF2B4258), Color(0xFF4F7396)),
            late = ToneColors(Mainspring.AccentLight, Color(0xFF9B1C1C), Color(0xFFC62828)),
            neutral = ToneColors(Mainspring.SurfaceAlt, Mainspring.TextMid, Color(0xFF8A929A))),
        avatars = listOf(
            Mainspring.AccentLight to Color(0xFF8A2412), Color(0xFFFFF4DB) to Color(0xFF6B4100), Color(0xFFE3F2E8) to Color(0xFF1E5A33),
            Color(0xFFE3EAF1) to Color(0xFF2B4258), Mainspring.SurfaceAlt to Mainspring.TextMid, Color(0xFFF0DDD3) to Color(0xFF6B3A24)))
    else -> CalibrePalette(appearance, dark, card = Calibre.Tint, placeholder = if(dark) Calibre.DarkForestContainer else Calibre.ForestMint,
        displayFont = CalibreDisplay, cardRadius = 12.dp, cardElevation = 1.dp, wordmark = "atelier / calibre")
}

/** Provided by MainspringTheme. Defaults to light Calibre so previews and tests that skip the theme keep the old look. */
val LocalCalibrePalette = staticCompositionLocalOf { calibrePaletteFor(AppAppearance.CALIBRE, false) }

/** Web (Capacitor) design tokens from frontend/src/index.css. */
object Mainspring {
    val Background = Color(0xFFF6F7F9)
    val Surface = Color.White
    val SurfaceAlt = Color(0xFFEEF1F4)
    val Text = Color(0xFF12141A)
    val TextMid = Color(0xFF3C4249)
    val Muted = Color(0xFF596068)
    val Border = Color(0xFFE2E6EA)
    val BorderStrong = Color(0xFFC9CFD6)
    val Accent = Color(0xFFD2361B)
    val AccentHover = Color(0xFFB32D16)
    val AccentLight = Color(0xFFFDEAE6)
}

object Calibre {
    /** Very light green-grey card surface (Ink 16:1, Muted 5.7:1 on it). */
    val Tint = Color(0xFFF5F8F6)
    val Forest = Color(0xFF294D3C)
    val ForestMint = Color(0xFFE6EFE9)
    val Grey = Color(0xFFF3F3F3)
    val Hairline = Color(0xFFDADADA)
    val Ink = Color(0xFF1B1B1B)
    val Muted = Color(0xFF5F5F5F)  // 6.4:1 on white, 5.1:1 on the darkest Calibre surface (was 6A6A6A, 4.3:1 on E6E6E6)
    // Dark (system night) variants, used by the Calibre dark scheme in MainspringTheme.
    val ForestDark = Color(0xFF8FC4A3)
    val OnForestDark = Color(0xFF0B1A12)
    val DarkForestContainer = Color(0xFF1E3328)
    val DarkBackground = Color(0xFF111512)
    val DarkSurface = Color(0xFF1B201C)
    val DarkInk = Color(0xFFEEF2EE)
    val DarkMuted = Color(0xFFA9B1AB)
    val DarkHairline = Color(0xFF2E352F)
    val label = TextStyle(fontFamily = CalibreMono, fontWeight = FontWeight.Normal, fontSize = 11.sp, lineHeight = 15.sp, letterSpacing = 0.6.sp)
}

/** Soft card surface: light green-grey in light mode, the dark surface in night mode. */
@Composable fun calibreCardColor(): Color =
    if(MaterialTheme.colorScheme.background.luminance() < 0.5f) MaterialTheme.colorScheme.surfaceVariant else LocalCalibrePalette.current.card

/** Display-face variant of [base]: Instrument Serif for Mainspring, DM Serif Display for Calibre (both ship only a regular weight). */
@Composable fun calibreDisplayStyle(base: TextStyle): TextStyle = base.copy(fontFamily = LocalCalibrePalette.current.displayFont, fontWeight = FontWeight.Normal, letterSpacing = 0.sp)

/** Small uppercase monospace caption, e.g. "REPAIR HISTORY / 4 VISITS". */
@Composable fun MonoLabel(text: String, modifier: Modifier = Modifier, color: Color = MaterialTheme.colorScheme.onSurfaceVariant) {
    Text(text.uppercase(), modifier, style = Calibre.label, color = color, maxLines = 2)
}

/** Three forest bars plus "atelier / calibre": the Calibre wordmark, with the shop name as a mono tag on the right. */
@Composable fun CalibreWordmark(shop: String?, modifier: Modifier = Modifier, trailing: (@Composable () -> Unit)? = null) {
    val markColor = MaterialTheme.colorScheme.primary
    Row(modifier.fillMaxWidth().statusBarsPadding().padding(start = 20.dp, end = 20.dp, top = 14.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        if(LocalCalibrePalette.current.appearance == AppAppearance.MAINSPRING) androidx.compose.foundation.Canvas(Modifier.size(26.dp)) {
            val c = markColor; val r = size.minDimension / 2f; val ctr = center
            drawCircle(Mainspring.BorderStrong, r - 0.5.dp.toPx(), ctr, style = androidx.compose.ui.graphics.drawscope.Stroke(1.dp.toPx()))
            drawCircle(c, r * 0.62f, ctr, style = androidx.compose.ui.graphics.drawscope.Stroke(1.5.dp.toPx()))
            drawCircle(c, r * 0.34f, ctr, style = androidx.compose.ui.graphics.drawscope.Stroke(1.5.dp.toPx()))
            drawCircle(c, 1.6.dp.toPx(), ctr)
        } else androidx.compose.foundation.Canvas(Modifier.size(width = 20.dp, height = 22.dp)) {
            val bar = 3.dp.toPx(); val gap = 5.dp.toPx(); val c = markColor
            drawRect(c, androidx.compose.ui.geometry.Offset(0f, size.height * 0.15f), androidx.compose.ui.geometry.Size(bar, size.height * 0.7f))
            drawRect(c, androidx.compose.ui.geometry.Offset(bar + gap, 0f), androidx.compose.ui.geometry.Size(bar, size.height))
            drawRect(c, androidx.compose.ui.geometry.Offset((bar + gap) * 2, size.height * 0.25f), androidx.compose.ui.geometry.Size(bar, size.height * 0.5f))
        }
        Spacer(Modifier.width(10.dp))
        Text(LocalCalibrePalette.current.wordmark, style = calibreDisplayStyle(MaterialTheme.typography.titleLarge), color = MaterialTheme.colorScheme.onSurface)
        Spacer(Modifier.weight(1f))
        if(shop != null) MonoLabel(shop.take(22))
        trailing?.invoke()
    }
}

/** Four-segment progress strip with mono captions (Intake / Approved / Serviced / Collect). */
@Composable fun JobStageStrip(stage: Int, labels: List<String> = listOf("Intake", "Approved", "Serviced", "Collect"), modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().semantics(mergeDescendants = true) { contentDescription = "Progress: ${labels.getOrNull(stage.coerceIn(0, (labels.size - 1).coerceAtLeast(0))).orEmpty()}, step ${stage + 1} of ${labels.size}" }, verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(6.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(4.dp)) {
            labels.forEachIndexed { i, _ ->
                Box(Modifier.weight(1f).height(3.dp).background(if(i <= stage) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant))
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(4.dp)) {
            labels.forEachIndexed { i, l -> Box(Modifier.weight(1f)) { MonoLabel(l, color = if(i <= stage) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant) } }
        }
    }
}

/** Maps a watch-repair status to its stage on the Calibre strip. */
fun watchStage(status: String): Int = when(status) {
    "go_ahead", "third_party_quote_approved" -> 1
    "working_on", "awaiting_parts", "parts_to_order", "sent_to_labanda", "quoted_by_labanda", "at_third_party_for_quoting", "at_third_party_repairer", "service", "completed" -> 2
    "awaiting_collection", "collected" -> 3
    else -> 0
}

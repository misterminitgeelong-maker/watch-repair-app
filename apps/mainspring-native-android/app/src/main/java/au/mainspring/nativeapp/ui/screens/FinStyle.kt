package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import au.mainspring.nativeapp.ui.AppAppearance
import au.mainspring.nativeapp.ui.BackButton
import au.mainspring.nativeapp.ui.LocalCalibre
import au.mainspring.nativeapp.ui.LocalCalibrePalette
import au.mainspring.nativeapp.ui.Mainspring
import au.mainspring.nativeapp.ui.PrimaryAction
import au.mainspring.nativeapp.ui.StatusTone
import au.mainspring.nativeapp.ui.TonePill
import au.mainspring.nativeapp.ui.ToolIcon
import au.mainspring.nativeapp.ui.calibreDisplayStyle
import au.mainspring.nativeapp.ui.statusLabel
import au.mainspring.nativeapp.ui.statusTone

/*
 * Web-matching building blocks for the money screens (Quotes, Invoices, Reports, Catalogue): a display-serif title with a
 * short red underline, bordered white cards, outlined buttons, a select box, a search box and a segmented button row.
 * Everything reads colours from MaterialTheme so the non-Mainspring appearances and dark mode keep working.
 */

/** Page gutter used by the web phone layout. */
internal val FinGutter = 16.dp

/** Sand fill for a selected segment (the web "All" / "All types" buttons). */
internal val FinSand = Color(0xFFF2E8DC)

/** Border of inputs and outlined buttons: the stronger web border in the Mainspring look, the theme outline elsewhere. */
@Composable internal fun finBorderColor(): Color =
    if(LocalCalibrePalette.current.appearance == AppAppearance.MAINSPRING) Mainspring.BorderStrong else MaterialTheme.colorScheme.outlineVariant

/** Title (display serif) with the short accent underline. [onBack] adds a slim back row, [insets] pads for the status bar. */
@Composable internal fun FinTitle(text: String, modifier: Modifier = Modifier, onBack: (() -> Unit)? = null, insets: Boolean = false, gutter: Dp = FinGutter, actions: (@Composable RowScope.() -> Unit)? = null) {
    Column(modifier.fillMaxWidth()) {
        if(onBack != null || actions != null) Row(Modifier.fillMaxWidth().then(if(insets) Modifier.statusBarsPadding() else Modifier).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            if(onBack != null) BackButton(onBack)
            Spacer(Modifier.weight(1f))
            actions?.invoke(this)
        }
        Column(Modifier.fillMaxWidth().then(if(insets && onBack == null && actions == null) Modifier.statusBarsPadding() else Modifier).padding(start = gutter, end = gutter, top = 16.dp, bottom = 12.dp)) {
            Text(text, Modifier.semantics { heading() }, style = (if(LocalCalibre.current) calibreDisplayStyle(MaterialTheme.typography.headlineLarge) else MaterialTheme.typography.headlineLarge).copy(fontSize = 30.sp, lineHeight = 36.sp),
                color = MaterialTheme.colorScheme.onSurface, maxLines = 2)
            Box(Modifier.padding(top = 8.dp).width(28.dp).height(3.dp).background(MaterialTheme.colorScheme.primary))
        }
    }
}

/** Bordered white card (optionally tappable), the web "card" surface. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun FinCard(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, contentPadding: Dp = 16.dp, content: @Composable ColumnScope.() -> Unit) {
    val shape = RoundedCornerShape(8.dp)
    val border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
    val inner: @Composable () -> Unit = { Column(Modifier.fillMaxWidth().padding(contentPadding), verticalArrangement = Arrangement.spacedBy(6.dp), content = content) }
    if(onClick != null) Surface(onClick, modifier.fillMaxWidth(), shape = shape, color = MaterialTheme.colorScheme.surface, border = border, content = inner)
    else Surface(modifier.fillMaxWidth(), shape = shape, color = MaterialTheme.colorScheme.surface, border = border, content = inner)
}

/** White outlined button with centred label; [content] replaces the label when an icon is needed. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun FinOutlinedButton(onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, content: @Composable RowScope.() -> Unit) {
    Surface(onClick, modifier.heightIn(min = 48.dp).semantics { role = Role.Button }, enabled = enabled, shape = RoundedCornerShape(6.dp), color = MaterialTheme.colorScheme.surface,
        contentColor = MaterialTheme.colorScheme.onSurface.copy(alpha = if(enabled) 1f else 0.5f), border = BorderStroke(1.dp, finBorderColor())) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically, content = content)
    }
}

@Composable internal fun FinOutlinedLabel(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) =
    FinOutlinedButton(onClick, modifier, enabled) { Text(label, style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold), maxLines = 1) }

/** Full-width solid accent button ("+ New Quote"). */
@Composable internal fun FinPrimaryButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    PrimaryAction(onClick, modifier.fillMaxWidth(), enabled, shape = RoundedCornerShape(6.dp)) { Text(label, style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold)) }
}

/** Search box with a magnifier, 44dp high and white with the strong border (web search field). */
@Composable internal fun FinSearchField(value: String, onValueChange: (String) -> Unit, placeholder: String, modifier: Modifier = Modifier, onSearch: (() -> Unit)? = null, fieldTag: String? = null) {
    val textStyle = MaterialTheme.typography.bodyLarge.copy(color = MaterialTheme.colorScheme.onSurface)
    Row(modifier.fillMaxWidth().heightIn(min = 48.dp).background(MaterialTheme.colorScheme.surface, RoundedCornerShape(6.dp)).border6(finBorderColor()).padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        ToolIcon("search", size = 20.dp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box(Modifier.weight(1f)) {
            if(value.isEmpty()) Text(placeholder, style = textStyle, color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f), maxLines = 1)
            BasicTextField(value, onValueChange, Modifier.fillMaxWidth().then(if(fieldTag != null) Modifier.testTag(fieldTag) else Modifier).then(Modifier.semantics { contentDescription = placeholder }), singleLine = true, textStyle = textStyle,
                cursorBrush = SolidColor(MaterialTheme.colorScheme.primary), keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { onSearch?.invoke() }))
        }
    }
}

private fun Modifier.border6(color: Color): Modifier = this.then(Modifier.border(1.dp, color, RoundedCornerShape(6.dp)))

/** Drop-down select that looks like the web `<select>`: bordered white box, value left, chevron right. */
@Composable internal fun FinSelect(valueLabel: String, options: List<Pair<String?, String>>, onSelect: (String?) -> Unit, modifier: Modifier = Modifier, tag: String? = null, description: String? = null) {
    var open by remember { mutableStateOf(false) }
    Box(modifier) {
        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).background(MaterialTheme.colorScheme.surface, RoundedCornerShape(6.dp)).border6(finBorderColor())
            .then(if(tag != null) Modifier.testTag(tag) else Modifier)
            .semantics(mergeDescendants = true) { role = Role.DropdownList; if(description != null) contentDescription = "$description: $valueLabel" }
            .clickable { open = true }.padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(valueLabel, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge, maxLines = 1)
            FinChevron(MaterialTheme.colorScheme.onSurface)
        }
        DropdownMenu(open, { open = false }) {
            options.forEach { (key, label) -> DropdownMenuItem({ Text(label) }, { open = false; onSelect(key) }, Modifier.heightIn(min = 48.dp)) }
        }
    }
}

/** Equal-width segmented buttons: the selected one is sand-filled, the others white and bordered (web "All | Unpaid | Paid"). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun FinSegmentRow(options: List<Pair<String?, String>>, selected: String?, onSelect: (String?) -> Unit, modifier: Modifier = Modifier, tagPrefix: String? = null) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (key, label) ->
            val on = key == selected
            Surface({ onSelect(key) }, Modifier.weight(1f).heightIn(min = 48.dp).then(if(tagPrefix != null) Modifier.testTag("$tagPrefix-${key ?: "all"}") else Modifier).semantics { this.selected = on; role = Role.Tab },
                shape = RoundedCornerShape(4.dp), color = if(on) FinSand else MaterialTheme.colorScheme.surface, contentColor = MaterialTheme.colorScheme.onSurface,
                border = if(on) null else BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                Box(Modifier.padding(horizontal = 6.dp, vertical = 10.dp), contentAlignment = Alignment.Center) {
                    Text(label, style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold), maxLines = 1)
                }
            }
        }
    }
}

/** Plain-text period switch (web "3 months | 6 months | 12 months"): the selected option is a white pill with accent text. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun FinPillSwitch(options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(2.dp), verticalAlignment = Alignment.CenterVertically) {
        options.forEach { (key, label) ->
            val on = key == selected
            Surface({ onSelect(key) }, Modifier.weight(1f).heightIn(min = 48.dp).semantics { this.selected = on; role = Role.Tab }, shape = RoundedCornerShape(6.dp),
                color = if(on) MaterialTheme.colorScheme.surface else Color.Transparent, shadowElevation = if(on) 1.dp else 0.dp) {
                Box(Modifier.padding(horizontal = 4.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
                    Text(label, style = MaterialTheme.typography.labelMedium.copy(fontWeight = if(on) FontWeight.SemiBold else FontWeight.Medium), maxLines = 1, softWrap = false,
                        color = if(on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** Underline tabs with a leading icon, full width with a hairline under them (web "Overview | Regional Report"). */
@Composable internal fun FinTabs(options: List<Triple<String, String, String?>>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(20.dp)) {
            options.forEach { (key, label, icon) ->
                val on = key == selected
                val tint = if(on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                Column(Modifier.heightIn(min = 48.dp).semantics { this.selected = on; role = Role.Tab }.clickable { onSelect(key) }, verticalArrangement = Arrangement.Bottom) {
                    Row(Modifier.heightIn(min = 44.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if(icon != null) FinGlyph(icon, tint, 18.dp)
                        Text(label, style = MaterialTheme.typography.labelLarge.copy(fontWeight = if(on) FontWeight.SemiBold else FontWeight.Medium), color = tint, maxLines = 1)
                    }
                    Box(Modifier.fillMaxWidth().height(2.dp).background(if(on) MaterialTheme.colorScheme.primary else Color.Transparent))
                }
            }
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(MaterialTheme.colorScheme.outlineVariant))
    }
}

/** Soft green chip such as "MOBILE". */
@Composable internal fun FinChip(text: String, modifier: Modifier = Modifier) {
    Text(text, modifier.background(Color(0xFFE3F2E8), RoundedCornerShape(12.dp)).padding(horizontal = 8.dp, vertical = 3.dp),
        style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold, letterSpacing = 0.5.sp), color = Color(0xFF1E5A33), maxLines = 1)
}

/** Status pill with the web tone for invoices: unpaid reads amber like the web, everything else follows [statusTone]. */
@Composable internal fun FinStatusPill(status: String, modifier: Modifier = Modifier) {
    val tone = if(status.trim().lowercase() == "unpaid") StatusTone.Waiting else statusTone(status)
    TonePill(statusLabel(status), tone, modifier)
}

/** Monospace accent document number, "#" and the number as separate text nodes. */
@Composable internal fun FinDocNumber(number: String, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        val style = MaterialTheme.typography.titleMedium.copy(fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 16.sp)
        Text("#", style = style, color = MaterialTheme.colorScheme.primary, maxLines = 1)
        Text(number, style = style, color = MaterialTheme.colorScheme.primary, maxLines = 1)
    }
}

/** Empty state: bordered card with a thin dash above one muted line (web "No quotes yet."). */
@Composable internal fun FinEmptyCard(text: String, modifier: Modifier = Modifier) {
    FinCard(modifier, contentPadding = 0.dp) {
        Column(Modifier.fillMaxWidth().padding(vertical = 56.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Box(Modifier.width(32.dp).height(1.dp).background(finBorderColor()))
            Text(text, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** KPI card: coloured rounded-square icon on the left, small caps label and a big value. */
@Composable internal fun FinKpiCard(label: String, value: String, glyph: String, tint: Color, container: Color, modifier: Modifier = Modifier, valueTag: String? = null) {
    FinCard(modifier, contentPadding = 20.dp) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(44.dp).background(container, RoundedCornerShape(4.dp)), contentAlignment = Alignment.Center) { FinGlyph(glyph, tint, 24.dp) }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(label.uppercase(), style = MaterialTheme.typography.labelMedium.copy(letterSpacing = 0.8.sp), color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                Text(value, if(valueTag != null) Modifier.testTag(valueTag) else Modifier, style = MaterialTheme.typography.headlineMedium.copy(fontWeight = FontWeight.Medium, fontSize = 30.sp), maxLines = 1)
            }
        }
    }
}

/** The four web KPI tints: green revenue, amber cost, purple profit, red outstanding. */
internal object FinKpi {
    val RevenueTint = Color(0xFF1E7B45); val RevenueBg = Color(0xFFE3F2E8)
    val CostTint = Color(0xFFB8741A); val CostBg = Color(0xFFF7E9D6)
    val ProfitTint = Color(0xFF6B4BB8); val ProfitBg = Color(0xFFECE6F8)
    val OutstandingTint = Color(0xFFB3261E); val OutstandingBg = Color(0xFFFBE4E1)
}

@Composable internal fun FinChevron(color: Color, size: Dp = 16.dp) {
    Canvas(Modifier.size(size)) {
        val w = 1.8.dp.toPx()
        val s = this.size.width
        drawLine(color, Offset(s * 0.2f, s * 0.38f), Offset(s * 0.5f, s * 0.68f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.5f, s * 0.68f), Offset(s * 0.8f, s * 0.38f), w, StrokeCap.Round)
    }
}

/** Small outline glyphs the ToolIcon set lacks: wrench, chip, wallet, scales, bars, dollar, sliders, dots, chart. */
@Composable internal fun FinGlyph(name: String, color: Color, size: Dp = 22.dp) {
    if(name == "dollar") { Text("$", style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Medium, fontSize = (size.value * 0.95f).sp, lineHeight = (size.value * 1.1f).sp), color = color); return }
    if(name == "search" || name == "settings" || name == "reports") { ToolIcon(name, size = size, color = color); return }
    Canvas(Modifier.size(size)) {
        val s = this.size.width / 24f
        val w = 1.7f * s
        fun p(x: Float, y: Float) = Offset(x * s, y * s)
        fun ln(x1: Float, y1: Float, x2: Float, y2: Float) = drawLine(color, p(x1, y1), p(x2, y2), w, StrokeCap.Round)
        val st = Stroke(w, cap = StrokeCap.Round, join = StrokeJoin.Round)
        when(name) {
            "wrench" -> { drawCircle(color, 4f * s, p(16.5f, 7.5f), style = st); ln(13.8f, 10.2f, 4.5f, 19.5f); ln(4.5f, 19.5f, 6f, 20.5f); ln(14.5f, 6.5f, 17.5f, 9f) }
            "chip" -> { drawRoundRect(color, p(6f, 6f), Size(12f * s, 12f * s), CornerRadius(1.5f * s), style = st); drawRect(color, p(10f, 10f), Size(4f * s, 4f * s), style = st)
                for(v in listOf(9f, 15f)) { ln(v, 3f, v, 6f); ln(v, 18f, v, 21f); ln(3f, v, 6f, v); ln(18f, v, 21f, v) } }
            "wallet" -> { drawRoundRect(color, p(3f, 6f), Size(18f * s, 13f * s), CornerRadius(2.5f * s), style = st); ln(3f, 10f, 21f, 10f); drawCircle(color, 1.1f * s, p(16.5f, 14.5f)) }
            "scales" -> { ln(12f, 4f, 12f, 20f); ln(7f, 20f, 17f, 20f); ln(5f, 7f, 19f, 7f); ln(5f, 7f, 2.5f, 13.5f); ln(5f, 7f, 7.5f, 13.5f); ln(2.5f, 13.5f, 7.5f, 13.5f)
                ln(19f, 7f, 16.5f, 13.5f); ln(19f, 7f, 21.5f, 13.5f); ln(16.5f, 13.5f, 21.5f, 13.5f) }
            "bars" -> { ln(5f, 20f, 5f, 12f); ln(10f, 20f, 10f, 6f); ln(15f, 20f, 15f, 10f); ln(20f, 20f, 20f, 4f) }
            "dots" -> for(cx in listOf(5f, 12f, 19f)) drawCircle(color, 1.7f * s, p(cx, 12f))
            "globe" -> { drawCircle(color, 8.5f * s, p(12f, 12f), style = st); ln(3.5f, 12f, 20.5f, 12f); drawOval(color, p(8f, 3.5f), Size(8f * s, 17f * s), style = st) }
            else -> drawCircle(color, 8f * s, p(12f, 12f), style = st)
        }
    }
}

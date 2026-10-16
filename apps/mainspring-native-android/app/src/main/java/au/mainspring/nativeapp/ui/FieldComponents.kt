package au.mainspring.nativeapp.ui

import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.clickable
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    if(LocalCalibre.current) { MonoLabel(text, modifier.padding(top = 18.dp, bottom = 4.dp).semantics { heading() }); return }
    Text(text, modifier = modifier.padding(top = 8.dp, bottom = 4.dp).semantics { heading() }, style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.onSurface)
}

@Composable fun FlatPanel(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    if(LocalCalibre.current) {
        Column(modifier.fillMaxWidth()) {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Column(Modifier.padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
        }
        return
    }
    Surface(modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
    }
}

@Composable fun DetailRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(label, Modifier.weight(0.4f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value.ifBlank { "Not recorded" }, Modifier.weight(0.6f), style = MaterialTheme.typography.bodySmall,
            textAlign = androidx.compose.ui.text.style.TextAlign.End)
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

/** Atelier status: a soft tinted pill (amber waiting, green ready, forest in progress, red late, grey neutral) in Calibre; the blue caption otherwise. */
@Composable fun StatusPill(status: String, modifier: Modifier = Modifier) {
    val negative = status in setOf("no_go", "failed_job", "job_delayed", "declined", "overdue", "urgent")
    if(LocalCalibre.current) { TonePill(statusLabel(status), statusTone(status), modifier); return }
    Text(statusLabel(status), modifier, style = MaterialTheme.typography.labelMedium,
        color = if(negative) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
}

@Composable fun MetricStrip(values: List<Pair<String, String>>, modifier: Modifier = Modifier) {
    if(LocalCalibre.current) {
        Column(modifier.fillMaxWidth()) {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                values.forEach { (label, value) ->
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(value, style = MaterialTheme.typography.headlineMedium.copy(fontWeight = FontWeight.Normal), color = MaterialTheme.colorScheme.onSurface)
                        MonoLabel(label)
                    }
                }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
        return
    }
    Row(modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        values.forEach { (label, value) ->
            Surface(Modifier.weight(1f).fillMaxHeight(), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
                Column(Modifier.padding(horizontal = 16.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(value, style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onSurface)
                    Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** Small scalable outline icons, kept local so every navigation item has a real glyph. */
@Composable fun FieldIcon(name: String, color: Color = MaterialTheme.colorScheme.onSurfaceVariant) {
    Canvas(Modifier.size(22.dp)) {
        val scale = size.width / 24f
        fun point(x: Float,y: Float) = Offset(x*scale,y*scale)
        fun line(x: Float,y: Float,x2: Float,y2: Float) = drawLine(color,point(x,y),point(x2,y2),1.5f*scale)
        when(name) {
            "Jobs" -> { drawCircle(color,5f*scale,point(8f,8f),style = Stroke(1.5f*scale)); line(11f,12f,21f,22f); line(17f,18f,20f,15f); line(19f,20f,22f,17f) }
            "Map" -> { val p=Path(); p.moveTo(2f*scale,5f*scale); p.lineTo(8f*scale,2f*scale); p.lineTo(16f*scale,5f*scale); p.lineTo(22f*scale,2f*scale); p.lineTo(22f*scale,19f*scale); p.lineTo(16f*scale,22f*scale); p.lineTo(8f*scale,19f*scale); p.lineTo(2f*scale,22f*scale); p.close(); drawPath(p,color,style=Stroke(1.5f*scale)); line(8f,2f,8f,19f); line(16f,5f,16f,22f) }
            "Pool" -> { for(y in listOf(5f,10f,15f)) { line(3f,y,12f,y-3f); line(12f,y-3f,21f,y); line(3f,y,12f,y+4f); line(12f,y+4f,21f,y) } }
            "POS" -> { drawRect(color,point(2f,5f),Size(20f*scale,14f*scale),style=Stroke(1.5f*scale)); line(2f,9f,22f,9f) }
            "Home" -> { line(2f,11f,12f,2f); line(12f,2f,22f,11f); line(5f,9f,5f,22f); line(5f,22f,19f,22f); line(19f,22f,19f,9f); line(10f,22f,10f,15f); line(10f,15f,14f,15f); line(14f,15f,14f,22f) }
            "Reports" -> { line(3f,2f,3f,22f); line(3f,22f,22f,22f); line(8f,18f,8f,12f); line(13f,18f,13f,6f); line(18f,18f,18f,9f) }
            "Stock" -> { drawRect(color,point(4f,4f),Size(16f*scale,18f*scale),style=Stroke(1.5f*scale)); line(8f,2f,16f,2f); for(y in listOf(9f,13f,17f)) line(8f,y,16f,y) }
            else -> { for(y in listOf(6f,12f,18f)) line(4f,y,20f,y) }
        }
    }
}

/** 48dp back arrow for top bars; announced as "Back" to screen readers. */
@Composable fun BackButton(onClick: () -> Unit, enabled: Boolean = true) {
    IconButton(onClick = onClick, enabled = enabled, modifier = Modifier.semantics { contentDescription = "Back" }) {
        val color = if(enabled) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.38f)
        Canvas(Modifier.size(24.dp)) {
            val s = size.width / 24f
            val w = 2f * s
            drawLine(color, Offset(20f * s, 12f * s), Offset(5f * s, 12f * s), w, cap = StrokeCap.Round)
            drawLine(color, Offset(11f * s, 5f * s), Offset(4f * s, 12f * s), w, cap = StrokeCap.Round)
            drawLine(color, Offset(11f * s, 19f * s), Offset(4f * s, 12f * s), w, cap = StrokeCap.Round)
        }
    }
}

/** Friendly inline error with a retry affordance, used instead of bare red text. */
@Composable fun ErrorBanner(message: String, modifier: Modifier = Modifier, onRetry: (() -> Unit)? = null) {
    Surface(modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Assertive }, color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
        Row(Modifier.padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(message, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onErrorContainer)
            if(onRetry != null) TextButton(onClick = onRetry) { Text("Retry") }
        }
    }
}

/** Centred empty-state with a headline, optional hint and optional single action. */
@Composable fun EmptyState(title: String, hint: String? = null, actionLabel: String? = null, onAction: (() -> Unit)? = null, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleMedium, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        if(hint != null) Text(hint, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        if(actionLabel != null && onAction != null) androidx.compose.material3.OutlinedButton(onClick = onAction) { Text(actionLabel) }
    }
}

/** Tappable card used by every directory list so rows share one look. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun ListCard(onClick: () -> Unit, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    if(LocalCalibre.current) {
        Column(modifier.fillMaxWidth()) {
            Surface(onClick, Modifier.fillMaxWidth(), color = Color.Transparent, shape = androidx.compose.ui.graphics.RectangleShape) {
                Column(Modifier.padding(vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(4.dp), content = content)
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
        return
    }
    Surface(onClick, modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
        Column(Modifier.padding(horizontal = 20.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(4.dp), content = content)
    }
}

/** Horizontally scrolling filter chips. `options` maps a stored key (null = all) to its label. */
@Composable fun FilterRow(options: List<Pair<String?, String>>, selected: String?, onSelect: (String?) -> Unit, modifier: Modifier = Modifier) {
    if(LocalCalibre.current) {
        Column(modifier.fillMaxWidth()) {
            Row(Modifier.fillMaxWidth().horizontalScroll(androidx.compose.foundation.rememberScrollState()).padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(22.dp)) {
                options.forEach { (key, label) -> PillChip(label, selected == key, { onSelect(key) }) }
            }
            HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
        }
        return
    }
    Row(modifier.fillMaxWidth().horizontalScroll(androidx.compose.foundation.rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (key, label) -> PillChip(label, selected == key, { onSelect(key) }) }
    }
}

/** "awaiting_go_ahead" -> "Awaiting go ahead". */
fun statusLabel(value: String): String = value.replace('_', ' ').replaceFirstChar { it.uppercase() }

/** A full-width pick-one row for wizards: outlined, tinted and ticked when selected. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun SelectableCard(selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, content: @Composable ColumnScope.() -> Unit) {
    Surface(onClick, modifier.fillMaxWidth().heightIn(min = 56.dp), enabled = enabled, shape = MaterialTheme.shapes.medium,
        color = if(selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
        border = if(selected) BorderStroke(2.dp, MaterialTheme.colorScheme.primary) else if(LocalCalibre.current) BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant) else null) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp), content = content)
            if(selected) Text("\u2713", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.primary)
        }
    }
}

/** Sticky bottom bar for multi-step forms: a step progress line plus Previous / primary buttons. */
@Composable fun WizardBar(step: Int, steps: Int, stepTitle: String, primaryLabel: String, onPrimary: () -> Unit, primaryEnabled: Boolean, onPrevious: (() -> Unit)?, previousEnabled: Boolean = true) {
    Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = if(LocalCalibre.current) 0.dp else 2.dp) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if(LocalCalibre.current) HorizontalDivider(Modifier.offset(y = (-10).dp), color = MaterialTheme.colorScheme.outlineVariant)
            if(LocalCalibre.current) {
                Text("0${step + 1} / 0$steps  ${stepTitle.uppercase()}", Modifier.semantics { contentDescription = "Step ${step + 1} of $steps, $stepTitle" }, style = Calibre.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    (0 until steps).forEach { i -> Box(Modifier.weight(1f).height(3.dp).background(if(i <= step) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)) }
                }
            } else {
            Text("Step ${step + 1} of $steps \u00b7 $stepTitle", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            LinearProgressIndicator(progress = { (step + 1f) / steps }, modifier = Modifier.fillMaxWidth())
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if(onPrevious != null) SecondaryAction(onClick = onPrevious, enabled = previousEnabled, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Previous") }
                PrimaryAction(onClick = onPrimary, enabled = primaryEnabled, modifier = Modifier.weight(if(onPrevious != null) 1.5f else 1f).heightIn(min = 52.dp)) { Text(primaryLabel, style = MaterialTheme.typography.titleMedium) }
            }
        }
    }
}

/** Dark/white pill used for segmented filters (Active / Mine / Ready, Watch / Shoe / Mobile). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun PillChip(label: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    if(LocalCalibre.current) {
        Column(modifier.width(IntrinsicSize.Max).heightIn(min = 48.dp).semantics { this.selected = selected }
            .clickable(enabled = enabled, role = androidx.compose.ui.semantics.Role.Tab, onClick = onClick), horizontalAlignment = Alignment.Start, verticalArrangement = Arrangement.Bottom) {
            Box(Modifier.heightIn(min = 44.dp).padding(horizontal = 2.dp), contentAlignment = Alignment.CenterStart) {
                Text(label, style = MaterialTheme.typography.labelLarge.copy(fontWeight = if(selected) FontWeight.SemiBold else FontWeight.Normal),
                    color = (if(selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant).copy(alpha = if(enabled) 1f else 0.5f), maxLines = 1)
            }
            Box(Modifier.fillMaxWidth().height(2.dp).background(if(selected) MaterialTheme.colorScheme.primary else Color.Transparent))
        }
        return
    }
    Surface(onClick, modifier.heightIn(min = 48.dp).semantics { this.selected = selected }, enabled = enabled, shape = MaterialTheme.shapes.small,
        color = if(selected) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.surface,
        contentColor = if(selected) MaterialTheme.colorScheme.onSecondary else MaterialTheme.colorScheme.onSurface) {
        Box(Modifier.padding(horizontal = 18.dp, vertical = 10.dp), contentAlignment = Alignment.Center) {
            Text(label, style = MaterialTheme.typography.labelLarge, maxLines = 1)
        }
    }
}

/** Equal-width segmented control built from [PillChip]s. */
@Composable fun SegmentedPills(options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    if(LocalCalibre.current) {
        Column(modifier.fillMaxWidth()) {
            val roomy = options.size <= 4 && androidx.compose.ui.platform.LocalDensity.current.fontScale <= 1.2f
            Row(Modifier.fillMaxWidth().then(if(roomy) Modifier else Modifier.horizontalScroll(androidx.compose.foundation.rememberScrollState())), horizontalArrangement = Arrangement.spacedBy(22.dp)) {
                options.forEach { (key, label) -> PillChip(label, selected == key, { onSelect(key) }) }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
        return
    }
    if(androidx.compose.ui.platform.LocalDensity.current.fontScale > 1.25f && options.size > 2) {
        Row(modifier.fillMaxWidth().horizontalScroll(androidx.compose.foundation.rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            options.forEach { (key, label) -> PillChip(label, selected == key, { onSelect(key) }) }
        }
    } else Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (key, label) -> PillChip(label, selected == key, { onSelect(key) }, Modifier.weight(1f)) }
    }
}

/** Atelier large-title header: small uppercase eyebrow, big bold title, optional round "+" button. */
@Composable fun LargeHeader(eyebrow: String?, title: String, modifier: Modifier = Modifier, onAdd: (() -> Unit)? = null, addDescription: String = "New", trailing: (@Composable () -> Unit)? = null, insets: Boolean = true) {
    Row(modifier.fillMaxWidth().then(if(insets) Modifier.statusBarsPadding() else Modifier).padding(start = 20.dp, end = 20.dp, top = 12.dp, bottom = 8.dp), verticalAlignment = Alignment.Bottom) {
        Column(Modifier.weight(1f)) {
            if(eyebrow != null) { if(LocalCalibre.current) MonoLabel(eyebrow) else Text(eyebrow.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.onSurface, maxLines = 2)
        }
        trailing?.invoke()
        if(onAdd != null) RoundPlusButton(onAdd, addDescription)
    }
}

/** White circle with a blue plus, the Atelier "new" affordance. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun RoundPlusButton(onClick: () -> Unit, description: String = "New", modifier: Modifier = Modifier) {
    if(LocalCalibre.current) {
        Surface(onClick, modifier.size(48.dp).semantics { contentDescription = description; role = Role.Button }, shape = MaterialTheme.shapes.small, color = MaterialTheme.colorScheme.primary) {
            val color = MaterialTheme.colorScheme.onPrimary
            Canvas(Modifier.padding(15.dp)) {
                val w = 2.2f * density
                drawLine(color, Offset(size.width / 2, 0f), Offset(size.width / 2, size.height), w, cap = StrokeCap.Square)
                drawLine(color, Offset(0f, size.height / 2), Offset(size.width, size.height / 2), w, cap = StrokeCap.Square)
            }
        }
        return
    }
    Surface(onClick, modifier.size(48.dp).semantics { contentDescription = description; role = Role.Button }, shape = androidx.compose.foundation.shape.CircleShape, color = MaterialTheme.colorScheme.surface) {
        val color = MaterialTheme.colorScheme.primary
        Canvas(Modifier.padding(14.dp)) {
            val w = 2.2f * density
            drawLine(color, Offset(size.width / 2, 0f), Offset(size.width / 2, size.height), w, cap = StrokeCap.Round)
            drawLine(color, Offset(0f, size.height / 2), Offset(size.width, size.height / 2), w, cap = StrokeCap.Round)
        }
    }
}

/** Dark hero card used on Today and for key totals (e.g. outstanding balance). */
@Composable fun HeroCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val calibre = LocalCalibre.current
    Surface(modifier.fillMaxWidth(), color = if(calibre) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.secondary, contentColor = if(calibre) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSecondary, shape = MaterialTheme.shapes.medium) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(6.dp), content = content)
    }
}

/** Line-art watch used on the Today hero card. */
@Composable fun WatchArt(modifier: Modifier = Modifier, color: Color = if(LocalCalibre.current) MaterialTheme.colorScheme.primary else Color(0xFFD7F36B)) {
    Canvas(modifier.size(width = 84.dp, height = 112.dp)) {
        val u = size.width / 84f
        val strap = color.copy(alpha = 0.16f)
        drawRoundRect(strap, Offset(26f * u, 0f), Size(32f * u, 112f * u), androidx.compose.ui.geometry.CornerRadius(8f * u))
        drawCircle(color, 38f * u, Offset(42f * u, 56f * u), style = Stroke(3f * u))
        drawLine(color, Offset(42f * u, 56f * u), Offset(42f * u, 34f * u), 3f * u, cap = StrokeCap.Round)
        drawLine(color, Offset(42f * u, 56f * u), Offset(58f * u, 64f * u), 3f * u, cap = StrokeCap.Round)
        drawRoundRect(color, Offset(80f * u, 48f * u), Size(4f * u, 16f * u), androidx.compose.ui.geometry.CornerRadius(2f * u))
    }
}

/** Atelier icon set for the tab bar (outline, 24dp grid). */
@Composable fun AtelierIcon(name: String, color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier.size(24.dp)) {
        val s = size.width / 24f
        val st = Stroke(1.6f * s, cap = StrokeCap.Round)
        fun p(x: Float, y: Float) = Offset(x * s, y * s)
        fun ln(x1: Float, y1: Float, x2: Float, y2: Float) = drawLine(color, p(x1, y1), p(x2, y2), 1.6f * s, cap = StrokeCap.Round)
        when(name) {
            "Today", "Dashboard" -> for(cx in listOf(7f, 17f)) for(cy in listOf(7f, 17f)) drawCircle(color, 3.4f * s, p(cx, cy), style = st)
            "Jobs" -> { ln(4f, 20f, 14f, 10f); drawCircle(color, 3.4f * s, p(17f, 7f), style = st); ln(15f, 4f, 20f, 9f); ln(5f, 5f, 10f, 10f); ln(10f, 14f, 20f, 20f).also { } }
            "People", "Customers" -> { drawCircle(color, 3.4f * s, p(9f, 8f), style = st); drawArc(color, 200f, 140f, false, p(3f, 14f), Size(12f * s, 12f * s), style = st)
                drawCircle(color, 2.8f * s, p(17f, 9f), style = st); drawArc(color, 200f, 140f, false, p(12.5f, 14.5f), Size(9f * s, 9f * s), style = st) }
            "Inbox" -> { val path = Path(); path.moveTo(3f * s, 13f * s); path.lineTo(6f * s, 5f * s); path.lineTo(18f * s, 5f * s); path.lineTo(21f * s, 13f * s); path.lineTo(21f * s, 19f * s); path.lineTo(3f * s, 19f * s); path.close()
                drawPath(path, color, style = st); ln(3f, 13f, 8f, 13f); ln(16f, 13f, 21f, 13f); drawArc(color, 0f, 180f, false, p(8f, 10f), Size(8f * s, 6f * s), style = st) }
            else -> for(cx in listOf(5f, 14f)) for(cy in listOf(5f, 14f)) drawRoundRect(color, p(cx, cy), Size(6f * s, 6f * s), androidx.compose.ui.geometry.CornerRadius(1.6f * s), style = st)
        }
    }
}

/** Floating rounded tab bar. `destinations` are (route, label); selected entry is tinted with the accent. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun FloatingTabBar(destinations: List<Pair<String, String>>, isSelected: (String) -> Boolean, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    if(LocalCalibre.current) {
        Column(modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background).navigationBarsPadding()) {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth().widthIn(max = 640.dp).align(Alignment.CenterHorizontally).padding(horizontal = 8.dp, vertical = 6.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                destinations.forEach { (route, label) ->
                    val chosen = isSelected(route)
                    val tint = if(chosen) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                    Column(Modifier.weight(1f).heightIn(min = 48.dp).semantics { selected = chosen }.testTag("nav-$route")
                        .clickable(role = androidx.compose.ui.semantics.Role.Tab, onClick = { onSelect(route) }),
                        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        NavIcon(route, label, tint)
                        Text(label, style = MaterialTheme.typography.labelMedium.copy(fontWeight = if(chosen) FontWeight.SemiBold else FontWeight.Normal), color = tint)
                    }
                }
            }
        }
        return
    }
    Box(modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 12.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
        Surface(Modifier.fillMaxWidth().widthIn(max = 560.dp), shape = androidx.compose.foundation.shape.RoundedCornerShape(32.dp), color = MaterialTheme.colorScheme.surface, shadowElevation = 6.dp) {
            Row(Modifier.padding(horizontal = 6.dp, vertical = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                destinations.forEach { (route, label) ->
                    val chosen = isSelected(route)
                    val tint = if(chosen) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                    Column(Modifier.weight(1f).heightIn(min = 48.dp).semantics { selected = chosen }.testTag("nav-$route")
                        .clickable(role = androidx.compose.ui.semantics.Role.Tab, onClick = { onSelect(route) }),
                        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        NavIcon(route, label, tint)
                        Text(label, style = MaterialTheme.typography.labelMedium, color = tint)
                    }
                }
            }
        }
    }
}

/** Top bar for sub-screens: transparent over the Atelier background, same slots as [TopAppBar]. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun AtelierTopAppBar(
    title: @Composable () -> Unit,
    modifier: Modifier = Modifier,
    navigationIcon: @Composable () -> Unit = {},
    actions: @Composable RowScope.() -> Unit = {},
    windowInsets: WindowInsets = TopAppBarDefaults.windowInsets,
    colors: TopAppBarColors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent, scrolledContainerColor = Color.Transparent),
) {
    Column(modifier.fillMaxWidth().background(colors.containerColor)) {
        Row(Modifier.fillMaxWidth().windowInsetsPadding(windowInsets).padding(horizontal = 4.dp).heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically) {
            navigationIcon()
            Spacer(Modifier.weight(1f))
            actions()
        }
        Box(Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, bottom = 10.dp).semantics(mergeDescendants = true) { heading() }) {
            CompositionLocalProvider(LocalTextStyle provides MaterialTheme.typography.headlineMedium.copy(color = MaterialTheme.colorScheme.onSurface)) { title() }
        }
    }
}

/** Drop-in replacement for FilterChip with the Atelier look: dark pill when selected, white pill otherwise. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun AtelierChip(selected: Boolean, onClick: () -> Unit, label: @Composable () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    if(LocalCalibre.current) {
        Surface(onClick, modifier.heightIn(min = 48.dp).semantics { this.selected = selected }, enabled = enabled, shape = MaterialTheme.shapes.small,
            color = if(selected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
            contentColor = (if(selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface).copy(alpha = if(enabled) 1f else 0.5f),
            border = BorderStroke(if(selected) 1.5.dp else 1.dp, if(selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)) {
            Box(Modifier.padding(horizontal = 14.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
                ProvideTextStyle(MaterialTheme.typography.labelLarge) { label() }
            }
        }
        return
    }
    Surface(onClick, modifier.heightIn(min = 48.dp).semantics { this.selected = selected }, enabled = enabled, shape = MaterialTheme.shapes.small,
        color = if(selected) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.surface,
        contentColor = (if(selected) MaterialTheme.colorScheme.onSecondary else MaterialTheme.colorScheme.onSurface).copy(alpha = if(enabled) 1f else 0.5f)) {
        Box(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
            ProvideTextStyle(MaterialTheme.typography.labelLarge) { label() }
        }
    }
}

/** OutlinedTextField with Atelier defaults: white field, 14dp corners, quiet outline, blue focus. */
@Composable fun AtelierTextField(
    value: String, onValueChange: (String) -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, readOnly: Boolean = false,
    textStyle: androidx.compose.ui.text.TextStyle = LocalTextStyle.current, label: (@Composable () -> Unit)? = null, placeholder: (@Composable () -> Unit)? = null,
    leadingIcon: (@Composable () -> Unit)? = null, trailingIcon: (@Composable () -> Unit)? = null, prefix: (@Composable () -> Unit)? = null, suffix: (@Composable () -> Unit)? = null,
    supportingText: (@Composable () -> Unit)? = null, isError: Boolean = false,
    visualTransformation: androidx.compose.ui.text.input.VisualTransformation = androidx.compose.ui.text.input.VisualTransformation.None,
    keyboardOptions: androidx.compose.foundation.text.KeyboardOptions = androidx.compose.foundation.text.KeyboardOptions.Default,
    keyboardActions: androidx.compose.foundation.text.KeyboardActions = androidx.compose.foundation.text.KeyboardActions.Default,
    singleLine: Boolean = false, maxLines: Int = if(singleLine) 1 else Int.MAX_VALUE, minLines: Int = 1,
    shape: androidx.compose.ui.graphics.Shape = MaterialTheme.shapes.small,
    colors: TextFieldColors = OutlinedTextFieldDefaults.colors(
        focusedContainerColor = if(LocalCalibre.current) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surface, unfocusedContainerColor = if(LocalCalibre.current) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surface, disabledContainerColor = if(LocalCalibre.current) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surface,
        unfocusedBorderColor = if(LocalCalibre.current) Color.Transparent else MaterialTheme.colorScheme.outlineVariant, focusedBorderColor = MaterialTheme.colorScheme.primary),
) = OutlinedTextField(value, onValueChange, modifier, enabled, readOnly, textStyle, label, placeholder, leadingIcon, trailingIcon, prefix, suffix, supportingText,
    isError, visualTransformation, keyboardOptions, keyboardActions, singleLine, maxLines, minLines, null, shape, colors)

/** Sub-screen header: blue "‹ Back" link above an eyebrow + large title (used where the screen has no Atelier tab frame). */
@Composable fun BackLargeHeader(backLabel: String, eyebrow: String?, title: String, onBack: () -> Unit, backEnabled: Boolean = true) {
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack, enabled = backEnabled, modifier = Modifier.heightIn(min = 48.dp).semantics { contentDescription = "Back" }) { Text("\u2039 $backLabel", style = MaterialTheme.typography.titleSmall) }
        }
        LargeHeader(eyebrow, title, insets = false)
    }
}

/** Filter/tab chip: an underline tab in Calibre, the regular chip elsewhere. */
@Composable fun TabChip(selected: Boolean, onClick: () -> Unit, label: @Composable () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    if(!LocalCalibre.current) { AtelierChip(selected, onClick, label, modifier, enabled); return }
    Column(modifier.width(IntrinsicSize.Max).heightIn(min = 48.dp).semantics { this.selected = selected }
        .clickable(enabled = enabled, role = androidx.compose.ui.semantics.Role.Tab, onClick = onClick), verticalArrangement = Arrangement.Bottom) {
        Box(Modifier.heightIn(min = 44.dp).padding(horizontal = 2.dp), contentAlignment = Alignment.CenterStart) {
            androidx.compose.runtime.CompositionLocalProvider(androidx.compose.material3.LocalContentColor provides (if(selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant).copy(alpha = if(enabled) 1f else 0.5f)) {
                ProvideTextStyle(MaterialTheme.typography.labelLarge.copy(fontWeight = if(selected) FontWeight.SemiBold else FontWeight.Normal)) { label() }
            }
        }
        Box(Modifier.fillMaxWidth().height(2.dp).background(if(selected) MaterialTheme.colorScheme.primary else Color.Transparent))
    }
}

/** Tab icon with the alert-count badge on Inbox. */
@Composable fun NavIcon(route: String, label: String, tint: Color) {
    val count = if(route == "inbox") au.mainspring.nativeapp.InboxCountStore.count.collectAsState().value else 0
    Box {
        AtelierIcon(when(route) { "today" -> "Today"; "jobs" -> "Jobs"; "inbox" -> "Inbox"; "more" -> "More"; "people" -> "People"; else -> label }, tint)
        if(count > 0) Box(Modifier.align(Alignment.TopEnd).offset(x = 8.dp, y = (-4).dp).defaultMinSize(minWidth = 16.dp, minHeight = 16.dp)
            .background(MaterialTheme.colorScheme.error, androidx.compose.foundation.shape.CircleShape).padding(horizontal = 4.dp), contentAlignment = Alignment.Center) {
            Text(if(count > 99) "99+" else count.toString(), Modifier.semantics { contentDescription = "$count unread" }, style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp), color = MaterialTheme.colorScheme.onError)
        }
    }
}

/** Radio row whose whole width (label included) selects; the radio itself is just the indicator. */
@Composable fun LabeledRadio(selected: Boolean, onSelect: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, label: @Composable () -> Unit) {
    Row(
        modifier.fillMaxWidth().heightIn(min = 48.dp).selectable(selected = selected, enabled = enabled, role = Role.RadioButton, onClick = onSelect),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null, enabled = enabled)
        Spacer(Modifier.width(8.dp))
        label()
    }
}

/** Checkbox row whose whole width (label included) toggles. */
@Composable fun LabeledCheckbox(checked: Boolean, onCheckedChange: (Boolean) -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, label: @Composable () -> Unit) {
    Row(
        modifier.fillMaxWidth().heightIn(min = 48.dp).toggleable(value = checked, enabled = enabled, role = Role.Checkbox, onValueChange = onCheckedChange),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(checked = checked, onCheckedChange = null, enabled = enabled)
        Spacer(Modifier.width(8.dp))
        label()
    }
}

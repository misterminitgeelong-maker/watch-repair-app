package au.mainspring.nativeapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
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

@Composable fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(text.uppercase(), modifier = modifier.padding(vertical = 8.dp), style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable fun FlatPanel(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), shape = MaterialTheme.shapes.small) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
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

@Composable fun StatusPill(status: String) {
    val dark = MaterialTheme.colorScheme.background.red < 0.2f
    val blue = if(dark) Color(0xFF172B3B) to Color(0xFF9ACAF2) else Color(0xFFE7F0FF) to Color(0xFF315F96)
    val green = if(dark) Color(0xFF1A3427) to Color(0xFFA2DBB6) else Color(0xFFE6F3E9) to Color(0xFF326747)
    val amber = if(dark) Color(0xFF3C3019) to Color(0xFFEED59B) else Color(0xFFFFF3DA) to Color(0xFF866020)
    val red = if(dark) Color(0xFF3E1D19) to Color(0xFFFFB4A8) else Color(0xFFFFE7E1) to Color(0xFF8C2514)
    val (background, foreground) = when(status) {
        "booked", "booking_confirmed", "booking_scheduled", "go_ahead", "working_on", "en_route", "on_site", "service" -> blue
        "work_completed", "invoice_paid", "paid", "completed", "collected", "booking_completed", "approved" -> green
        "unpaid", "awaiting_go_ahead", "quote_sent", "awaiting_confirmation", "awaiting_quote", "awaiting_parts", "parts_to_order", "awaiting_collection", "awaiting_customer_details", "booking_on_hold", "pending_booking" -> amber
        "no_go", "failed_job", "job_delayed", "declined", "overdue", "urgent" -> red
        else -> MaterialTheme.colorScheme.secondaryContainer to MaterialTheme.colorScheme.onSecondaryContainer
    }
    Surface(color = background, contentColor = foreground, shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp)) {
        Text(status.replace('_', ' ').replaceFirstChar { it.uppercase() }, Modifier.padding(horizontal = 10.dp, vertical = 4.dp), style = MaterialTheme.typography.labelMedium)
    }
}

@Composable fun MetricStrip(values: List<Pair<String, String>>, modifier: Modifier = Modifier) {
    Surface(modifier.fillMaxWidth(),color=MaterialTheme.colorScheme.surface,shape=androidx.compose.foundation.shape.RoundedCornerShape(10.dp)) {
        Row(Modifier.height(IntrinsicSize.Min)) {
            values.forEachIndexed {index,(label,value) ->
                Column(Modifier.weight(1f).padding(12.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                    Text(label.uppercase(),style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(value,style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.SemiBold)
                }
                if(index<values.lastIndex) VerticalDivider(Modifier.fillMaxHeight().padding(vertical=12.dp),color=MaterialTheme.colorScheme.outlineVariant)
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
    Surface(modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
        Row(Modifier.padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(message, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onErrorContainer)
            if(onRetry != null) TextButton(onClick = onRetry) { Text("Retry") }
        }
    }
}

/** Centred empty-state with a headline, optional hint and optional single action. */
@Composable fun EmptyState(title: String, hint: String? = null, actionLabel: String? = null, onAction: (() -> Unit)? = null, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        if(hint != null) Text(hint, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        if(actionLabel != null && onAction != null) androidx.compose.material3.OutlinedButton(onClick = onAction) { Text(actionLabel) }
    }
}

/** Tappable card used by every directory list so rows share one look. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun ListCard(onClick: () -> Unit, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Surface(onClick, modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp), content = content)
    }
}

/** Horizontally scrolling filter chips. `options` maps a stored key (null = all) to its label. */
@Composable fun FilterRow(options: List<Pair<String?, String>>, selected: String?, onSelect: (String?) -> Unit, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().horizontalScroll(androidx.compose.foundation.rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (key, label) -> FilterChip(selected = selected == key, onClick = { onSelect(key) }, label = { Text(label) }) }
    }
}

/** "awaiting_go_ahead" -> "Awaiting go ahead". */
fun statusLabel(value: String): String = value.replace('_', ' ').replaceFirstChar { it.uppercase() }

/** A full-width pick-one row for wizards: outlined, tinted and ticked when selected. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun SelectableCard(selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, content: @Composable ColumnScope.() -> Unit) {
    Surface(onClick, modifier.fillMaxWidth().heightIn(min = 56.dp), enabled = enabled, shape = MaterialTheme.shapes.medium,
        color = if(selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
        border = BorderStroke(if(selected) 2.dp else 1.dp, if(selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp), content = content)
            if(selected) Text("\u2713", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.primary)
        }
    }
}

/** Sticky bottom bar for multi-step forms: a step progress line plus Previous / primary buttons. */
@Composable fun WizardBar(step: Int, steps: Int, stepTitle: String, primaryLabel: String, onPrimary: () -> Unit, primaryEnabled: Boolean, onPrevious: (() -> Unit)?, previousEnabled: Boolean = true) {
    Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 2.dp) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Step ${step + 1} of $steps \u00b7 $stepTitle", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            LinearProgressIndicator(progress = { (step + 1f) / steps }, modifier = Modifier.fillMaxWidth())
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if(onPrevious != null) SecondaryAction(onClick = onPrevious, enabled = previousEnabled, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Previous") }
                PrimaryAction(onClick = onPrimary, enabled = primaryEnabled, modifier = Modifier.weight(if(onPrevious != null) 1.5f else 1f).heightIn(min = 52.dp)) { Text(primaryLabel, style = MaterialTheme.typography.titleMedium) }
            }
        }
    }
}

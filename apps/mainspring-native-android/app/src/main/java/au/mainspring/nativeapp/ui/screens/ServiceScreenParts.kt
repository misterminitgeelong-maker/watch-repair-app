package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.ui.LocalCalibre
import au.mainspring.nativeapp.ui.PrimaryAction
import au.mainspring.nativeapp.ui.SecondaryAction
import au.mainspring.nativeapp.ui.StatusTone
import au.mainspring.nativeapp.ui.TonePill
import au.mainspring.nativeapp.ui.calibreDisplayStyle
import au.mainspring.nativeapp.ui.statusTone

/**
 * Shared pieces of the phone "service screen" (Watch / Shoe / Mobile / All jobs), laid out like the web:
 * title, view toggle + secondary buttons, one primary button, sub-tabs, search + Filters, then the list.
 */

/** Large display-serif page title (swap for the shared PageTitle once it lands). */
@Composable internal fun ServiceTitle(text: String, modifier: Modifier = Modifier) { au.mainspring.nativeapp.ui.PageTitle(text, modifier) }

/** One option of a [TextToggle]: stored [key], visible [label] and an optional test tag. */
internal data class ToggleOption(val key: String, val label: String, val tag: String? = null)

/** Plain text toggle (web "Board | List", "Active | Completed"): the selected option sits in a bordered white box. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun TextToggle(options: List<ToggleOption>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
        options.forEach { o ->
            val on = o.key == selected
            val tag = if(o.tag != null) Modifier.testTag(o.tag) else Modifier
            Surface({ onSelect(o.key) }, tag.heightIn(min = 44.dp).semantics { role = Role.Tab },
                shape = RoundedCornerShape(6.dp), color = if(on) MaterialTheme.colorScheme.surface else androidx.compose.ui.graphics.Color.Transparent,
                border = if(on) BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant) else null) {
                Box(Modifier.padding(horizontal = 14.dp, vertical = 10.dp), contentAlignment = Alignment.Center) {
                    Text(o.label, style = MaterialTheme.typography.labelLarge, fontWeight = if(on) FontWeight.SemiBold else FontWeight.Normal,
                        color = if(on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                }
            }
        }
    }
}

/** Underlined sub-tabs (web "Jobs | Catalogue"). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun UnderlineTabs(options: List<ToggleOption>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    val line = MaterialTheme.colorScheme.primary
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(20.dp)) {
        options.forEach { o ->
            val on = o.key == selected
            val tag = if(o.tag != null) Modifier.testTag(o.tag) else Modifier
            Surface({ onSelect(o.key) }, tag.heightIn(min = 44.dp).semantics { role = Role.Tab }, color = androidx.compose.ui.graphics.Color.Transparent) {
                Box(Modifier.drawBehind { if(on) drawLine(line, Offset(0f, size.height - 1.dp.toPx()), Offset(size.width, size.height - 1.dp.toPx()), 2.dp.toPx()) }.padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
                    Text(o.label, style = MaterialTheme.typography.titleSmall, fontWeight = if(on) FontWeight.SemiBold else FontWeight.Normal,
                        color = if(on) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** Small line glyph for buttons: plus, queue, download, wrench, close. */
@Composable internal fun ServiceGlyph(kind: String, modifier: Modifier = Modifier, color: androidx.compose.ui.graphics.Color = MaterialTheme.colorScheme.onSurface) {
    androidx.compose.foundation.Canvas(modifier.androidx_size()) {
        val s = size.width / 24f
        fun ln(x1: Float, y1: Float, x2: Float, y2: Float) = drawLine(color, Offset(x1 * s, y1 * s), Offset(x2 * s, y2 * s), 1.8f * s, cap = androidx.compose.ui.graphics.StrokeCap.Round)
        when(kind) {
            "plus" -> { ln(12f, 5f, 12f, 19f); ln(5f, 12f, 19f, 12f) }
            "queue" -> { ln(10f, 7f, 20f, 7f); ln(10f, 12f, 20f, 12f); ln(10f, 17f, 20f, 17f); ln(4f, 6f, 6f, 8f); ln(4f, 11f, 6f, 13f); ln(4f, 16f, 6f, 18f) }
            "download" -> { ln(12f, 4f, 12f, 15f); ln(7f, 10f, 12f, 15f); ln(17f, 10f, 12f, 15f); ln(5f, 20f, 19f, 20f) }
            "wrench" -> { ln(5f, 19f, 13f, 11f); drawCircle(color, 3.6f * s, Offset(16.5f * s, 7.5f * s), style = androidx.compose.ui.graphics.drawscope.Stroke(1.8f * s)) }
            "close" -> { ln(7f, 7f, 17f, 17f); ln(17f, 7f, 7f, 17f) }
        }
    }
}
private fun Modifier.androidx_size(): Modifier = this.then(Modifier.size(18.dp))

/** Outlined button with a leading glyph (web "Queue", "Export CSV", "Add Watch"). */
@Composable internal fun IconLabelButton(glyph: String, label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    SecondaryAction(onClick, modifier.heightIn(min = 48.dp), enabled = enabled, shape = RoundedCornerShape(2.dp), contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp)) {
        ServiceGlyph(glyph); Spacer(Modifier.width(8.dp)); Text(label, style = MaterialTheme.typography.labelLarge, maxLines = 1)
    }
}

/** One full-width primary button ("+ New Job Ticket"). */
@Composable internal fun NewTicketButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, glyph: String = "plus", fullWidth: Boolean = true) {
    PrimaryAction(onClick, (if(fullWidth) modifier.fillMaxWidth() else modifier).testTag("new-job-ticket"), shape = RoundedCornerShape(2.dp)) {
        ServiceGlyph(glyph, color = MaterialTheme.colorScheme.onPrimary); Spacer(Modifier.width(8.dp)); Text(label, style = MaterialTheme.typography.titleSmall)
    }
}

/** Search field and the "Filters" button on one row. [activeCount] > 0 shows as "Filters (n)". */
@Composable internal fun SearchFiltersRow(query: String, onQuery: (String) -> Unit, placeholder: String, onFilters: () -> Unit, activeCount: Int = 0,
    onSearch: (() -> Unit)? = null, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        au.mainspring.nativeapp.ui.AtelierTextField(query, onQuery, Modifier.weight(1f).testTag("service-search"), singleLine = true, placeholder = { Text(placeholder, maxLines = 1, overflow = TextOverflow.Ellipsis) },
            keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Search),
            keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSearch = { onSearch?.invoke() }))
        SecondaryAction(onFilters, Modifier.heightIn(min = 56.dp).testTag("filters-button"), shape = RoundedCornerShape(10.dp)) { Text(if(activeCount > 0) "Filters ($activeCount)" else "Filters") }
    }
}

/** Filters bottom sheet; [content] holds the [FilterSection]s. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun FiltersSheet(onDismiss: () -> Unit, onReset: (() -> Unit)? = null, content: @Composable () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxWidth().testTag("filters-sheet").verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Filters", Modifier.weight(1f).semantics { heading() }, style = MaterialTheme.typography.titleLarge)
                if(onReset != null) TextButton(onReset, Modifier.heightIn(min = 48.dp)) { Text("Reset") }
            }
            content()
            PrimaryAction(onDismiss, Modifier.fillMaxWidth().testTag("filters-done"), shape = RoundedCornerShape(10.dp)) { Text("Done") }
        }
    }
}

/** Titled group of chips inside the Filters sheet. */
@OptIn(ExperimentalLayoutApi::class)
@Composable internal fun FilterSection(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { content() }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

/**
 * One job as a bordered white card (web phone list): job number large in the accent colour, title, customer,
 * a small status pill with "0d in shop", and the quote line. The photo thumbnail sits at the right.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun ServiceJobCard(onClick: () -> Unit, number: String, title: String, customer: String?, statusText: String, statusKey: String,
    daysText: String?, priceLine: String?, thumb: (@Composable () -> Unit)? = null, urgent: Boolean = false, modifier: Modifier = Modifier,
    badges: (@Composable () -> Unit)? = null, onDelete: (() -> Unit)? = null) {
    Surface(onClick, modifier.fillMaxWidth().semantics { role = Role.Button }, shape = RoundedCornerShape(8.dp), color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(number, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary, maxLines = 1)
                Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if(!customer.isNullOrBlank()) Text(customer, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    TonePill(statusText, if(urgent) StatusTone.Late else statusTone(statusKey))
                    badges?.invoke()
                    if(daysText != null) Text(daysText, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                }
                if(priceLine != null) Text(priceLine, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            thumb?.invoke()
            if(onDelete != null) Surface(onDelete, Modifier.size(44.dp).testTag("job-delete").semantics { contentDescription = "Delete $number" }, shape = androidx.compose.foundation.shape.CircleShape,
                color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                Box(contentAlignment = Alignment.Center) { ServiceGlyph("close", color = MaterialTheme.colorScheme.primary, modifier = Modifier) }
            }
        }
    }
}

/** Web-style "0d in shop" caption. */
internal fun shortDaysInShop(days: Int): String = "${days}d in shop"

/** Pill-shaped "New Job" floating button, bottom right. Place inside a Box over the list. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun NewJobFab(onClick: () -> Unit, modifier: Modifier = Modifier, label: String = "New Job") {
    Surface(onClick, modifier.testTag("new-job-fab").semantics { role = Role.Button }, shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.primary,
        contentColor = MaterialTheme.colorScheme.onPrimary, shadowElevation = 6.dp) {
        Row(Modifier.heightIn(min = 52.dp).padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("+", style = MaterialTheme.typography.titleLarge)
            Text(label, style = MaterialTheme.typography.titleSmall)
        }
    }
}

/** Filter chip used inside the sheet. */
@Composable internal fun SheetChip(label: String, selected: Boolean, onClick: () -> Unit, tag: String? = null) =
    au.mainspring.nativeapp.ui.AtelierChip(selected, onClick, { Text(label) }, if(tag != null) Modifier.testTag(tag) else Modifier)

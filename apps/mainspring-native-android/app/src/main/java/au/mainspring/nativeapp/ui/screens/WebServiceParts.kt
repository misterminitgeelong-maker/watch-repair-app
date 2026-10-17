package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.ScrollState
import androidx.compose.material3.Checkbox
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import au.mainspring.nativeapp.ui.GlyphIcon
import au.mainspring.nativeapp.ui.StatusTone
import au.mainspring.nativeapp.ui.toneColors
import kotlinx.coroutines.launch

/**
 * Building blocks that reproduce the web (Capacitor) phone view of the service pages: sand segmented control, accent
 * Board | Cards toggle, outlined and red buttons, bordered selects, kanban columns with coloured top borders.
 * Kept in their own file so the other service screens can adopt them without touching ServiceScreenParts.
 */

/** The warm sand track behind the web's segmented controls. */
internal val WebSand = Color(0xFFF3EADF)

private fun Modifier.tagged(tag: String?): Modifier = if(tag != null) testTag(tag) else this

/** Web button: [primary] is the solid accent button ("+ New Job"), otherwise a white bordered one ("Queue", "..."). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun WebButton(label: String?, onClick: () -> Unit, modifier: Modifier = Modifier, primary: Boolean = false, icon: String? = null,
    enabled: Boolean = true, tag: String? = null, description: String? = null, tint: Boolean = false) {
    val scheme = MaterialTheme.colorScheme
    val container = when { primary -> scheme.primary; tint -> scheme.primaryContainer; else -> scheme.surface }
    val content = when { primary -> scheme.onPrimary; tint -> scheme.primary; else -> scheme.onSurface }
    Surface(onClick, modifier.heightIn(min = 48.dp).tagged(tag).semantics { role = Role.Button; if(description != null) contentDescription = description },
        enabled = enabled, shape = RoundedCornerShape(6.dp), color = container, contentColor = content.copy(alpha = if(enabled) 1f else 0.5f),
        border = if(primary || tint) null else BorderStroke(1.dp, scheme.outlineVariant)) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically) {
            if(icon != null) GlyphIcon(icon, size = 18.dp, color = content.copy(alpha = if(enabled) 1f else 0.5f))
            if(label != null) Text(label, style = MaterialTheme.typography.titleSmall, fontWeight = if(primary) FontWeight.Bold else FontWeight.Medium, maxLines = 1)
        }
    }
}

/** Sand track with a white selected pill (web "Jobs | Services", "Active (2) | Completed (0)"). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun SandSegmented(options: List<ToggleOption>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    val track = if(au.mainspring.nativeapp.ui.LocalCalibrePalette.current.appearance == au.mainspring.nativeapp.ui.AppAppearance.MAINSPRING) WebSand else MaterialTheme.colorScheme.surfaceVariant
    Row(modifier.background(track, RoundedCornerShape(8.dp)).padding(4.dp), horizontalArrangement = Arrangement.spacedBy(2.dp), verticalAlignment = Alignment.CenterVertically) {
        options.forEach { o ->
            val on = o.key == selected
            Surface({ onSelect(o.key) }, Modifier.heightIn(min = 40.dp).tagged(o.tag).semantics { role = Role.Tab },
                shape = RoundedCornerShape(6.dp), color = if(on) MaterialTheme.colorScheme.surface else Color.Transparent) {
                Box(Modifier.padding(horizontal = 14.dp, vertical = 8.dp), contentAlignment = Alignment.Center) {
                    Text(o.label, style = MaterialTheme.typography.labelLarge, fontWeight = if(on) FontWeight.SemiBold else FontWeight.Medium, maxLines = 1,
                        color = if(on) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** Web "Board | Cards" view toggle: the selected option has a thin accent outline and accent text. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun AccentToggle(options: List<ToggleOption>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
        options.forEach { o ->
            val on = o.key == selected
            Surface({ onSelect(o.key) }, Modifier.heightIn(min = 44.dp).tagged(o.tag).semantics { role = Role.Tab }, shape = RoundedCornerShape(6.dp),
                color = if(on) MaterialTheme.colorScheme.surface else Color.Transparent,
                border = if(on) BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null) {
                Box(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), contentAlignment = Alignment.Center) {
                    Text(o.label, style = MaterialTheme.typography.labelLarge, fontWeight = if(on) FontWeight.SemiBold else FontWeight.Medium, maxLines = 1,
                        color = if(on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** Muted row with an icon and a chevron that expands [content] below it (web "Pricing combos & guarantee"). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun CollapsibleRow(label: String, icon: String, expanded: Boolean, onToggle: () -> Unit, modifier: Modifier = Modifier, tag: String? = null,
    content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Surface(onToggle, Modifier.tagged(tag).heightIn(min = 48.dp).semantics { role = Role.Button }, color = Color.Transparent) {
            Row(Modifier.padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                GlyphIcon(icon, size = 18.dp)
                Text(label, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Medium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                GlyphIcon(if(expanded) "chevronUp" else "chevronDown", size = 16.dp)
            }
        }
        if(expanded) content()
    }
}

/** Bordered white select (web <select>): shows [selectedLabel] and a chevron; opens a menu of [options]. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun WebSelect(selectedLabel: String, options: List<Pair<String, String>>, onSelect: (String) -> Unit, modifier: Modifier = Modifier, tag: String? = null,
    description: String? = null, enabled: Boolean = true, onOpen: (() -> Unit)? = null) {
    var open by remember { mutableStateOf(false) }
    Box(modifier.fillMaxWidth()) {
        Surface({ if(onOpen != null) onOpen() else open = true }, Modifier.fillMaxWidth().heightIn(min = 48.dp).tagged(tag).semantics { role = Role.DropdownList; if(description != null) contentDescription = description },
            enabled = enabled, shape = RoundedCornerShape(6.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
            Row(Modifier.padding(horizontal = 14.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(selectedLabel, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface, maxLines = 1, overflow = TextOverflow.Ellipsis)
                GlyphIcon("chevronDown", size = 18.dp, color = MaterialTheme.colorScheme.onSurface)
            }
        }
        DropdownMenu(open, { open = false }) {
            options.forEach { (key, label) -> DropdownMenuItem(text = { Text(label) }, onClick = { open = false; onSelect(key) }, modifier = Modifier.tagged(tag?.let { "$it-$key" })) }
        }
    }
}

/** Bordered white checkbox row (web "Cost outliers only"). */
@Composable internal fun WebCheckRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit, modifier: Modifier = Modifier, tag: String? = null) {
    Surface(modifier.fillMaxWidth().tagged(tag), shape = RoundedCornerShape(6.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Row(Modifier.heightIn(min = 48.dp).toggleable(value = checked, role = Role.Checkbox, onValueChange = onChange).padding(horizontal = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked, null)
            Text(label, Modifier.padding(start = 6.dp), style = MaterialTheme.typography.bodyLarge)
        }
    }
}

/** Bordered white search field with a leading magnifier (web "Search jobs or services..."). */
@Composable internal fun WebSearchField(query: String, onQuery: (String) -> Unit, placeholder: String, modifier: Modifier = Modifier, tag: String = "service-search", onSearch: (() -> Unit)? = null) {
    Surface(modifier.fillMaxWidth(), shape = RoundedCornerShape(6.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Row(Modifier.heightIn(min = 48.dp).padding(horizontal = 14.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
            GlyphIcon("search", size = 18.dp)
            BasicTextField(query, onQuery, Modifier.weight(1f).testTag(tag), singleLine = true, textStyle = MaterialTheme.typography.bodyLarge.copy(color = MaterialTheme.colorScheme.onSurface),
                cursorBrush = SolidColor(MaterialTheme.colorScheme.primary), keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { onSearch?.invoke() }),
                decorationBox = { inner -> Box(contentAlignment = Alignment.CenterStart) {
                    if(query.isEmpty()) Text(placeholder, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    inner()
                } })
        }
    }
}

/** White card with a 1px border, no shadow (web detail cards). */
@Composable internal fun WebCard(modifier: Modifier = Modifier, padding: Dp = 16.dp, content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier.fillMaxWidth(), shape = RoundedCornerShape(6.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(padding), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}

/** Card heading: accent icon, bold title, optional light count and trailing action. */
@Composable internal fun WebCardTitle(title: String, icon: String? = null, count: String? = null, modifier: Modifier = Modifier, trailing: (@Composable () -> Unit)? = null) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        if(icon != null) GlyphIcon(icon, size = 18.dp, color = MaterialTheme.colorScheme.primary)
        Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if(count != null) Text(count, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
        trailing?.invoke()
    }
}

/** Thin grey scrollbar under a horizontally scrolling row (the web shows the browser scrollbar here). */
@Composable internal fun ScrollTrack(state: ScrollState, modifier: Modifier = Modifier) {
    if(state.maxValue <= 0) return
    BoxWithConstraints(modifier.fillMaxWidth().height(5.dp)) {
        val density = LocalDensity.current
        val track = constraints.maxWidth.toFloat()
        val thumb = track * track / (track + state.maxValue)
        val offset = (track - thumb) * state.value / state.maxValue
        Box(Modifier.offset(with(density) { offset.toDp() }).width(with(density) { thumb.toDp() }).height(5.dp).background(Color(0xFFC5CBD2), RoundedCornerShape(3.dp)))
    }
}

/** Horizontal tab chips (web "Jobs & dispatch | Revenue control | Team"): selected is solid accent, the others white. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun ChipTabs(options: List<ToggleOption>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    val scroll = rememberScrollState()
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(Modifier.fillMaxWidth().horizontalScroll(scroll), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            options.forEach { o ->
                val on = o.key == selected
                Surface({ onSelect(o.key) }, Modifier.heightIn(min = 48.dp).tagged(o.tag).semantics { role = Role.Tab }, shape = RoundedCornerShape(6.dp),
                    color = if(on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
                    contentColor = if(on) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant) {
                    Box(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), contentAlignment = Alignment.Center) {
                        Text(o.label, style = MaterialTheme.typography.titleSmall, fontWeight = if(on) FontWeight.Bold else FontWeight.Medium, maxLines = 1)
                    }
                }
            }
        }
        ScrollTrack(scroll)
    }
}

/** One status column of a [WebKanban]. [color] is the top border and job-number colour, [tint] the count badge fill. */
internal data class WebKanbanColumn(val key: String, val label: String, val color: Color, val tint: Color, val cards: List<BoardCard>)

/** Small red-tinted date pill with a calendar icon (web job card "18/10/2026"). */
@Composable internal fun DatePill(text: String, modifier: Modifier = Modifier) {
    Row(modifier.background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(50)).padding(horizontal = 8.dp, vertical = 3.dp),
        horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
        GlyphIcon("calendar", size = 13.dp, color = MaterialTheme.colorScheme.primary)
        Text(text, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, maxLines = 1)
    }
}

/** Small green "0d" age chip on a kanban card. */
@Composable internal fun AgeChip(text: String, modifier: Modifier = Modifier) {
    val c = toneColors(StatusTone.Ready)
    Text(text, modifier.background(c.container, RoundedCornerShape(50)).padding(horizontal = 8.dp, vertical = 2.dp), style = MaterialTheme.typography.labelMedium, color = c.content, maxLines = 1)
}

/**
 * Web kanban: columns scrolled sideways, each a white bordered panel with a 3dp coloured top edge, bold title and a
 * count badge; an empty column says "No jobs in this stage." [card] draws one job (it gets the column colour).
 * A round chevron at the top right scrolls to the next columns, and a grey track shows the scroll position.
 */
@Composable internal fun WebKanban(columns: List<WebKanbanColumn>, modifier: Modifier = Modifier, columnWidth: Dp = 232.dp, minColumnHeight: Dp = 300.dp,
    card: @Composable (BoardCard, Color) -> Unit) {
    val scroll = rememberScrollState()
    val scope = rememberCoroutineScope()
    val density = LocalDensity.current
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Box {
            Row(Modifier.horizontalScroll(scroll).padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {
                columns.forEach { col ->
                    Surface(Modifier.width(columnWidth).testTag("board-column-${col.key}"), shape = RoundedCornerShape(4.dp), color = MaterialTheme.colorScheme.surface,
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                        Column {
                            Box(Modifier.fillMaxWidth().height(3.dp).background(col.color))
                            Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 10.dp, top = 12.dp, bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text(col.label, Modifier.weight(1f), style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text("${col.cards.size}", Modifier.background(col.tint, CircleShape).padding(horizontal = 8.dp, vertical = 1.dp), style = MaterialTheme.typography.labelMedium, color = col.color)
                            }
                            androidx.compose.material3.HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                            Column(Modifier.heightIn(min = minColumnHeight).padding(10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                if(col.cards.isEmpty()) Text("No jobs in this stage.", Modifier.fillMaxWidth().padding(top = 56.dp), style = MaterialTheme.typography.bodySmall,
                                    fontStyle = FontStyle.Italic, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                col.cards.forEach { c -> card(c, col.color) }
                            }
                        }
                    }
                }
            }
            if(scroll.maxValue > 0 && scroll.value < scroll.maxValue) Surface({ scope.launch { scroll.animateScrollTo(scroll.value + with(density) { (columnWidth + 10.dp).toPx() }.toInt()) } },
                Modifier.align(Alignment.TopEnd).padding(top = 10.dp, end = 12.dp).size(36.dp).semantics { contentDescription = "Scroll to next columns" },
                shape = CircleShape, color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), shadowElevation = 1.dp) {
                Box(contentAlignment = Alignment.Center) { GlyphIcon("chevronRight", size = 18.dp, color = MaterialTheme.colorScheme.onSurface) }
            }
        }
        ScrollTrack(scroll, Modifier.padding(horizontal = 16.dp))
    }
}

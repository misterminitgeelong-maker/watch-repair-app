package au.mainspring.nativeapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.heading
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/** One entry in the "..." overflow menu of an [AtelierDetail]. */
data class DetailAction(val label: String, val enabled: Boolean = true, val onClick: () -> Unit)

/** One light inline "Label: value" fact in the header block. [pillStatus] renders the value as a status pill. */
data class DetailFact(val label: String, val value: String, val pillStatus: String? = null, val valueColor: Color? = null, val tag: String? = null)

/**
 * Job detail frame, laid out like the web phone view: "‹ Jobs" back link with Prev / Next at the right, a big
 * display-serif title with a short accent underline, one row with the next-step button and a "..." overflow
 * menu, light inline facts, a [header] slot (contact buttons, workflow stepper), an underlined scrollable tab
 * row and the tab content as spaced cards. The whole page scrolls; the Messages tab keeps its own scroller
 * so only the compact header stays above it.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AtelierDetail(
    backLabel: String,
    title: String,
    facts: List<DetailFact>,
    tabs: List<Pair<String, String>>,
    selectedTab: String,
    onTab: (String) -> Unit,
    onBack: () -> Unit,
    primaryLabel: String?,
    onPrimary: () -> Unit,
    onChangeStatus: () -> Unit,
    modifier: Modifier = Modifier,
    primaryEnabled: Boolean = true,
    primaryTag: String = "detail-primary",
    backEnabled: Boolean = true,
    onPrev: (() -> Unit)? = null,
    onNext: (() -> Unit)? = null,
    showNav: Boolean = onPrev != null || onNext != null,
    menu: List<DetailAction> = emptyList(),
    scrollBody: Boolean = true,
    header: @Composable ColumnScope.() -> Unit = {},
    content: @Composable ColumnScope.(String) -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }
    val calibre = LocalCalibre.current
    val compact = !scrollBody
    val headerBlock: @Composable ColumnScope.() -> Unit = {
        Row(Modifier.fillMaxWidth().statusBarsPadding().padding(start = 8.dp, end = 16.dp, top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack, enabled = backEnabled, modifier = Modifier.heightIn(min = 48.dp).semanticsBack()) {
                Text("‹ $backLabel", style = MaterialTheme.typography.titleSmall)
            }
            Spacer(Modifier.weight(1f))
            if(showNav) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SecondaryAction(onClick = { onPrev?.invoke() }, enabled = backEnabled && onPrev != null, modifier = Modifier.heightIn(min = 44.dp).testTag("job-prev"),
                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)) { Text("‹ Prev") }
                SecondaryAction(onClick = { onNext?.invoke() }, enabled = backEnabled && onNext != null, modifier = Modifier.heightIn(min = 44.dp).testTag("job-next"),
                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)) { Text("Next ›") }
            }
        }
        Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(title, Modifier.padding(top = 4.dp),
                    style = if(calibre) calibreDisplayStyle(MaterialTheme.typography.headlineMedium) else MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.colorScheme.onSurface, maxLines = 3)
                Box(Modifier.width(40.dp).height(3.dp).background(MaterialTheme.colorScheme.primary))
            }
            if(!compact) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    if(primaryLabel != null) AccentAction(onClick = onPrimary, enabled = primaryEnabled, modifier = Modifier.heightIn(min = 48.dp).testTag(primaryTag)) {
                        Text(primaryLabel, style = MaterialTheme.typography.titleSmall, maxLines = 1)
                    }
                    Box {
                        SecondaryAction(onClick = { menuOpen = true }, modifier = Modifier.heightIn(min = 48.dp).widthIn(min = 56.dp).testTag("detail-menu").semantics { contentDescription = "More actions" },
                            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp)) { Text("•••", style = MaterialTheme.typography.titleMedium) }
                        DropdownMenu(menuOpen, { menuOpen = false }) {
                            DropdownMenuItem(text = { Text("Change status") }, enabled = primaryEnabled, onClick = { menuOpen = false; onChangeStatus() })
                            menu.forEach { action -> DropdownMenuItem(text = { Text(action.label) }, enabled = action.enabled, onClick = { menuOpen = false; action.onClick() }) }
                        }
                    }
                }
                if(facts.isNotEmpty()) FlowRow(Modifier.fillMaxWidth().padding(top = 2.dp), horizontalArrangement = Arrangement.spacedBy(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    facts.forEach { f ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(f.label + ": ", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            if(f.pillStatus != null) TonePill(f.value, statusTone(f.pillStatus))
                            else Text(f.value, if(f.tag != null) Modifier.testTag(f.tag) else Modifier, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium, color = f.valueColor ?: MaterialTheme.colorScheme.onSurface)
                        }
                    }
                }
                header()
            }
            if(tabs.size > 1) UnderlineTabs(tabs, selectedTab, onTab)
        }
    }
    if(scrollBody) Column(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).verticalScroll(rememberScrollState()).navigationBarsPadding()) {
        headerBlock()
        Column(Modifier.padding(horizontal = 16.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) { content(selectedTab) }
    } else Column(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        headerBlock()
        Column(Modifier.weight(1f).padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) { content(selectedTab) }
    }
}

/** Web-style tab row: plain labels in a scrollable row, the selected one in the accent colour with an underline. */
@Composable
fun UnderlineTabs(tabs: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            tabs.forEach { (key, label) ->
                val on = key == selected
                Column(Modifier.selectable(selected = on, role = Role.Tab, onClick = { onSelect(key) }).heightIn(min = 48.dp).testTag("tab-$key"), horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(Modifier.heightIn(min = 45.dp), contentAlignment = Alignment.Center) {
                        Text(label, style = MaterialTheme.typography.titleSmall, fontWeight = if(on) FontWeight.SemiBold else FontWeight.Normal, maxLines = 1,
                            color = if(on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(Modifier.height(3.dp).fillMaxWidth().background(if(on) MaterialTheme.colorScheme.primary else Color.Transparent))
                }
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

/** Small heading inside a detail card (mono caps in Calibre, like the web's "JOB TICKET"). */
@Composable
fun CardHeading(text: String, modifier: Modifier = Modifier) {
    if(LocalCalibre.current) MonoLabel(text.uppercase(), modifier.semantics { heading() })
    else Text(text, modifier.semantics { heading() }, style = MaterialTheme.typography.titleMedium)
}

/** Label on the left, value on the right, one line of a detail card. */
@Composable
fun DetailRow(label: String, value: String, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().padding(vertical = 2.dp), horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.Top) {
        Text(label, Modifier.width(96.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, textAlign = androidx.compose.ui.text.style.TextAlign.End)
    }
}

private fun Modifier.semanticsBack(): Modifier = this.then(Modifier.semantics { contentDescription = "Back" })

/** White tappable summary card: bold title with chevron, subtitle, blue hint line (Atelier "Customer & contact ›"). */
@Composable
fun SummaryCard(title: String, subtitle: String?, hint: String?, onClick: (() -> Unit)? = null, modifier: Modifier = Modifier) {
    val content: @Composable ColumnScope.() -> Unit = {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            if(onClick != null) Text("›", style = MaterialTheme.typography.titleLarge)
        }
        subtitle?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        hint?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary) }
    }
    if(onClick != null) ListCard(onClick, modifier, content) else FlatPanel(modifier, content)
}

/** Timeline-style event card used on the Activity tab: bold line, grey detail, caption timestamp. */
@Composable
fun ActivityCard(title: String, detail: String?, time: String?, modifier: Modifier = Modifier) {
    if(LocalCalibre.current) {
        Column(modifier.fillMaxWidth()) {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Column(Modifier.padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(title, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
                detail?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                time?.let { Text(it.uppercase(), Modifier.padding(top = 3.dp), style = Calibre.label, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2) }
            }
        }
        return
    }
    FlatPanel(modifier) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        detail?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        time?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

/** Calibre check/lock row: mono mark in a hairline box, label and optional grey detail. */
@Composable
fun CalibreCheckRow(done: Boolean, title: String, detail: String? = null) {
    Column(Modifier.fillMaxWidth()) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Row(Modifier.padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.size(22.dp).background(if(done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
                Text(if(done) "✓" else "•", style = Calibre.label, color = if(done) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
                detail?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            Text(if(done) "DONE" else "LOCKED", style = Calibre.label, color = if(done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** Atelier intake header: "‹ Today", Discard, eyebrow + large "New intake" title and a Watch / Shoe / Mobile switcher. */
@Composable
fun IntakeHeader(current: String, onBack: () -> Unit, backEnabled: Boolean, onDiscard: () -> Unit, discardEnabled: Boolean,
    services: List<Pair<String, String>>, onSwitch: ((String) -> Unit)?) {
    if(LocalCalibre.current) {
        // Web sheet header: title left, Discard, then the x close at the right; native draft banner and service switcher below.
        Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface)) {
            Row(Modifier.fillMaxWidth().statusBarsPadding().padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(when(current) { "shoe" -> "New Shoe Repair"; "auto_key" -> "New Mobile Job"; else -> "New Job Ticket" }, Modifier.weight(1f).padding(vertical = 12.dp).semantics { heading() },
                    style = MaterialTheme.typography.titleMedium.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold), color = MaterialTheme.colorScheme.onSurface)
                TextButton(onClick = onDiscard, enabled = discardEnabled, modifier = Modifier.heightIn(min = 48.dp)) { Text("Discard") }
                IconButton(onClick = onBack, enabled = backEnabled, modifier = Modifier.semantics { contentDescription = "Back" }) {
                    Text("×", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            if(onSwitch != null && services.size > 1) SegmentedPills(services, current, { if(it != current) onSwitch(it) }, Modifier.padding(horizontal = 16.dp))
            MonoLabel("Draft saved on this device", Modifier.padding(horizontal = 16.dp, vertical = 6.dp))
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
        return
    }
    Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background)) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().padding(start = 12.dp, end = 12.dp, top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack, enabled = backEnabled, modifier = Modifier.heightIn(min = 48.dp).semantics { contentDescription = "Back" }) { Text("\u2039 Today", style = MaterialTheme.typography.titleSmall) }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onDiscard, enabled = discardEnabled, modifier = Modifier.heightIn(min = 48.dp)) { Text("Discard") }
        }
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            if(LocalCalibre.current) MonoLabel("Atelier / Counter · Draft saved on this device") else Text("DRAFT SAVED ON THIS DEVICE", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("New intake", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.onSurface)
            if(onSwitch != null && services.size > 1) SegmentedPills(services, current, { if(it != current) onSwitch(it) }, Modifier.padding(top = 6.dp, bottom = 6.dp))
        }
    }
}

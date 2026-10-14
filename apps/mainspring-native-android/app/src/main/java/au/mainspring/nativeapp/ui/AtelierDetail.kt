package au.mainspring.nativeapp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

/** One entry in the "..." overflow menu of an [AtelierDetail]. */
data class DetailAction(val label: String, val enabled: Boolean = true, val onClick: () -> Unit)

/**
 * Atelier job detail frame: blue "‹ Back" link and "…" menu, big bold title, reference line, dark status
 * banner, segmented Summary/Activity/Messages tabs, scrolling cards, and one blue primary action pinned
 * to the bottom with a small footnote.
 */
@Composable
fun AtelierDetail(
    backLabel: String,
    title: String,
    reference: String?,
    banner: String?,
    tabs: List<Pair<String, String>>,
    selectedTab: String,
    onTab: (String) -> Unit,
    onBack: () -> Unit,
    primaryLabel: String?,
    onPrimary: () -> Unit,
    modifier: Modifier = Modifier,
    primaryEnabled: Boolean = true,
    footnote: String? = null,
    backEnabled: Boolean = true,
    menu: List<DetailAction> = emptyList(),
    scrollBody: Boolean = true,
    content: @Composable ColumnScope.(String) -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }
    Column(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(Modifier.weight(1f)) {
            Row(Modifier.fillMaxWidth().statusBarsPadding().padding(start = 12.dp, end = 12.dp, top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onBack, enabled = backEnabled, modifier = Modifier.heightIn(min = 48.dp).semanticsBack()) {
                    Text("‹ $backLabel", style = MaterialTheme.typography.titleSmall)
                }
                Spacer(Modifier.weight(1f))
                if(menu.isNotEmpty()) Box {
                    TextButton(onClick = { menuOpen = true }, modifier = Modifier.heightIn(min = 48.dp).widthIn(min = 48.dp).testTag("detail-menu")) {
                        Text("•••", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                    }
                    DropdownMenu(menuOpen, { menuOpen = false }) {
                        menu.forEach { action -> DropdownMenuItem(text = { Text(action.label) }, enabled = action.enabled, onClick = { menuOpen = false; action.onClick() }) }
                    }
                }
            }
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(title, style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.onSurface, maxLines = 2)
                reference?.let { if(LocalCalibre.current) MonoLabel(it) else Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                banner?.let {
                    if(LocalCalibre.current) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Box(Modifier.size(7.dp).background(MaterialTheme.colorScheme.primary, androidx.compose.foundation.shape.CircleShape))
                        Text(it, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                    } else Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.secondary, contentColor = MaterialTheme.colorScheme.onSecondary, shape = MaterialTheme.shapes.small) {
                        Text(it, Modifier.padding(horizontal = 16.dp, vertical = 14.dp), style = MaterialTheme.typography.titleSmall)
                    }
                }
                if(tabs.size > 1) SegmentedPills(tabs, selectedTab, onTab)
            }
            val body = if(scrollBody) Modifier.weight(1f).verticalScroll(rememberScrollState()) else Modifier.weight(1f)
            Column(body.padding(start = 20.dp, end = 20.dp, top = 12.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) { content(selectedTab) }
        }
        if(primaryLabel != null) Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 20.dp, vertical = 10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            AccentAction(onClick = onPrimary, enabled = primaryEnabled, modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp).testTag("detail-primary")) {
                Text(primaryLabel, style = MaterialTheme.typography.titleMedium)
            }
            footnote?.let { Text(it, Modifier.padding(top = 6.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
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
                detail?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = Calibre.Muted) }
                time?.let { Text(it.uppercase(), Modifier.padding(top = 3.dp), style = Calibre.label, color = Calibre.Muted, maxLines = 2) }
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
            Box(Modifier.size(22.dp).background(if(done) Calibre.Forest else Calibre.Grey), contentAlignment = Alignment.Center) {
                Text(if(done) "✓" else "•", style = Calibre.label, color = if(done) androidx.compose.ui.graphics.Color.White else Calibre.Muted)
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
                detail?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = Calibre.Muted) }
            }
            Text(if(done) "DONE" else "LOCKED", style = Calibre.label, color = if(done) Calibre.Forest else Calibre.Muted)
        }
    }
}

/** Atelier intake header: "‹ Today", Discard, eyebrow + large "New intake" title and a Watch / Shoe / Mobile switcher. */
@Composable
fun IntakeHeader(current: String, onBack: () -> Unit, backEnabled: Boolean, onDiscard: () -> Unit, discardEnabled: Boolean,
    services: List<Pair<String, String>>, onSwitch: ((String) -> Unit)?) {
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

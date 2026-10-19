package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.ui.*

/** One service the chooser can start: feature key, label, one-line blurb and the wizard route it opens. */
internal data class IntakeService(val key: String, val label: String, val blurb: String, val route: String)

/** Only the services the shop has enabled, in a fixed order. */
internal fun intakeServices(features: Set<String>): List<IntakeService> = buildList {
    if("watch" in features) add(IntakeService("watch", "Watch repair", "Customer, watches, work and photos", "watch_intake"))
    if("shoe" in features) add(IntakeService("shoe", "Shoe repair", "Customer, pairs, services and photos", "shoe_intake"))
    if("auto_key" in features) add(IntakeService("auto_key", "Mobile job", "Customer, vehicle, location and booking", "mobile_intake"))
}

/** "New Job Ticket" chooser: pick a service, then continue into that service's stepped intake. */
@Composable
fun NewIntakeScreen(features: Set<String>, onBack: () -> Unit, onStart: (String) -> Unit) {
    val services = intakeServices(features)
    var selected by rememberSaveable { mutableStateOf(services.firstOrNull()?.key ?: "watch") }
    val current = services.firstOrNull { it.key == selected } ?: services.firstOrNull()
    if(LocalCalibre.current) {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).testTag("new-intake")) {
            Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface)) {
                Row(Modifier.fillMaxWidth().statusBarsPadding().padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("New Job Ticket", Modifier.weight(1f).padding(vertical = 12.dp).semantics { heading() },
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold), color = MaterialTheme.colorScheme.onSurface)
                    IconButton(onClick = onBack, modifier = Modifier.testTag("intake-close").semantics { contentDescription = "Close" }) {
                        Text("×", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
            Column(Modifier.weight(1f).verticalScroll(androidx.compose.foundation.rememberScrollState()).padding(horizontal = 20.dp, vertical = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("What are you booking in?", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface)
                if(services.isEmpty()) Text("No services are enabled for this shop.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                services.forEach { svc ->
                    val isSelected = svc.key == selected
                    SelectableCard(isSelected, { selected = svc.key },
                        Modifier.heightIn(min = 72.dp).testTag("service-${svc.key}").semantics { this.selected = isSelected; role = androidx.compose.ui.semantics.Role.RadioButton }) {
                        Text(svc.label, style = MaterialTheme.typography.titleMedium)
                        Text(svc.blurb, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface)) {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp).navigationBarsPadding(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    PrimaryAction(onClick = { current?.let { onStart(it.route) } }, enabled = current != null,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp).testTag("intake-continue")) {
                        Text("Continue", style = MaterialTheme.typography.titleMedium)
                    }
                    Text("Draft saved on this device", Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        return
    }
    Column(Modifier.fillMaxSize().verticalScrollCompat(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        LargeHeader("Today", "New intake")
        Row(Modifier.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack, modifier = Modifier.heightIn(min = 44.dp)) { Text("‹ Back", style = MaterialTheme.typography.labelLarge) }
        }
        if(services.size > 1) SegmentedPills(services.map { it.key to it.label }, selected, { selected = it }, Modifier.padding(horizontal = 20.dp))
        HeroCard(Modifier.padding(horizontal = 20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                WatchArt()
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(when(selected) { "shoe" -> "Book in a pair"; "auto_key" -> "Start a mobile job"; else -> "Capture the details" }, style = MaterialTheme.typography.titleMedium)
                    Text(current?.blurb.orEmpty(), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        PrimaryAction(onClick = { current?.let { onStart(it.route) } }, enabled = current != null,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).heightIn(min = 52.dp)) {
            Text("Continue", style = MaterialTheme.typography.titleMedium)
        }
        Spacer(Modifier.height(120.dp))
    }
}

@Composable private fun Modifier.verticalScrollCompat(): Modifier = this.then(Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()))

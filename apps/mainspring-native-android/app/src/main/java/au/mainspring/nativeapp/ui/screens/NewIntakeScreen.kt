package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.ui.*

/** Atelier "New intake": pick a service, then continue into that service's stepped intake. */
@Composable
fun NewIntakeScreen(features: Set<String>, onBack: () -> Unit, onStart: (String) -> Unit) {
    val services = buildList {
        if("watch" in features) add(Triple("watch", "Watch", "watch_intake"))
        if("shoe" in features) add(Triple("shoe", "Shoe", "shoe_intake"))
        if("auto_key" in features) add(Triple("auto_key", "Mobile", "mobile_intake"))
    }
    var selected by rememberSaveable { mutableStateOf(services.firstOrNull()?.first ?: "watch") }
    val current = services.firstOrNull { it.first == selected }
    if(LocalCalibre.current) {
        Column(Modifier.fillMaxSize().verticalScrollCompat(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(Modifier.padding(horizontal = 12.dp).statusBarsPadding(), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onBack, modifier = Modifier.heightIn(min = 44.dp)) { Text("‹ Back", style = MaterialTheme.typography.labelLarge) }
            }
            LargeHeader("Intake / Step 1 of 3", "New intake", insets = false)
            if(services.size > 1) SegmentedPills(services.map { it.first to it.second }, selected, { selected = it }, Modifier.padding(horizontal = 20.dp))
            HeroCard(Modifier.padding(horizontal = 20.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    WatchArt()
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        MonoLabel("Capture")
                        Text(when(selected) { "shoe" -> "Book in a pair"; "auto_key" -> "Start a mobile job"; else -> "Capture the details" }, style = MaterialTheme.typography.titleMedium)
                        Text(when(selected) { "shoe" -> "Customer, pairs, services and photos"; "auto_key" -> "Customer, vehicle, location and booking"; else -> "Customer, watches, work and photos" }, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
            Column(Modifier.padding(horizontal = 20.dp)) {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    MonoLabel("Step 1 of 3")
                    MonoLabel("Customer → Item → Work", color = MaterialTheme.colorScheme.primary)
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
            PrimaryAction(onClick = { current?.let { onStart(it.third) } }, enabled = current != null,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).heightIn(min = 52.dp)) {
                Text("Continue", style = MaterialTheme.typography.titleMedium)
            }
            MonoLabel("You can save a draft at any step", Modifier.padding(horizontal = 20.dp))
            Spacer(Modifier.height(120.dp))
        }
        return
    }
    Column(Modifier.fillMaxSize().verticalScrollCompat(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        LargeHeader("Today", "New intake")
        Row(Modifier.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack, modifier = Modifier.heightIn(min = 44.dp)) { Text("‹ Back", style = MaterialTheme.typography.labelLarge) }
        }
        if(services.size > 1) SegmentedPills(services.map { it.first to it.second }, selected, { selected = it }, Modifier.padding(horizontal = 20.dp))
        HeroCard(Modifier.padding(horizontal = 20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                WatchArt()
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(when(selected) { "shoe" -> "Book in a pair"; "auto_key" -> "Start a mobile job"; else -> "Capture the details" }, style = MaterialTheme.typography.titleMedium)
                    Text(when(selected) { "shoe" -> "Customer, pairs, services and photos"; "auto_key" -> "Customer, vehicle, location and booking"; else -> "Customer, watches, work and photos" }, style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        FlatPanelRow("Step 1 of 3", "Customer → Item → Work")
        PrimaryAction(onClick = { current?.let { onStart(it.third) } }, enabled = current != null,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).heightIn(min = 52.dp)) {
            Text("Continue", style = MaterialTheme.typography.titleMedium)
        }
        Spacer(Modifier.height(120.dp))
    }
}

@Composable private fun FlatPanelRow(label: String, value: String) {
    Text("$label · $value", Modifier.padding(horizontal = 24.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable private fun Modifier.verticalScrollCompat(): Modifier = this.then(Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()))

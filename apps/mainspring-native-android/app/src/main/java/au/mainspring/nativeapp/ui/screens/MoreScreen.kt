package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

private data class WorkspaceSection(val key: String, val title: String, val items: List<Pair<String, String>>)

/** More tab: every tool, grouped and named like the web app's menu, always visible (two taps from anywhere), plus settings. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MoreScreen(shop: String?, summary: String?, features: Set<String>, canSwitch: Boolean,
    onSwitch: () -> Unit, onNavigate: (String) -> Unit, onLogout: () -> Unit) {
    val fieldNavigation by DesignPreferences.fieldNavigation.collectAsState()
    val appearance by DesignPreferences.appearance.collectAsState()
    var signOut by remember { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    val owner = TokenStore.canManageInvoices()
    val mobile = "auto_key" in features
    val sections = buildList {
        add(WorkspaceSection("workshop", "Workshop", buildList {
            if(mobile || "shop_mobile_booking" in features) add("Book mobile services" to "bookingRequests")
            if("watch" in features) add("Watch Repairs" to "watch_jobs")
            if("shoe" in features) add("Shoe Repairs" to "shoe_jobs")
            add("Customer Orders" to "customerOrders")
            if("watch" in features) add("Catalogue" to "catalogue")
            if("shoe" in features) add("Shoe services" to "shoeServices")
        }))
        if(mobile) add(WorkspaceSection("mobile", "Mobile services", buildList {
            add("Jobs & dispatch" to "auto_jobs"); add("Send booking request" to "sendBookingRequest"); add("Revenue control" to "revenueControl"); if(owner) add("Finance report" to "financeReport"); add("Dispatch" to "dispatch"); add("Map and today's route" to "route"); add("Dispatch pool" to "dispatchPool")
            add("POS / quick sale" to "counterSale"); add("Lead inbox" to "leads"); add("Prospects" to "prospects")
            if(owner) add("Team" to "team")
            add("Mobile toolkit" to "toolkit")
        }))
        add(WorkspaceSection("business", "Business", buildList {
            if("customer_accounts" in features) add("Customer Accounts" to "businessAccounts")
            add("Quotes" to "quotes"); add("Invoices" to "invoices")
            if(owner) add("Reports" to "reports")
            add("Inventory" to "stock")
            if(owner) add("Database" to "database")
            add("Queued changes" to "queuedChanges")
            add("Accounts" to "accounts")
        }))
    }
    val q = query.trim()
    val shown = sections.map { g -> if(q.isEmpty()) g else g.copy(items = g.items.filter { it.first.contains(q, true) }) }.filter { it.items.isNotEmpty() }
    LazyColumn(Modifier.fillMaxSize().testTag("more-list"), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(0.dp)) {
        item { LargeHeader((shop ?: "Your shop") + " · Every tool in reach", "More") }
        item {
            au.mainspring.nativeapp.ui.AtelierTextField(query, { query = it }, singleLine = true, placeholder = { Text("Find a tool or workflow") }, shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).padding(bottom = 8.dp),
                colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.surface, focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent, focusedBorderColor = MaterialTheme.colorScheme.primary))
        }
        shown.forEach { g ->
            item(key = "h-${g.key}") { SectionLabel(g.title, Modifier.padding(horizontal = 20.dp)) }
            items(g.items, key = { "${g.key}/${it.second}" }) { (label, route) ->
                Column(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).clickable { onNavigate(route) }, verticalAlignment = Alignment.CenterVertically) {
                        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                        Text("\u2192", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            item(key = "e-${g.key}") { HorizontalDivider(Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.outlineVariant) }
        }
        item { if(LocalCalibre.current) SectionLabel("Settings & support", Modifier.padding(horizontal = 20.dp)) else Text("Settings & support", Modifier.padding(horizontal = 24.dp, vertical = 8.dp), style = MaterialTheme.typography.titleMedium) }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if("auto_key" in features && owner) FlatPanel {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text("Use field navigation", Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                        Switch(fieldNavigation, { DesignPreferences.fieldNavigation(it) }, Modifier.semantics { contentDescription = "Use field navigation" })
                    }
                }
                SectionLabel("Appearance")
                AppAppearance.entries.chunked(2).forEach { pair ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        pair.forEach { option ->
                            SelectableCard(appearance == option, { DesignPreferences.select(option) }, Modifier.weight(1f).semantics { selected = appearance == option; role = Role.RadioButton }) {
                                Text(option.label, style = MaterialTheme.typography.labelLarge)
                                Text(if(appearance == option) "Selected" else "Use theme", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
                SectionLabel("Enabled modules")
                FlatPanel {
                    listOf("auto_key" to "Mobile services", "watch" to "Watch repairs", "shoe" to "Shoe repairs").forEach { (key, label) -> DetailRow(label, if(key in features) "Enabled" else "Not enabled") }
                }
                SectionLabel("Shop")
                FlatPanel {
                    DetailRow("Shop", TokenStore.shopValue("name") ?: shop ?: "Current shop")
                    TokenStore.shopValue("abn")?.let { DetailRow("ABN", it) }
                    TokenStore.shopValue("phone")?.let { DetailRow("Shop phone", it) }
                    TokenStore.shopValue("address")?.let { DetailRow("Base address", it) }
                    TokenStore.shopValue("currency")?.let { DetailRow("Currency", it) }
                    DetailRow("Calendar", TokenStore.calendarTimezone())
                    summary?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    if(canSwitch) LinkAction(onSwitch, Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Switch shop") }
                }
                TextButton({ signOut = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Sign out") }
            }
        }
    }
    if(signOut) AlertDialog(onDismissRequest = { signOut = false }, title = { Text("Sign out?") }, text = { Text("Saved drafts remain tied to this shop and account on this device.") },
        confirmButton = { TextButton({ signOut = false; onLogout() }) { Text("Sign out") } }, dismissButton = { TextButton({ signOut = false }) { Text("Cancel") } })
}

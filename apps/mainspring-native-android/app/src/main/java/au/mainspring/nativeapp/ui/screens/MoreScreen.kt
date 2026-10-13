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
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

private data class WorkspaceGroup(val key: String, val title: String, val subtitle: String, val hint: String, val items: List<Pair<String, String>>)

/** More tab: Atelier "Your workspace" — grouped tool cards that expand to their destinations, plus settings. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MoreScreen(shop: String?, summary: String?, features: Set<String>, canSwitch: Boolean,
    onSwitch: () -> Unit, onNavigate: (String) -> Unit, onLogout: () -> Unit) {
    val fieldNavigation by DesignPreferences.fieldNavigation.collectAsState()
    val appearance by DesignPreferences.appearance.collectAsState()
    var signOut by remember { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    var open by rememberSaveable { mutableStateOf<String?>(null) }
    val owner = TokenStore.canManageInvoices()
    val groups = buildList {
        add(WorkspaceGroup("repairs", "Repairs & customer orders",
            listOfNotNull(if("watch" in features) "Watch" else null, if("shoe" in features) "Shoe" else null, if("auto_key" in features) "Mobile services" else null).joinToString(" · ").ifBlank { "All services" },
            "Bookings, dispatch and toolkit",
            buildList {
                if("watch" in features) add("Watch repair jobs" to "watch_jobs")
                if("shoe" in features) add("Shoe repair jobs" to "shoe_jobs")
                if("auto_key" in features) {
                    add("Mobile services jobs" to "auto_jobs"); add("Dispatch" to "dispatch"); add("Map and today's route" to "route"); add("Dispatch pool" to "dispatchPool")
                    add("POS / quick sale" to "counterSale"); add("Mobile toolkit" to "toolkit")
                }
                if("auto_key" in features || "shop_mobile_booking" in features) add("Mobile booking requests" to "bookingRequests")
            }))
        add(WorkspaceGroup("money", "Money & performance", "Quotes · Invoices · Revenue control", "Reports, scorecards and exports",
            buildList { add("Quotes" to "quotes"); add("Invoices" to "invoices"); if(owner) add("Reports" to "reports") }))
        add(WorkspaceGroup("people", "People & network", "Customers · Accounts · Team", "Prospects, shops and regions",
            buildList {
                add("Customers" to "people")
                if("customer_accounts" in features) add("Business accounts" to "businessAccounts")
                if("auto_key" in features) add("Lead inbox & prospects" to "leads")
                if(owner) add("Team & commission" to "team")
            }))
        add(WorkspaceGroup("stock", "Stock & data", "Inventory · Catalogue", "Search and check stock levels", listOf("Inventory" to "stock")))
    }
    val q = query.trim()
    val shown = groups.map { g -> if(q.isEmpty()) g else g.copy(items = g.items.filter { it.first.contains(q, true) || g.title.contains(q, true) }) }.filter { it.items.isNotEmpty() }
    LazyColumn(Modifier.fillMaxSize().testTag("more-list"), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { LargeHeader((shop ?: "Your shop") + " · Every tool in reach", "Your workspace") }
        item {
            au.mainspring.nativeapp.ui.AtelierTextField(query, { query = it }, singleLine = true, placeholder = { Text("Find a tool or workflow") }, shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp),
                colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.surface, focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent, focusedBorderColor = MaterialTheme.colorScheme.primary))
        }
        item { Text("Operations", Modifier.padding(horizontal = 24.dp, vertical = 4.dp), style = MaterialTheme.typography.titleMedium) }
        items(shown, key = { it.key }) { g ->
            val expanded = q.isNotEmpty() || open == g.key
            Surface(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
                Column {
                    Column(Modifier.fillMaxWidth().clickable { open = if(open == g.key) null else g.key }.padding(horizontal = 20.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(g.title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                            Text(if(expanded) "⌃" else "›", style = MaterialTheme.typography.titleLarge)
                        }
                        Text(g.subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(g.hint, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                    }
                    if(expanded) g.items.forEach { (label, route) ->
                        HorizontalDivider(Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.outlineVariant)
                        Row(Modifier.fillMaxWidth().heightIn(min = 52.dp).clickable { onNavigate(route) }.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                            Text("›", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
        item { Text("Settings & support", Modifier.padding(horizontal = 24.dp, vertical = 8.dp), style = MaterialTheme.typography.titleMedium) }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if("auto_key" in features && owner) FlatPanel {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text("Use field navigation", Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                        Switch(fieldNavigation, { DesignPreferences.fieldNavigation(it) })
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
                    if(canSwitch) SecondaryAction(onSwitch, Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Switch shop") }
                }
                TextButton({ signOut = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Sign out") }
            }
        }
    }
    if(signOut) AlertDialog(onDismissRequest = { signOut = false }, title = { Text("Sign out?") }, text = { Text("Saved drafts remain tied to this shop and account on this device.") },
        confirmButton = { TextButton({ signOut = false; onLogout() }) { Text("Sign out") } }, dismissButton = { TextButton({ signOut = false }) { Text("Cancel") } })
}

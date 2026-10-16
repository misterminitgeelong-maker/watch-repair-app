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
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

private data class MoreItem(val label: String, val route: String)
private data class MoreGroup(val key: String, val title: String, val items: List<MoreItem>)

/** Remembers which More groups are open and which tools are used most, per device. */
private object MoreUsage {
    private fun prefs(ctx: android.content.Context) = ctx.getSharedPreferences("more_usage", android.content.Context.MODE_PRIVATE)
    fun expanded(ctx: android.content.Context, default: Set<String>): Set<String> =
        prefs(ctx).let { if(it.contains("expanded")) it.getStringSet("expanded", emptySet()).orEmpty().toSet() else default }
    fun setExpanded(ctx: android.content.Context, keys: Set<String>) { prefs(ctx).edit().putStringSet("expanded", keys).apply() }
    fun counts(ctx: android.content.Context): Map<String, Int> =
        prefs(ctx).all.filterKeys { it.startsWith("use_") }.mapKeys { it.key.removePrefix("use_") }.mapValues { (it.value as? Int) ?: 0 }
    fun bump(ctx: android.content.Context, route: String) { prefs(ctx).let { it.edit().putInt("use_$route", it.getInt("use_$route", 0) + 1).apply() } }
}

/**
 * More tab: grouped, collapsible tools that fit the shop's service plan, a most-used row on top and search.
 * Everything the bottom bar does not show is reachable here in at most two taps.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MoreScreen(shop: String?, summary: String?, features: Set<String>, canSwitch: Boolean,
    onSwitch: () -> Unit, onNavigate: (String) -> Unit, onLogout: () -> Unit) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val fieldNavigation by DesignPreferences.fieldNavigation.collectAsState()
    val appearance by DesignPreferences.appearance.collectAsState()
    var signOut by remember { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    val owner = TokenStore.canManageInvoices()
    val mobile = "auto_key" in features
    val workshop = "watch" in features || "shoe" in features
    val groups = remember(features, owner) {
        val workshopGroup = if(workshop || "shop_mobile_booking" in features) MoreGroup("workshop", "Workshop", buildList {
            if("watch" in features) add(MoreItem("Repair queue", "repairQueue"))
            add(MoreItem("Customer Orders", "customerOrders"))
            if("watch" in features) add(MoreItem("Catalogue", "catalogue"))
            if("shoe" in features) add(MoreItem("Shoe services", "shoeServices"))
            if(!mobile && "shop_mobile_booking" in features) add(MoreItem("Book mobile services", "bookingRequests"))
        }) else null
        val mobileGroup = if(mobile) MoreGroup("mobile", "Mobile services", buildList {
            add(MoreItem("Dispatch", "dispatch")); add(MoreItem("Map and today's route", "route")); add(MoreItem("Dispatch pool", "dispatchPool"))
            add(MoreItem("POS / quick sale", "counterSale")); add(MoreItem("Book mobile services", "bookingRequests")); add(MoreItem("Send booking request", "sendBookingRequest"))
            add(MoreItem("Jobs & dispatch", "auto_jobs")); add(MoreItem("Lead inbox", "leads")); add(MoreItem("Prospects", "prospects")); add(MoreItem("Mobile toolkit", "toolkit"))
        }) else null
        val money = MoreGroup("money", "Money", buildList {
            add(MoreItem("Quotes", "quotes")); add(MoreItem("Invoices", "invoices"))
            if(mobile) add(MoreItem("Revenue control", "revenueControl"))
            if(owner) { add(MoreItem("Reports", "reports")); add(MoreItem("Sales & activity", "reportExtras")); if(mobile) add(MoreItem("Finance report", "financeReport")); add(MoreItem("Database", "database")) }
        })
        val people = MoreGroup("people", "People", buildList {
            add(MoreItem("Customers", "customers"))
            if("customer_accounts" in features) add(MoreItem("Customer Accounts", "businessAccounts"))
            if(owner) add(MoreItem("Team", "team"))
        })
        val shopGroup = MoreGroup("shop", "Shop", buildList {
            add(MoreItem("Inventory", "stock")); if(owner) add(MoreItem("Shop settings", "shopSettings"))
            add(MoreItem("Queued changes", "queuedChanges")); add(MoreItem("Accounts", "accounts"))
        })
        // The shop's own kind of work comes first.
        if(mobile && !workshop) listOfNotNull(mobileGroup, money, people, shopGroup) else listOfNotNull(workshopGroup, mobileGroup, money, people, shopGroup)
    }
    var open by remember { mutableStateOf(MoreUsage.expanded(ctx, emptySet())) }
    fun toggle(key: String) { open = if(key in open) open - key else open + key; MoreUsage.setExpanded(ctx, open) }
    fun go(route: String) { MoreUsage.bump(ctx, route); onNavigate(route) }
    val all = groups.flatMap { it.items }.distinctBy { it.route }
    val usage = remember(groups) { MoreUsage.counts(ctx) }
    val quick = remember(groups) {
        val used = all.filter { (usage[it.route] ?: 0) > 0 }.sortedByDescending { usage[it.route] }
        (used + listOf("customers", "quotes", "invoices", "reports").mapNotNull { r -> all.firstOrNull { it.route == r } }).distinctBy { it.route }.take(4)
    }
    val q = query.trim()
    val matches = if(q.isEmpty()) emptyList() else all.filter { it.label.contains(q, true) }
    LazyColumn(Modifier.fillMaxSize().testTag("more-list"), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(0.dp)) {
        item { LargeHeader(shop ?: "Your shop", "More") }
        item {
            au.mainspring.nativeapp.ui.AtelierTextField(query, { query = it }, singleLine = true, placeholder = { Text("Find a tool") }, shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).padding(bottom = 8.dp).testTag("more-search"),
                colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.surface, focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent, focusedBorderColor = MaterialTheme.colorScheme.primary))
        }
        if(q.isNotEmpty()) {
            if(matches.isEmpty()) item { Text("No tool matches \u201c$q\u201d.", Modifier.padding(horizontal = 20.dp, vertical = 16.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            items(matches, key = { "m/${it.route}" }) { MoreRow(it.label, it.route, Modifier) { go(it.route) } }
        } else {
            item(key = "quick") {
                Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SectionLabel(if(usage.isEmpty()) "Quick access" else "Most used")
                    quick.chunked(2).forEach { pair ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            pair.forEach { item ->
                                val calibre = LocalCalibre.current
                                val tileShape = if(calibre) CalibreCardShape else MaterialTheme.shapes.small
                                Box(Modifier.weight(1f).heightIn(min = if(calibre) 64.dp else 56.dp).background(if(calibre) calibreCardColor() else MaterialTheme.colorScheme.surfaceVariant, tileShape)
                                    .then(if(calibre) Modifier.border(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f), tileShape) else Modifier)
                                    .clip(tileShape).clickable(role = Role.Button) { go(item.route) }.padding(horizontal = 14.dp, vertical = 10.dp), contentAlignment = Alignment.CenterStart) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                        if(calibre) ToolIcon(item.route, size = 24.dp)
                                        Text(item.label, style = MaterialTheme.typography.titleSmall)
                                    }
                                }
                            }
                            if(pair.size == 1) Spacer(Modifier.weight(1f))
                        }
                    }
                }
            }
            groups.forEach { g ->
                val isOpen = g.key in open
                item(key = "h-${g.key}") { MoreGroupHeader(g.title, g.key, g.items.size, isOpen,Modifier.testTag("more-group-${g.key}")) { toggle(g.key) } }
                if(isOpen) items(g.items, key = { "${g.key}/${it.route}" }) { MoreRow(it.label, it.route, Modifier) { go(it.route) } }
            }
            item(key = "h-settings") { MoreGroupHeader("Settings & appearance", "settings", null,"settings" in open, Modifier.testTag("more-group-settings")) { toggle("settings") } }
            if("settings" in open) item(key = "settings") { SettingsPanels(shop, summary, features, canSwitch, onSwitch, fieldNavigation, appearance, owner) }
            item(key = "signout") { TextButton({ signOut = true }, modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth().heightIn(min = 56.dp)) { Text("Sign out") } }
        }
    }
    if(signOut) AlertDialog(onDismissRequest = { signOut = false }, title = { Text("Sign out?") }, text = { Text("Saved drafts remain tied to this shop and account on this device.") },
        confirmButton = { TextButton({ signOut = false; onLogout() }) { Text("Sign out") } }, dismissButton = { TextButton({ signOut = false }) { Text("Cancel") } })
}

@Composable private fun MoreRow(label: String, route: String, modifier: Modifier, onClick: () -> Unit) {
    Column(modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).clickable(role = Role.Button, onClick = onClick), verticalAlignment = Alignment.CenterVertically) {
            if(LocalCalibre.current) { ToolIcon(route, size = 22.dp); Spacer(Modifier.width(14.dp)) }
            Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
            Text("\u2192", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable private fun MoreGroupHeader(title: String, key: String, count: Int?, open: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Column(modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Row(Modifier.fillMaxWidth().heightIn(min = 60.dp).semantics { role = Role.Button; stateDescription = if(open) "Expanded" else "Collapsed" }.clickable(onClick = onClick), verticalAlignment = Alignment.CenterVertically) {
            if(LocalCalibre.current) { ToolIcon(key, size = 24.dp); Spacer(Modifier.width(14.dp)) }
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            if(count != null) Text(count.toString(), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(end = 16.dp))
            Text(if(open) "\u2212" else "+", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable private fun SettingsPanels(shop: String?, summary: String?, features: Set<String>, canSwitch: Boolean, onSwitch: () -> Unit,
    fieldNavigation: Boolean, appearance: AppAppearance, owner: Boolean) {
    Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
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
    }
}

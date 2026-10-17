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
import androidx.compose.ui.unit.sp
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

private data class MoreItem(val label: String, val route: String)

/** Tool tiles per row on the More grid. */
private const val MORE_COLUMNS = 4

/**
 * More tab: a four-column grid of icon tiles for every tool that fits the shop's service plan and role, with search above,
 * then settings and sign out. Anything the bottom bar does not show is one tap away.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MoreScreen(shop: String?, summary: String?, features: Set<String>, canSwitch: Boolean,
    onSwitch: () -> Unit, onNavigate: (String) -> Unit, onLogout: () -> Unit) {
    val fieldNavigation by DesignPreferences.fieldNavigation.collectAsState()
    val appearance by DesignPreferences.appearance.collectAsState()
    var signOut by remember { mutableStateOf(false) }
    var settingsOpen by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    val owner = TokenStore.canManageInvoices()
    val mobile = "auto_key" in features
    val items = remember(features, owner) {
        buildList {
            add(MoreItem("All jobs", "jobs"))
            // A third service line does not fit in the bar, so it lives here.
            if("shoe" in features && TAB_SHOE !in serviceTabKeys(features)) add(MoreItem("Shoe", "shoe_jobs"))
            add(MoreItem("Customers", "customers")); add(MoreItem("Quotes", "quotes")); add(MoreItem("Invoices", "invoices"))
            if(owner) { add(MoreItem("Reports", "reports")); add(MoreItem("Sales & activity", "reportExtras")) }
            add(MoreItem("Inventory", "stock"))
            if("customer_accounts" in features) add(MoreItem("Customer Accounts", "businessAccounts"))
            if(owner) { add(MoreItem("Database", "database")); add(MoreItem("Team", "team")); add(MoreItem("Shop settings", "shopSettings")) }
            add(MoreItem("Queued changes", "queuedChanges"))
            if("watch" in features) add(MoreItem("Repair queue", "repairQueue"))
            add(MoreItem("Accounts", "accounts")); add(MoreItem("Customer Orders", "customerOrders"))
            if("watch" in features) add(MoreItem("Catalogue", "catalogue"))
            if("shoe" in features) add(MoreItem("Shoe services", "shoeServices"))
            if(!mobile && "shop_mobile_booking" in features) add(MoreItem("Book mobile services", "bookingRequests"))
            if(mobile) {
                add(MoreItem("Dispatch", "dispatch")); add(MoreItem("Map and today's route", "route")); add(MoreItem("Dispatch pool", "dispatchPool"))
                add(MoreItem("POS / quick sale", "counterSale")); add(MoreItem("Lead inbox", "leads")); add(MoreItem("Prospects", "prospects")); add(MoreItem("Mobile toolkit", "toolkit"))
                add(MoreItem("Book mobile services", "bookingRequests")); add(MoreItem("Send booking request", "sendBookingRequest"))
                if(owner) add(MoreItem("Finance report", "financeReport"))
                add(MoreItem("Revenue control", "revenueControl"))
            }
        }.distinctBy { it.route }
    }
    val q = query.trim()
    val shown = if(q.isEmpty()) items else items.filter { it.label.contains(q, true) }
    LazyColumn(Modifier.fillMaxSize().testTag("more-list"), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(0.dp)) {
        item { PageTitle("More") }
        item {
            au.mainspring.nativeapp.ui.AtelierTextField(query, { query = it }, singleLine = true, placeholder = { Text("Find a tool") }, shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).padding(bottom = 12.dp).testTag("more-search"),
                colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.surface, focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent, focusedBorderColor = MaterialTheme.colorScheme.primary))
        }
        if(q.isNotEmpty() && shown.isEmpty()) item { Text("No tool matches \u201c$q\u201d.", Modifier.padding(horizontal = 20.dp, vertical = 16.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(shown.chunked(MORE_COLUMNS), key = { row -> "row/" + row.first().route }) { row ->
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp).padding(bottom = 12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { tool -> MoreTile(tool.label, tool.route, Modifier.weight(1f)) { onNavigate(tool.route) } }
                repeat(MORE_COLUMNS - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
        if(q.isEmpty()) {
            item(key = "h-settings") { MoreGroupHeader("Settings & appearance", "settings", settingsOpen, Modifier.testTag("more-group-settings")) { settingsOpen = !settingsOpen } }
            if(settingsOpen) item(key = "settings") { SettingsPanels(shop, summary, features, canSwitch, onSwitch, fieldNavigation, appearance, owner) }
            item(key = "signout") { TextButton({ signOut = true }, modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth().heightIn(min = 56.dp)) { Text("Sign out") } }
        }
    }
    if(signOut) AlertDialog(onDismissRequest = { signOut = false }, title = { Text("Sign out?") }, text = { Text("Saved drafts remain tied to this shop and account on this device.") },
        confirmButton = { TextButton({ signOut = false; onLogout() }) { Text("Sign out") } }, dismissButton = { TextButton({ signOut = false }) { Text("Cancel") } })
}

/** One icon-over-label tool tile, at least 76dp tall. */
@Composable private fun MoreTile(label: String, route: String, modifier: Modifier, onClick: () -> Unit) {
    val calibre = LocalCalibre.current
    val shape = if(calibre) CalibreCardShape else MaterialTheme.shapes.small
    Column(modifier.heightIn(min = 76.dp).background(if(calibre) calibreCardColor() else MaterialTheme.colorScheme.surfaceVariant, shape)
        .then(if(calibre) Modifier.border(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f), shape) else Modifier)
        .clip(shape).clickable(role = Role.Button, onClick = onClick).padding(horizontal = 4.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp, Alignment.CenterVertically)) {
        if(calibre) ToolIcon(route, size = 26.dp)
        Text(label, style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp, lineHeight = 13.sp), textAlign = androidx.compose.ui.text.style.TextAlign.Center, maxLines = 3, color = MaterialTheme.colorScheme.onSurface)
    }
}

@Composable private fun MoreGroupHeader(title: String, key: String, open: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Column(modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Row(Modifier.fillMaxWidth().heightIn(min = 60.dp).semantics { role = Role.Button; stateDescription = if(open) "Expanded" else "Collapsed" }.clickable(onClick = onClick), verticalAlignment = Alignment.CenterVertically) {
            if(LocalCalibre.current) { ToolIcon(key, size = 24.dp); Spacer(Modifier.width(14.dp)) }
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
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

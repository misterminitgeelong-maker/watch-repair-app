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
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import au.mainspring.nativeapp.AppLock
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

internal data class MoreItem(val label: String, val route: String, val children: List<MoreItem> = emptyList())

/** The More grid: a handful of main tools plus three group tiles that open a smaller grid of their own. */
internal fun moreTools(features: Set<String>, owner: Boolean): List<MoreItem> {
    val mobile = "auto_key" in features
    val workshop = buildList {
        if("watch" in features) add(MoreItem("Repair queue", "repairQueue"))
        add(MoreItem("Customer Orders", "customerOrders"))
        if("watch" in features) add(MoreItem("Catalogue", "catalogue"))
        if("shoe" in features) add(MoreItem("Shoe services", "shoeServices"))
        if(!mobile && "shop_mobile_booking" in features) add(MoreItem("Book mobile services", "bookingRequests"))
    }
    val mobileTools = if(!mobile) emptyList() else buildList {
        add(MoreItem("Dispatch", "dispatch")); add(MoreItem("Map and today's route", "route")); add(MoreItem("Dispatch pool", "dispatchPool"))
        add(MoreItem("POS / quick sale", "counterSale")); add(MoreItem("Lead inbox", "leads")); add(MoreItem("Prospects", "prospects")); add(MoreItem("Mobile toolkit", "toolkit"))
        add(MoreItem("Book mobile services", "bookingRequests")); add(MoreItem("Send booking request", "sendBookingRequest"))
        if(owner) add(MoreItem("Finance report", "financeReport"))
        add(MoreItem("Revenue control", "revenueControl"))
    }
    val shop = buildList {
        if(owner) { add(MoreItem("Sales & activity", "reportExtras")); add(MoreItem("Database", "database")); add(MoreItem("Team", "team")); add(MoreItem("Shop settings", "shopSettings")) }
        add(MoreItem("Queued changes", "queuedChanges")); add(MoreItem("Accounts", "accounts"))
    }
    return buildList {
        add(MoreItem("All jobs", "jobs"))
        // A third service line does not fit in the bar, so it lives here.
        if("shoe" in features && TAB_SHOE !in serviceTabKeys(features)) add(MoreItem("Shoe", "shoe_jobs"))
        add(MoreItem("Customers", "customers")); add(MoreItem("Quotes", "quotes")); add(MoreItem("Invoices", "invoices"))
        if(owner) add(MoreItem("Reports", "reports"))
        add(MoreItem("Inventory", "stock"))
        if("customer_accounts" in features) add(MoreItem("Customer Accounts", "businessAccounts"))
        if(workshop.isNotEmpty()) add(MoreItem("Workshop tools", "toolsWorkshop", workshop))
        if(mobileTools.isNotEmpty()) add(MoreItem("Mobile tools", "toolsMobile", mobileTools))
        add(MoreItem("Shop & team", "toolsShop", shop))
    }.distinctBy { it.route }
}

/** Title and tiles of one group tile, or null for an unknown key. */
internal fun moreToolGroup(route: String, features: Set<String>, owner: Boolean): MoreItem? = moreTools(features, owner).firstOrNull { it.route == route && it.children.isNotEmpty() }

/** The smaller grid a group tile opens. */
@Composable fun ToolsGridScreen(route: String, features: Set<String>, onBack: () -> Unit, onNavigate: (String) -> Unit) {
    val group = moreToolGroup(route, features, TokenStore.canManageInvoices())
    val cols = moreColumns()
    LazyColumn(Modifier.fillMaxSize().testTag("tools-grid"), contentPadding = PaddingValues(bottom = 112.dp)) {
        item { TextButton(onBack, Modifier.padding(horizontal = 8.dp).heightIn(min = 48.dp)) { Text("\u2039 More") } }
        item { PageTitle(group?.label ?: "Tools") }
        items((group?.children ?: emptyList()).chunked(cols), key = { row -> "row/" + row.first().route }) { row ->
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp).padding(bottom = 12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { tool -> MoreTile(tool.label, tool.route, Modifier.weight(1f)) { onNavigate(tool.route) } }
                repeat(cols - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

/** Tool tiles per row on the More grid. */
/** Four tiles per row, two when the text is very large so labels do not break mid-word. */
@Composable private fun moreColumns(): Int = if(androidx.compose.ui.platform.LocalDensity.current.fontScale > 1.3f) 2 else 4

/**
 * More tab, as on the web phone view: a compact popup sheet anchored above the bottom bar over a dimmed page, with a
 * four-column grid of icon tiles (every tool that fits the shop's plan and role, plus Settings), a divider and a red
 * Sign out row. A small search field sits at the top of the sheet. Settings opens the settings and appearance panels.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MoreScreen(shop: String?, summary: String?, features: Set<String>, canSwitch: Boolean,
    onSwitch: () -> Unit, onNavigate: (String) -> Unit, onLogout: () -> Unit, onDismiss: () -> Unit = {}) {
    val fieldNavigation by DesignPreferences.fieldNavigation.collectAsState()
    val appearance by DesignPreferences.appearance.collectAsState()
    var signOut by remember { mutableStateOf(false) }
    var settingsOpen by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    val owner = TokenStore.canManageInvoices()
    val items = remember(features, owner) { moreTools(features, owner) }
    val everyTool = remember(items) { (items.flatMap { if(it.children.isEmpty()) listOf(it) else it.children } + MoreItem("Settings", "settings")).distinctBy { it.route } }
    val q = query.trim()
    val shown = if(q.isEmpty()) items + MoreItem("Settings", "settings") else everyTool.filter { it.label.contains(q, true) }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.32f)).clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onDismiss))
        Surface(Modifier.align(Alignment.BottomCenter).padding(horizontal = 12.dp, vertical = 10.dp).widthIn(max = 480.dp).fillMaxWidth().heightIn(max = maxHeight * 0.92f),
            color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(12.dp), shadowElevation = 14.dp,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
            val cols = moreColumns()
            LazyColumn(Modifier.testTag("more-list"), contentPadding = PaddingValues(top = 12.dp)) {
                item {
                    au.mainspring.nativeapp.ui.AtelierTextField(query, { query = it }, singleLine = true, placeholder = { Text("Find a tool") }, shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp).padding(bottom = 6.dp).testTag("more-search"),
                        colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.background, focusedContainerColor = MaterialTheme.colorScheme.background,
                            unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant, focusedBorderColor = MaterialTheme.colorScheme.primary))
                }
                if(q.isNotEmpty() && shown.isEmpty()) item { Text("No tool matches \u201c$q\u201d.", Modifier.padding(horizontal = 20.dp, vertical = 16.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                items(shown.chunked(cols), key = { row -> "row/" + row.first().route }) { row ->
                    Row(Modifier.fillMaxWidth().padding(horizontal = 6.dp)) {
                        row.forEach { tool ->
                            val tag = if(tool.route == "settings") Modifier.testTag("more-group-settings") else Modifier
                            MoreTile(tool.label, tool.route, Modifier.weight(1f).then(tag), plain = true) { if(tool.route == "settings") settingsOpen = true else onNavigate(tool.route) }
                        }
                        repeat(cols - row.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
                if(q.isEmpty()) {
                    item(key = "divider") { HorizontalDivider(Modifier.padding(top = 4.dp), color = MaterialTheme.colorScheme.outlineVariant) }
                    item(key = "signout") {
                        val red = MaterialTheme.colorScheme.primary
                        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).clickable(role = Role.Button) { signOut = true }, horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                            SignOutGlyph(red); Spacer(Modifier.width(8.dp))
                            Text("Sign out", style = MaterialTheme.typography.titleSmall, color = red)
                        }
                    }
                }
            }
        }
    }
    if(settingsOpen) androidx.compose.ui.window.Dialog({ settingsOpen = false }, androidx.compose.ui.window.DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            LazyColumn(Modifier.statusBarsPadding().testTag("settings-list"), contentPadding = PaddingValues(bottom = 48.dp)) {
                item { TextButton({ settingsOpen = false }, Modifier.padding(horizontal = 8.dp).heightIn(min = 48.dp)) { Text("\u2039 More") } }
                item { PageTitle("Settings & appearance") }
                item(key = "settings") { SettingsPanels(shop, summary, features, canSwitch, onSwitch, fieldNavigation, appearance, owner) }
            }
        }
    }
    if(signOut) AlertDialog(onDismissRequest = { signOut = false }, title = { Text("Sign out?") }, text = { Text("Saved drafts remain tied to this shop and account on this device.") },
        confirmButton = { TextButton({ signOut = false; onLogout() }) { Text("Sign out") } }, dismissButton = { TextButton({ signOut = false }) { Text("Cancel") } })
}

/** Exit glyph: a door bracket with an arrow leaving it. */
@Composable private fun SignOutGlyph(color: Color) {
    androidx.compose.foundation.Canvas(Modifier.size(20.dp)) {
        val s = size.width / 24f; val w = 1.8f * s
        fun l(a: Float, b: Float, c: Float, d: Float) = drawLine(color, androidx.compose.ui.geometry.Offset(a * s, b * s), androidx.compose.ui.geometry.Offset(c * s, d * s), w, cap = androidx.compose.ui.graphics.StrokeCap.Round)
        l(10f, 4f, 5f, 4f); l(5f, 4f, 5f, 20f); l(5f, 20f, 10f, 20f); l(10f, 12f, 21f, 12f); l(17f, 8f, 21f, 12f); l(17f, 16f, 21f, 12f)
    }
}

/** One icon-over-label tool tile, at least 76dp tall. [plain] drops the card (the More sheet draws bare tiles). */
@Composable internal fun MoreTile(label: String, route: String, modifier: Modifier, plain: Boolean = false, onClick: () -> Unit) {
    val calibre = LocalCalibre.current
    if(plain) {
        Column(modifier.heightIn(min = 76.dp).clip(RoundedCornerShape(8.dp)).clickable(role = Role.Button, onClick = onClick).padding(horizontal = 2.dp, vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterVertically)) {
            ToolIcon(route, size = 24.dp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.78f))
            Text(label, style = MaterialTheme.typography.labelMedium.copy(fontSize = 12.sp, lineHeight = 14.sp), textAlign = androidx.compose.ui.text.style.TextAlign.Center, maxLines = 2, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f))
        }
        return
    }
    val shape = if(calibre) CalibreCardShape else MaterialTheme.shapes.small
    Column(modifier.heightIn(min = 76.dp).background(if(calibre) calibreCardColor() else MaterialTheme.colorScheme.surfaceVariant, shape)
        .then(if(calibre) Modifier.border(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f), shape) else Modifier)
        .clip(shape).clickable(role = Role.Button, onClick = onClick).padding(horizontal = 4.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp, Alignment.CenterVertically)) {
        if(calibre) ToolIcon(route, size = 26.dp)
        Text(label, style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp, lineHeight = 13.sp), textAlign = androidx.compose.ui.text.style.TextAlign.Center, maxLines = 3, color = MaterialTheme.colorScheme.onSurface)
    }
}

/** "Unlock with fingerprint, face or phone PIN": only shown when the phone has a screen lock; turning it on asks the phone first. */
@Composable private fun AppLockSetting() {
    val context = androidx.compose.ui.platform.LocalContext.current
    if(!AppLock.available(context)) return
    var on by remember { mutableStateOf(AppLock.enabled()) }
    var note by remember { mutableStateOf<String?>(null) }
    FlatPanel {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Unlock with fingerprint, face or PIN", style = MaterialTheme.typography.bodyLarge)
                Text("Asks your phone to unlock Mainspring when you open it. Your shop password is never asked for.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(on, { want ->
                note = null
                if(!want) { AppLock.setEnabled(false); on = false }
                else context.findFragmentActivity()?.let { act ->
                    AppLock.prompt(act, "Turn on unlock", { AppLock.setEnabled(true); on = true }, { note = it })
                }
            }, Modifier.testTag("app-lock-switch").semantics { contentDescription = "Unlock with fingerprint, face or PIN" })
        }
        note?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
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
        AppLockSetting()
        FlatPanel { au.mainspring.nativeapp.ui.PushSettingRow() }
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

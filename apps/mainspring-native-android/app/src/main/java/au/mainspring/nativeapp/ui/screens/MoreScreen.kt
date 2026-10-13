package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MoreScreen(shop: String?, summary: String?, features: Set<String>, canSwitch: Boolean,
    onSwitch: () -> Unit, onNavigate: (String) -> Unit, onLogout: () -> Unit) {
    val fieldNavigation by DesignPreferences.fieldNavigation.collectAsState()
    val appearance by DesignPreferences.appearance.collectAsState()
    var signOut by remember { mutableStateOf(false) }
    Scaffold(topBar={TopAppBar(title={Column {
        shop?.let {Text(it.uppercase(),style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
        Text("More",style=MaterialTheme.typography.headlineMedium)
    }})}) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("more-list"),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
            item {
                SectionLabel("Workspace")
                MoreLink("Home dashboard",{onNavigate("home")})
                MoreLink("Customers",{onNavigate("customers")})
                if("auto_key" in features) {
                    MoreLink("Mobile services jobs",{onNavigate("auto_jobs")})
                    MoreLink("Map and today's route",{onNavigate("route")})
                    MoreLink("Dispatch pool",{onNavigate("dispatchPool")})
                    MoreLink("POS / quick sale",{onNavigate("counterSale")})
                    MoreLink("Mobile toolkit",{onNavigate("toolkit")})
                    MoreLink("Lead inbox & prospects",{onNavigate("leads")})
                }
                if("watch" in features) { MoreLink("Watch repair jobs",{onNavigate("jobs")});MoreLink("Quotes",{onNavigate("quotes")});MoreLink("Invoices",{onNavigate("invoices")}) }
                if("shoe" in features) MoreLink("Shoe repair jobs",{onNavigate("shoe_jobs")})
                MoreLink("Inbox",{onNavigate("inbox")})
                if("auto_key" in features || "shop_mobile_booking" in features) MoreLink("Mobile booking requests",{onNavigate("bookingRequests")})
                if("customer_accounts" in features) MoreLink("Business accounts",{onNavigate("businessAccounts")})
                MoreLink("Inventory and stocktakes",{onNavigate("stock")})
                if(TokenStore.canManageInvoices()) { MoreLink("Reports",{onNavigate("reports")});MoreLink("Team & commission",{onNavigate("team")}) }
            }
            item {
                if("auto_key" in features && TokenStore.canManageInvoices()) Row(Modifier.fillMaxWidth(),verticalAlignment=androidx.compose.ui.Alignment.CenterVertically) {
                    Text("Use field navigation",Modifier.weight(1f),style=MaterialTheme.typography.bodyMedium)
                    Switch(fieldNavigation,{DesignPreferences.fieldNavigation(it)})
                }
                SectionLabel("Theme")
                AppAppearance.entries.chunked(2).forEach { pair -> Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    pair.forEach { option -> Surface(Modifier.weight(1f).padding(bottom=8.dp).clickable {DesignPreferences.select(option)}.semantics {selected=appearance==option;role=Role.RadioButton},
                        color=if(appearance==option) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
                        border=BorderStroke(if(appearance==option) 2.dp else 1.dp,if(appearance==option) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)) {
                        Column(Modifier.padding(12.dp)) {Text(option.label,style=MaterialTheme.typography.labelLarge);Text(if(appearance==option) "Selected" else "Use theme",style=MaterialTheme.typography.bodySmall)}
                    } }
                } }
            }
            item {
                SectionLabel("Enabled modules")
                FlatPanel {
                    listOf("auto_key" to "Mobile services","watch" to "Watch repairs","shoe" to "Shoe repairs").forEach { (key,label) -> DetailRow(label,if(key in features) "Enabled" else "Not enabled") }
                }
            }
            item {
                SectionLabel("Shop")
                FlatPanel {
                    DetailRow("Shop",TokenStore.shopValue("name") ?: shop ?: "Current shop")
                    TokenStore.shopValue("abn")?.let {DetailRow("ABN",it)}
                    TokenStore.shopValue("phone")?.let {DetailRow("Shop phone",it)}
                    TokenStore.shopValue("address")?.let {DetailRow("Base address",it)}
                    TokenStore.shopValue("currency")?.let {DetailRow("Currency",it)}
                    DetailRow("Calendar",TokenStore.calendarTimezone())
                    summary?.let {Text(it,style=MaterialTheme.typography.bodySmall)}
                    if(canSwitch) OutlinedButton(onSwitch,shape=MaterialTheme.shapes.small) {Text("Switch shop")}
                }
                TextButton({signOut=true},modifier=Modifier.fillMaxWidth()) {Text("Sign out")}
            }
        }
    }
    if(signOut) AlertDialog(onDismissRequest={signOut=false},title={Text("Sign out?")},text={Text("Saved drafts remain tied to this shop and account on this device.")},
        confirmButton={TextButton({signOut=false;onLogout()}) {Text("Sign out")}},dismissButton={TextButton({signOut=false}) {Text("Cancel")}})
}

@Composable private fun MoreLink(label: String,onClick: () -> Unit) {
    Surface(Modifier.fillMaxWidth().clickable(onClick=onClick),color=MaterialTheme.colorScheme.surface) {
        Row(Modifier.padding(horizontal=12.dp,vertical=16.dp),horizontalArrangement=Arrangement.SpaceBetween) {Text(label,style=MaterialTheme.typography.bodyMedium);Text("›")}
    }
    HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
}

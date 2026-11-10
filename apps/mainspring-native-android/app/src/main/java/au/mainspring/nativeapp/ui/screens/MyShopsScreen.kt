package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MyShopsScreen(onBack: () -> Unit, onSwitchSite: (String) -> Unit, onMembershipChanged: () -> Unit = {}, vm: MyShopsViewModel = viewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    var add by rememberSaveable { mutableStateOf(false) }
    var create by rememberSaveable { mutableStateOf(false) }
    var name by rememberSaveable { mutableStateOf("") }
    var slug by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var number by rememberSaveable { mutableStateOf("") }
    var plan by rememberSaveable { mutableStateOf("basic_all_tabs") }
    var confirm by remember { mutableStateOf<Pair<String, () -> Unit>?>(null) }
    val enabled = !s.busy && !s.loading && !s.unknown
    val canWrite = TokenStore.isOwner() && s.summary?.role == "hq_admin"
    Scaffold(topBar = { AtelierTopAppBar(title = { Text("My Shops") }, navigationIcon = { BackButton(onClick = onBack) }, actions = { TextButton(vm::refresh, enabled = !s.busy) { Text("Refresh") } }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                if(s.loading || s.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                s.error?.let { ErrorBanner(it) }; s.info?.let { Text(it) }
                if(s.unknown) { Text("An earlier change needs review. Refresh and check the current records before trying again."); TextButton(vm::reviewed, enabled = s.reviewed && !s.busy) { Text("I have reviewed the current records") } }
                s.summary?.let { Text(it.name, style = MaterialTheme.typography.titleLarge); Text("${it.siteCount} linked locations") }
                if(canWrite) Button({ add = true }, enabled = enabled) { Text("Add Shop") }
            }
            if(s.invitations.isNotEmpty()) item { SectionLabel("NETWORK INVITATIONS") }
            items(s.invitations, key = { "invitation-${it.id}" }) { request -> FlatPanel {
                Text(request.parentName, style = MaterialTheme.typography.titleMedium)
                Text("${request.tenantName} has been invited to join this network. Accepting links this shop to the network.")
                Text(formatShopDate(request.createdAt))
                Row { TextButton({ confirm = "Join ${request.parentName}?" to { vm.invitation(request, true, onMembershipChanged) } }, enabled = enabled) { Text("Accept") }; TextButton({ confirm = "Decline ${request.parentName}?" to { vm.invitation(request, false, onMembershipChanged) } }, enabled = enabled) { Text("Decline") } }
            } }
            if(s.summary == null && !s.loading) item { EmptyState("This account has no linked network", "Ask your network owner to send a link request for this shop. Invitations appear here for the shop owner to accept.") }
            if(s.summary != null) {
                item { OutlinedTextField(s.query, vm::query, label = { Text("Find a shop") }, modifier = Modifier.fillMaxWidth()) }
                items(s.shops, key = { it.id }) { shop -> FlatPanel {
                    Text("${shop.number?.let { "#$it · " }.orEmpty()}${shop.name}", style = MaterialTheme.typography.titleMedium)
                    Text("${shop.slug} · ${shop.plan.replace('_', ' ')} · ${shop.networkRole}")
                    Text(shop.ownerEmail); shop.region?.let { Text(it) }
                    if(shop.id == TokenStore.currentTenantId()) Text("Current shop") else Row {
                        TextButton({ onSwitchSite(shop.id) }, enabled = enabled) { Text("Switch to this shop") }
                        if(canWrite) TextButton({ confirm = "Remove ${shop.name} from this account?" to { vm.unlink(shop); onMembershipChanged() } }, enabled = enabled) { Text("Remove") }
                    }
                } }
                if(s.shops.size < s.total) item { TextButton(vm::more, enabled = !s.loading) { Text("Load more shops (${s.shops.size} of ${s.total})") } }
                if(s.summary?.pending.orEmpty().isNotEmpty()) item { SectionLabel("PENDING LINK REQUESTS") }
                items(s.summary?.pending.orEmpty(), key = { "pending-${it.id}" }) { request -> Text("${request.tenantName} · ${request.slug} · Awaiting shop owner acceptance") }
                item {
                    SectionLabel("SHOP BOOKING USAGE")
                    OutlinedTextField(s.month, vm::month, label = { Text("Month (YYYY-MM)") })
                    s.usageError?.let { ErrorBanner(it) }
                    s.usage?.let { usage -> Text("${usage.count} shops with booking access"); usage.shops.forEach { shop -> DetailRow("${shop.number?.let { "#$it · " }.orEmpty()}${shop.name}", "${shop.accepted} accepted · ${shop.pending} pending") } }
                }
                item { SectionLabel("RECENT ACTIVITY"); s.activityError?.let { ErrorBanner(it) } }
                items(s.activity, key = { "activity-${it.id}" }) { activity -> Text("${formatShopDate(activity.createdAt)} · ${activity.summary}") }
            }
        }
    }
    confirm?.let { (title, action) -> AlertDialog(onDismissRequest = { confirm = null }, title = { Text(title) }, confirmButton = { TextButton({ confirm = null; action() }) { Text("Confirm") } }, dismissButton = { TextButton({ confirm = null }) { Text("Cancel") } }) }
    if(add) AlertDialog(onDismissRequest = { if(!s.busy) add = false }, title = { Text("Add Shop") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row { FilterChip(!create, { create = false }, label = { Text("Link existing") }); FilterChip(create, { create = true }, label = { Text("Create new") }) }
            if(create) OutlinedTextField(name, { name = it }, label = { Text("Shop name") }, enabled = !s.busy)
            OutlinedTextField(slug, { slug = it }, label = { Text("Shop login ID") }, enabled = !s.busy)
            OutlinedTextField(number, { number = it }, label = { Text("Shop number (optional)") }, enabled = !s.busy)
            if(!create) { OutlinedTextField(email, { email = it }, label = { Text("Owner email") }, enabled = !s.busy); Text("The existing shop owner receives a request and must accept it.") }
            else {
                Text("Starting plan")
                Row(Modifier.horizontalScroll(rememberScrollState())) { listOf("booking_only" to "Booking only", "basic_watch" to "Watch", "basic_shoe" to "Shoe", "basic_auto_key" to "Mobile", "basic_all_tabs" to "All services", "pro" to "Pro").forEach { (key, label) -> FilterChip(plan == key, { plan = key }, label = { Text(label) }) } }
                Text("Creates a shop under this account. Billing and entitlements follow the account’s existing plan rules.")
            }
            s.error?.let { ErrorBanner(it) }
        }
    }, confirmButton = { TextButton({ vm.save(create, name, slug, email, number, plan) { add = false; name = ""; slug = ""; email = ""; number = ""; onMembershipChanged() } }, enabled = enabled) { Text(if(s.busy) "Saving…" else if(create) "Create shop" else "Send link request") } }, dismissButton = { TextButton({ add = false }, enabled = !s.busy) { Text("Cancel") } })
}

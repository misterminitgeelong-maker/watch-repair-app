package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.CUSTOMER_NON_ACTIVE_STATUSES
import androidx.compose.ui.platform.testTag
import au.mainspring.nativeapp.ui.RefreshOnResume
import au.mainspring.nativeapp.ui.formatShopDate

private data class CustomerHistoryRow(val id: String, val number: String, val title: String, val status: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerDetailScreen(customerId: String, onBack: () -> Unit, onOpenWatchJob: (String) -> Unit,
    onEdit: (String) -> Unit, onNewRepair: (String) -> Unit,
    features: Set<String> = setOf("watch"), onOpenShoeJob: (String) -> Unit = {}, onOpenMobileJob: (String) -> Unit = {},
    onNewShoe: (String) -> Unit = {}, onNewMobile: (String) -> Unit = {},
    onAddWatch: (String) -> Unit = {}, onEditWatch: (String) -> Unit = {},
    vm: CustomerDetailViewModel = viewModel(key = customerId, factory = CustomerDetailViewModel.factory(customerId,features))) {
    val state by vm.state.collectAsStateWithLifecycle()
    RefreshOnResume(vm::load)
    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text(state.customer?.fullName ?: "Customer") },
        navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
        actions = {
            TextButton(onClick = vm::load, enabled = !state.loading && state.paging == null, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") }
            if(state.customer != null) TextButton(onClick = { onEdit(customerId) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Edit") }
        }) }) { padding ->
        when {
            state.loading && state.customer == null -> LinearProgressIndicator(Modifier.padding(padding).fillMaxWidth())
            state.customer == null -> Column(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = vm::load) }
            }
            else -> {
                val customer = state.customer!!
                var tab by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("jobs") }
                var jobView by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("active") }
                val inView = { status: String -> (status in CUSTOMER_NON_ACTIVE_STATUSES) == (jobView == "completed") }
                LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    item {
                        if(state.loading || state.paging != null) LinearProgressIndicator(Modifier.fillMaxWidth())
                        state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = vm::load) }
                        val contact = listOf("Phone" to customer.phone, "Email" to customer.email, "Address" to customer.address, "Notes" to customer.notes).filter { !it.second.isNullOrBlank() }
                        au.mainspring.nativeapp.ui.FlatPanel {
                            val initials = customer.fullName.split(' ').filter { it.isNotBlank() }.take(2).joinToString("") { it.take(1).uppercase() }.ifBlank { "?" }
                            if(au.mainspring.nativeapp.ui.LocalCalibre.current) Row(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                au.mainspring.nativeapp.ui.InitialsAvatar(customer.fullName, size = 72.dp)
                                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                    au.mainspring.nativeapp.ui.MonoLabel("Customer profile")
                                    Text("Customer since ${formatShopDate(customer.createdAt).substringBefore(' ')}", style = MaterialTheme.typography.titleMedium)
                                }
                            } else {
                            Text(initials, style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.primary)
                            Text("Customer since ${formatShopDate(customer.createdAt).substringBefore(' ')}", style = MaterialTheme.typography.titleMedium)
                            }
                            au.mainspring.nativeapp.ui.ContactQuickActions(customer.phone, customer.email, Modifier.fillMaxWidth())
                            au.mainspring.nativeapp.ui.SectionLabel("Overview")
                            if(contact.isEmpty()) Text("No contact details on file.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            contact.forEach { (label, value) -> au.mainspring.nativeapp.ui.DetailRow(label, value.orEmpty()) }
                            TextButton({ onEdit(customerId) }, modifier = Modifier.heightIn(min = 44.dp)) { Text("Edit details") }
                        }
                    }
                    item {
                        val jobTotal = state.watchJobs.size + state.shoeJobs.size + state.mobileJobs.size
                        au.mainspring.nativeapp.ui.SegmentedPills(customerTabs(features, jobTotal, state.watches.size, state.orders.size.takeIf { state.ordersLoaded }), tab, { tab = it })
                    }
                    if(tab == "orders") {
                        val currency = TokenStore.shopValue("currency") ?: "AUD"
                        item {
                            state.ordersError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = vm::load) }
                            if(state.ordersLoaded && state.orders.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No orders yet", "Customer orders will appear here once one is created.")
                            else if(!state.ordersLoaded && state.ordersError == null) LinearProgressIndicator(Modifier.fillMaxWidth())
                        }
                        items(state.orders, key = { "order/${it.id}" }) { order ->
                            au.mainspring.nativeapp.ui.FlatPanel(Modifier.testTag("customer-order-row")) {
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                    Text(order.title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                                    au.mainspring.nativeapp.ui.StatusPill(order.status)
                                }
                                val detail = listOfNotNull(order.supplier?.takeIf { it.isNotBlank() }, order.priority.takeIf { it != "normal" }?.let { "${au.mainspring.nativeapp.ui.statusLabel(it)} priority" },
                                    order.estimatedCostCents.takeIf { it > 0 }?.let { au.mainspring.nativeapp.ui.formatCents(it, currency) }).joinToString(" · ")
                                if(detail.isNotEmpty()) Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    if(tab == "account") item {
                        LoyaltyAndMergeSection(state, vm, customer.fullName)
                    }
                    if(tab == "jobs") item {
                        val services = listOf("watch" in features, "shoe" in features, "auto_key" in features)
                        val first = customer.fullName.substringBefore(' ')
                        if(services.count { it } == 1) au.mainspring.nativeapp.ui.PrimaryAction(onClick = { if(services[0]) onNewRepair(customerId) else if(services[1]) onNewShoe(customerId) else onNewMobile(customerId) },
                            modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("Start a new job for $first", style = MaterialTheme.typography.titleMedium) }
                        else au.mainspring.nativeapp.ui.SectionLabel("Start a new job for $first")
                        Column(Modifier.fillMaxWidth().padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            if("watch" in features) OutlinedButton(onClick = { onNewRepair(customerId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("New watch repair") }
                            if("shoe" in features) OutlinedButton(onClick = { onNewShoe(customerId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("New shoe repair") }
                            if("auto_key" in features) OutlinedButton(onClick = { onNewMobile(customerId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("New mobile job") }
                        }
                    }
                    if(tab == "jobs") item {
                        val all = state.watchJobs.map { it.status } + state.shoeJobs.map { it.status } + state.mobileJobs.map { it.status }
                        val activeCount = all.count { it !in CUSTOMER_NON_ACTIVE_STATUSES }
                        au.mainspring.nativeapp.ui.SegmentedPills(listOf("active" to "Active ($activeCount)", "completed" to "Completed (${all.size - activeCount})"), jobView, { jobView = it })
                    }
                    if(tab == "watches" && "watch" in features) {
                        item {
                            au.mainspring.nativeapp.ui.SectionLabel("Watches (${state.watches.size})")
                            state.historyErrors["watches"]?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
                            if(state.watches.isEmpty() && "watches" !in state.historyErrors) Text("No watches on file.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        items(state.watches,key = { "watch/${it.id}" }) { watch ->
                            au.mainspring.nativeapp.ui.FlatPanel {
                                Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                    Column(Modifier.weight(1f)) {
                                        Text(listOfNotNull(watch.brand,watch.model).joinToString(" ").ifBlank { "Watch" }, style = MaterialTheme.typography.titleMedium)
                                        listOfNotNull(watch.serialNumber?.let { "Serial $it" }, watch.movementType).takeIf { it.isNotEmpty() }?.let { Text(it.joinToString(" \u00b7 "), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                                    }
                                    TextButton({ onEditWatch(watch.id) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Edit") }
                                }
                            }
                        }
                        item { OutlinedButton({ onAddWatch(customerId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Add watch") } }
                        if("watches" in state.more) item { OutlinedButton(onClick = { vm.loadMore("watches") },enabled = !state.loading && state.paging == null, modifier = Modifier.fillMaxWidth()) { Text("Load older watches") } }
                    }
                    if(tab == "jobs" && "watch" in features) historySection("Watch repair jobs","watch",state.watchJobs.filter { inView(it.status) }.map { CustomerHistoryRow(it.id,it.jobNumber,it.title,it.status) },state,onOpenWatchJob,vm)
                    if(tab == "jobs" && "shoe" in features) historySection("Shoe repair jobs","shoe",state.shoeJobs.filter { inView(it.status) }.map { CustomerHistoryRow(it.id,it.jobNumber,it.title,it.status) },state,onOpenShoeJob,vm)
                    if(tab == "jobs" && "auto_key" in features) historySection("Mobile service jobs","mobile",state.mobileJobs.filter { inView(it.status) }.map { CustomerHistoryRow(it.id,it.jobNumber,it.title,it.status) },state,onOpenMobileJob,vm)
                }
            }
        }
    }
}

/** Segment keys and labels for the customer profile; counts make each tab worth opening before tapping it. */
internal fun customerTabs(features: Set<String>, jobCount: Int, watchCount: Int, orderCount: Int?): List<Pair<String, String>> = buildList {
    add("jobs" to "Jobs ($jobCount)")
    if("watch" in features) add("watches" to "Watches ($watchCount)")
    add("orders" to if(orderCount != null) "Orders ($orderCount)" else "Orders")
    add("account" to "Account")
}

private fun LazyListScope.historySection(title: String, section: String, rows: List<CustomerHistoryRow>, state: CustomerDetailUiState,
    onOpen: (String) -> Unit, vm: CustomerDetailViewModel) {
    item {
        au.mainspring.nativeapp.ui.SectionLabel("$title (${rows.size})")
        state.historyErrors[section]?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
        if(rows.isEmpty() && section !in state.historyErrors) Text("No ${title.lowercase()} for this customer.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    items(rows,key = { "$section/job/${it.id}" }) { row ->
        au.mainspring.nativeapp.ui.ListCard({ onOpen(row.id) }) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text(row.number, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                au.mainspring.nativeapp.ui.StatusPill(row.status)
            }
            Text(row.title, style = MaterialTheme.typography.titleMedium)
        }
    }
    if(section in state.more) item { OutlinedButton(onClick = { vm.loadMore(section) },enabled = !state.loading && state.paging == null, modifier = Modifier.fillMaxWidth()) { Text("Load older $section jobs") } }
}

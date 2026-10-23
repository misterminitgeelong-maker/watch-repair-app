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
import androidx.compose.foundation.background
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import au.mainspring.nativeapp.ui.calibreDisplayStyle

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
    Scaffold(topBar = { if(!au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text(state.customer?.fullName ?: "Customer") },
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
                if(au.mainspring.nativeapp.ui.LocalCalibre.current) {
                    CalibreCustomerBody(Modifier.padding(padding), customer, state, vm, features, onBack, onEdit, onNewRepair, onNewShoe, onNewMobile,
                        onAddWatch, onEditWatch, onOpenWatchJob, onOpenShoeJob, onOpenMobileJob)
                    return@Scaffold
                }
                var tab by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("jobs") }
                var jobView by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("active") }
                val inView = { status: String -> (status in CUSTOMER_NON_ACTIVE_STATUSES) == (jobView == "completed") }
                LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(if(au.mainspring.nativeapp.ui.LocalCalibre.current) 20.dp else 16.dp), verticalArrangement = Arrangement.spacedBy(if(au.mainspring.nativeapp.ui.LocalCalibre.current) 14.dp else 8.dp)) {
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

/** Web phone layout of the customer page: back link, serif name, actions, Email line, Watches and Repair Jobs cards; native extras follow as cards. */
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun CalibreCustomerBody(modifier: Modifier, customer: au.mainspring.nativeapp.api.CustomerRead, state: CustomerDetailUiState, vm: CustomerDetailViewModel, features: Set<String>,
    onBack: () -> Unit, onEdit: (String) -> Unit, onNewRepair: (String) -> Unit, onNewShoe: (String) -> Unit, onNewMobile: (String) -> Unit,
    onAddWatch: (String) -> Unit, onEditWatch: (String) -> Unit, onOpenWatchJob: (String) -> Unit, onOpenShoeJob: (String) -> Unit, onOpenMobileJob: (String) -> Unit) {
    val id = customer.id
    var jobView by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf("active") }
    val inView = { status: String -> (status in CUSTOMER_NON_ACTIVE_STATUSES) == (jobView == "completed") }
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    val line = MaterialTheme.colorScheme.outlineVariant
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    val watchOnly = features.contains("watch") && !features.contains("shoe") && !features.contains("auto_key")
    val all = state.watchJobs.map { it.status } + state.shoeJobs.map { it.status } + state.mobileJobs.map { it.status }
    val activeCount = all.count { it !in CUSTOMER_NON_ACTIVE_STATUSES }
    val shown = state.watchJobs.count { inView(it.status) } + state.shoeJobs.count { inView(it.status) } + state.mobileJobs.count { inView(it.status) }
    val contact = listOf("Phone" to customer.phone, "Email" to customer.email, "Address" to customer.address, "Notes" to customer.notes).filter { !it.second.isNullOrBlank() }
    @Composable fun Card(content: @Composable ColumnScope.() -> Unit) = Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface, shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, line)) { Column(content = content) }
    @Composable fun CardTitle(text: String) { Text(text, Modifier.padding(horizontal = 20.dp, vertical = 16.dp), style = MaterialTheme.typography.titleMedium, fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold); HorizontalDivider(color = line) }
    LazyColumn(modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if(state.loading || state.paging != null) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = vm::load) }
                TextButton(onBack, Modifier.heightIn(min = 48.dp)) { Text("‹  Back to Customers", color = muted) }
                Column {
                    Text(customer.fullName, style = au.mainspring.nativeapp.ui.calibreDisplayStyle(MaterialTheme.typography.headlineLarge), maxLines = 2)
                    Box(Modifier.padding(top = 8.dp).width(28.dp).height(3.dp).background(MaterialTheme.colorScheme.primary))
                }
                androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if("watch" in features) IconLabelButton("plus", "Add Watch", { onAddWatch(id) })
                    if("watch" in features) NewTicketButton("New Job Ticket", { onNewRepair(id) }, glyph = "wrench", fullWidth = false)
                    if("shoe" in features) OutlinedButton(onClick = { onNewShoe(id) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("New shoe repair") }
                    if("auto_key" in features) OutlinedButton(onClick = { onNewMobile(id) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("New mobile job") }
                    if(!watchOnly && "watch" in features) OutlinedButton(onClick = { onNewRepair(id) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("New watch repair") }
                }
                customer.email?.takeIf { it.isNotBlank() }?.let { Text(buildAnnotatedString { withStyle(SpanStyle(fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold)) { append("Email: ") }; append(it) }, style = MaterialTheme.typography.bodyMedium, color = muted) }
            }
        }
        if("watch" in features) item {
            Card {
                CardTitle("Watches (${state.watches.size})")
                state.historyErrors["watches"]?.let { Box(Modifier.padding(16.dp)) { au.mainspring.nativeapp.ui.ErrorBanner(it) } }
                if(state.watches.isEmpty() && "watches" !in state.historyErrors) Text("No watches on file.", Modifier.padding(20.dp), style = MaterialTheme.typography.bodyMedium, color = muted)
                state.watches.forEachIndexed { i, watch ->
                    if(i > 0) HorizontalDivider(color = line)
                    Surface({ onEditWatch(watch.id) }, color = MaterialTheme.colorScheme.surface) {
                        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 16.dp)) {
                            Text(listOfNotNull(watch.brand, watch.model).joinToString(" ").ifBlank { "Watch" }, style = MaterialTheme.typography.bodyLarge)
                            listOfNotNull(watch.serialNumber?.let { "Serial $it" }, watch.movementType).takeIf { it.isNotEmpty() }?.let { Text(it.joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = muted) }
                        }
                    }
                }
                if("watches" in state.more) OutlinedButton(onClick = { vm.loadMore("watches") }, enabled = !state.loading && state.paging == null, modifier = Modifier.fillMaxWidth().padding(12.dp)) { Text("Load older watches") }
            }
        }
        item {
            Card {
                CardTitle("Repair Jobs (${all.size})")
                Box(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                    SandSegmented(listOf(ToggleOption("active", "Active ($activeCount)", "segment-active"), ToggleOption("completed", "Completed (${all.size - activeCount})", "segment-completed")), jobView, { jobView = it })
                }
                HorizontalDivider(color = line)
                if(shown == 0) Text(if(jobView == "active") "No active jobs." else "No completed jobs.", Modifier.padding(20.dp), style = MaterialTheme.typography.bodyMedium,
                    fontStyle = androidx.compose.ui.text.font.FontStyle.Italic, color = muted)
            }
        }
        if("watch" in features) historySection("Watch repair jobs", "watch", state.watchJobs.filter { inView(it.status) }.map { CustomerHistoryRow(it.id, it.jobNumber, it.title, it.status) }, state, onOpenWatchJob, vm)
        if("shoe" in features) historySection("Shoe repair jobs", "shoe", state.shoeJobs.filter { inView(it.status) }.map { CustomerHistoryRow(it.id, it.jobNumber, it.title, it.status) }, state, onOpenShoeJob, vm)
        if("auto_key" in features) historySection("Mobile service jobs", "mobile", state.mobileJobs.filter { inView(it.status) }.map { CustomerHistoryRow(it.id, it.jobNumber, it.title, it.status) }, state, onOpenMobileJob, vm)
        item {
            Card {
                CardTitle("Contact")
                Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    au.mainspring.nativeapp.ui.ContactQuickActions(customer.phone, customer.email, Modifier.fillMaxWidth())
                    Text("Customer since ${formatShopDate(customer.createdAt).substringBefore(' ')}", style = MaterialTheme.typography.bodyMedium, color = muted)
                    if(contact.isEmpty()) Text("No contact details on file.", style = MaterialTheme.typography.bodyMedium, color = muted)
                    contact.forEach { (label, value) -> au.mainspring.nativeapp.ui.DetailRow(label, value.orEmpty()) }
                    TextButton({ onEdit(id) }, modifier = Modifier.heightIn(min = 44.dp)) { Text("Edit details") }
                }
            }
        }
        item {
            Card {
                CardTitle(if(state.ordersLoaded) "Orders (${state.orders.size})" else "Orders")
                Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    state.ordersError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = vm::load) }
                    if(state.ordersLoaded && state.orders.isEmpty()) Text("No orders yet. Customer orders will appear here once one is created.", style = MaterialTheme.typography.bodyMedium, color = muted)
                    else if(!state.ordersLoaded && state.ordersError == null) LinearProgressIndicator(Modifier.fillMaxWidth())
                    state.orders.forEach { order ->
                        Column(Modifier.fillMaxWidth().testTag("customer-order-row"), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Text(order.title, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                                au.mainspring.nativeapp.ui.StatusPill(order.status)
                            }
                            val detail = listOfNotNull(order.supplier?.takeIf { it.isNotBlank() }, order.priority.takeIf { it != "normal" }?.let { "${au.mainspring.nativeapp.ui.statusLabel(it)} priority" },
                                order.estimatedCostCents.takeIf { it > 0 }?.let { au.mainspring.nativeapp.ui.formatCents(it, currency) }).joinToString(" · ")
                            if(detail.isNotEmpty()) Text(detail, style = MaterialTheme.typography.bodySmall, color = muted)
                        }
                    }
                }
            }
        }
        item {
            Card {
                CardTitle("Account")
                Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { LoyaltyAndMergeSection(state, vm, customer.fullName) }
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

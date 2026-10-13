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
    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text(state.customer?.fullName ?: "Customer", style = MaterialTheme.typography.titleLarge) },
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
                LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    item {
                        if(state.loading || state.paging != null) LinearProgressIndicator(Modifier.fillMaxWidth())
                        state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = vm::load) }
                        val contact = listOf("Phone" to customer.phone, "Email" to customer.email, "Address" to customer.address, "Notes" to customer.notes).filter { !it.second.isNullOrBlank() }
                        val context = androidx.compose.ui.platform.LocalContext.current
                        au.mainspring.nativeapp.ui.FlatPanel {
                            Text(customer.fullName.split(' ').filter { it.isNotBlank() }.take(2).joinToString("") { it.take(1).uppercase() }.ifBlank { "?" },
                                style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.primary)
                            Text("Customer since ${formatShopDate(customer.createdAt).substringBefore(' ')}", style = MaterialTheme.typography.titleMedium)
                            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                if(!customer.phone.isNullOrBlank()) TextButton({ runCatching { context.startActivity(android.content.Intent(android.content.Intent.ACTION_DIAL, android.net.Uri.fromParts("tel", customer.phone, null))) } }, modifier = Modifier.heightIn(min = 44.dp)) { Text("Call") }
                                if(!customer.email.isNullOrBlank()) TextButton({ runCatching { context.startActivity(android.content.Intent(android.content.Intent.ACTION_SENDTO, android.net.Uri.fromParts("mailto", customer.email, null))) } }, modifier = Modifier.heightIn(min = 44.dp)) { Text("Email") }
                                TextButton({ onEdit(customerId) }, modifier = Modifier.heightIn(min = 44.dp)) { Text("Edit details") }
                            }
                            if(contact.isEmpty()) Text("No contact details on file.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            contact.forEach { (label, value) -> au.mainspring.nativeapp.ui.DetailRow(label, value.orEmpty()) }
                        }
                    }
                    item {
                        au.mainspring.nativeapp.ui.SectionLabel("Start something for ${customer.fullName.substringBefore(' ')}")
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            if("watch" in features) OutlinedButton(onClick = { onNewRepair(customerId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("New watch repair") }
                            if("shoe" in features) OutlinedButton(onClick = { onNewShoe(customerId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("New shoe repair") }
                            if("auto_key" in features) OutlinedButton(onClick = { onNewMobile(customerId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("New mobile job") }
                        }
                    }
                    if("watch" in features) {
                        item {
                            au.mainspring.nativeapp.ui.SectionLabel("Watches")
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
                        historySection("Watch repair jobs","watch",state.watchJobs.map { CustomerHistoryRow(it.id,it.jobNumber,it.title,it.status) },state,onOpenWatchJob,vm)
                    }
                    if("shoe" in features) historySection("Shoe repair jobs","shoe",state.shoeJobs.map { CustomerHistoryRow(it.id,it.jobNumber,it.title,it.status) },state,onOpenShoeJob,vm)
                    if("auto_key" in features) historySection("Mobile service jobs","mobile",state.mobileJobs.map { CustomerHistoryRow(it.id,it.jobNumber,it.title,it.status) },state,onOpenMobileJob,vm)
                }
            }
        }
    }
}

private fun LazyListScope.historySection(title: String, section: String, rows: List<CustomerHistoryRow>, state: CustomerDetailUiState,
    onOpen: (String) -> Unit, vm: CustomerDetailViewModel) {
    item {
        au.mainspring.nativeapp.ui.SectionLabel(title)
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

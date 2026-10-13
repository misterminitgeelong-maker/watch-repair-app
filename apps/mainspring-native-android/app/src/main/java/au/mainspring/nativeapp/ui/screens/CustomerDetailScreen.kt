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
    Scaffold(topBar = { TopAppBar(title = { Text(state.customer?.fullName ?: "Customer") },
        navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
        actions = { if(state.customer != null) TextButton(onClick = { onEdit(customerId) }) { Text("Edit") } }) }) { padding ->
        when {
            state.loading && state.customer == null -> CircularProgressIndicator(Modifier.padding(padding).padding(24.dp))
            state.customer == null -> Column(Modifier.padding(padding).padding(16.dp)) {
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                OutlinedButton(onClick = vm::load) { Text("Retry customer") }
            }
            else -> {
                val customer = state.customer!!
                LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    item {
                        if(state.loading || state.paging != null) LinearProgressIndicator(Modifier.fillMaxWidth())
                        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                        OutlinedButton(onClick = vm::load, enabled = !state.loading && state.paging == null) { Text("Refresh customer and history") }
                        listOf("Email" to customer.email, "Phone" to customer.phone, "Address" to customer.address, "Notes" to customer.notes).forEach { (label,value) ->
                            if(!value.isNullOrBlank()) { Text(label, style = MaterialTheme.typography.labelMedium); Text(value) }
                        }
                        Text("Created ${formatShopDate(customer.createdAt)}", style = MaterialTheme.typography.bodySmall)
                        if("watch" in features) OutlinedButton(onClick = { onNewRepair(customerId) }) { Text("New watch repair") }
                        if("shoe" in features) OutlinedButton(onClick = { onNewShoe(customerId) }) { Text("New shoe repair") }
                        if("auto_key" in features) OutlinedButton(onClick = { onNewMobile(customerId) }) { Text("New mobile job") }
                    }
                    if("watch" in features) {
                        item { HorizontalDivider(); Text("Watches", style = MaterialTheme.typography.titleMedium)
                            state.historyErrors["watches"]?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                            OutlinedButton({ onAddWatch(customerId) }) { Text("Add watch") }
                            if(state.watches.isEmpty() && "watches" !in state.historyErrors) Text("No watches on file.") }
                        items(state.watches,key = { "watch/${it.id}" }) { watch ->
                            Column { Text(listOfNotNull(watch.brand,watch.model).joinToString(" · ").ifBlank { "Watch" }); watch.serialNumber?.let { Text("Serial $it") }; watch.movementType?.let { Text(it) }; OutlinedButton({ onEditWatch(watch.id) }) { Text("Edit ${watch.brand ?: "watch"} ${watch.model.orEmpty()}") } }
                        }
                        if("watches" in state.more) item { OutlinedButton(onClick = { vm.loadMore("watches") },enabled = !state.loading && state.paging == null) { Text("Load older watches") } }
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
    item { HorizontalDivider(); Text(title, style = MaterialTheme.typography.titleMedium)
        state.historyErrors[section]?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if(rows.isEmpty() && section !in state.historyErrors) Text("No ${title.lowercase()} for this customer.") }
    items(rows,key = { "$section/job/${it.id}" }) { row -> Column(Modifier.fillMaxWidth().clickable { onOpen(row.id) }.padding(vertical = 8.dp)) {
        Text("${row.number} · ${row.status.replace('_',' ')}", style = MaterialTheme.typography.titleSmall); Text(row.title)
    } }
    if(section in state.more) item { OutlinedButton(onClick = { vm.loadMore(section) },enabled = !state.loading && state.paging == null) { Text("Load older $section jobs") } }
}

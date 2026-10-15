package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CUSTOMER_ORDER_PRIORITIES
import au.mainspring.nativeapp.CUSTOMER_ORDER_STATUSES
import au.mainspring.nativeapp.CustomerOrdersViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.CustomerOrderRead
import au.mainspring.nativeapp.api.CustomerRead
import androidx.compose.ui.platform.testTag
import au.mainspring.nativeapp.ui.*

@Composable fun CustomerOrdersScreen(onBack: () -> Unit, viewModel: CustomerOrdersViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    var selected by remember { mutableStateOf<CustomerOrderRead?>(null) }
    var creating by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<CustomerOrderRead?>(null) }
    var deleting by remember { mutableStateOf<CustomerOrderRead?>(null) }
    var importing by remember { mutableStateOf(false) }
    Scaffold(topBar = { BackLargeHeader("More", "Workshop", "Customer orders", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            item {
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    TabChip(state.filter == null, { viewModel.filter(null) }, { Text("All") })
                    CUSTOMER_ORDER_STATUSES.forEach { s -> TabChip(state.filter == s, { viewModel.filter(s) }, { Text(statusLabel(s)) }) }
                }
                PrimaryAction({ creating = true }, Modifier.fillMaxWidth().padding(top = 8.dp)) { Text("New order") }
                SecondaryAction({ importing = true }, Modifier.fillMaxWidth().padding(top = 8.dp).testTag("customer-order-import")) { Text("Import from CSV or Excel") }
                if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 8.dp))
            }
            state.error?.let { item { ErrorBanner(it, onRetry = viewModel::refresh) } }
            if(!state.loading && state.error == null && state.orders.isEmpty()) item {
                EmptyState("No customer orders", if(state.filter == null) "Items ordered on a customer's behalf will appear here." else "No orders with this status.",
                    "New order", { creating = true })
            }
            items(state.orders, key = { it.id }) { order ->
                ListCard({ selected = order }) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(order.title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                        StatusPill(order.status)
                    }
                    order.customerName?.takeIf { it.isNotBlank() }?.let { MonoLabel(it) }
                    val detail = listOfNotNull(order.supplier?.takeIf { it.isNotBlank() }, order.priority.takeIf { it != "normal" }?.let { "${statusLabel(it)} priority" }, order.estimatedCostCents.takeIf { it > 0 }?.let { formatCents(it, currency) }).joinToString(" · ")
                    if(detail.isNotEmpty()) Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
    if(importing) OrderImportDialog(onDismiss = { importing = false }, onImported = viewModel::refresh)
    selected?.let { order ->
        AlertDialog(onDismissRequest = { selected = null }, title = { Text(order.title) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    MonoLabel("Set status")
                    CUSTOMER_ORDER_STATUSES.forEach { s ->
                        TabChip(order.status == s, { viewModel.setStatus(order, s) { selected = null } }, { Text(statusLabel(s)) }, enabled = !state.saving)
                    }
                    MonoLabel("Priority: ${statusLabel(order.priority)}")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SecondaryAction({ editing = order; selected = null }, enabled = !state.saving) { Text("Edit") }
                        SecondaryAction({ deleting = order; selected = null }, enabled = !state.saving, modifier = Modifier.testTag("customer-order-delete")) { Text("Delete") }
                    }
                    state.error?.let { ErrorBanner(it) }
                }
            },
            confirmButton = { TextButton({ selected = null }) { Text("Close") } })
    }
    deleting?.let { order ->
        AlertDialog(onDismissRequest = { if(!state.saving) deleting = null }, title = { Text("Delete this order?") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("\"${order.title}\" will be permanently deleted.")
                state.error?.let { ErrorBanner(it) }
            } },
            confirmButton = { PrimaryAction({ viewModel.delete(order) { deleting = null } }, enabled = !state.saving, modifier = Modifier.testTag("customer-order-delete-confirm")) { Text("Delete order") } },
            dismissButton = { SecondaryAction({ deleting = null }, enabled = !state.saving) { Text("Cancel") } })
    }
    editing?.let { order ->
        NewCustomerOrderDialog(state.saving, state.error, emptyList(), false, null, {}, { editing = null }, initial = order) { title, supplier, cents, notes, priority, _ ->
            viewModel.edit(order, title, supplier, cents, notes, priority) { editing = null }
        }
    }
    if(creating) NewCustomerOrderDialog(state.saving, state.error, state.customerResults, state.customerSearching, state.customerError,
        viewModel::searchCustomers, { creating = false; viewModel.clearCustomerSearch() }) { title, supplier, cents, notes, priority, customerId ->
        viewModel.create(title, supplier, cents, notes, priority, customerId) { creating = false; viewModel.clearCustomerSearch() }
    }
}

@Composable private fun NewCustomerOrderDialog(saving: Boolean, error: String?, results: List<CustomerRead>, searching: Boolean, searchError: String?,
    onSearch: (String) -> Unit, onDismiss: () -> Unit, initial: CustomerOrderRead? = null, onSave: (String, String, Int, String, String, String?) -> Unit) {
    var priority by remember { mutableStateOf(initial?.priority ?: "normal") }
    var customer by remember { mutableStateOf<CustomerRead?>(null) }
    var customerQuery by remember { mutableStateOf("") }
    var title by remember { mutableStateOf(initial?.title.orEmpty()) }
    var supplier by remember { mutableStateOf(initial?.supplier.orEmpty()) }
    var cost by remember { mutableStateOf(initial?.estimatedCostCents?.takeIf { it > 0 }?.let { java.math.BigDecimal(it).movePointLeft(2).toPlainString() }.orEmpty()) }
    var notes by remember { mutableStateOf(initial?.notes.orEmpty()) }
    val cents = cost.trim().ifBlank { "0" }.toBigDecimalOrNull()?.takeIf { it.signum() >= 0 }?.movePointRight(2)?.toInt()
    AlertDialog(onDismissRequest = onDismiss, title = { Text(if(initial != null) "Edit order" else "New order") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                AtelierTextField(title, { title = it }, singleLine = true, label = { Text("Title") }, modifier = Modifier.fillMaxWidth())
                AtelierTextField(supplier, { supplier = it }, singleLine = true, label = { Text("Supplier") }, modifier = Modifier.fillMaxWidth())
                AtelierTextField(cost, { cost = it }, singleLine = true, label = { Text("Estimated cost") }, isError = cents == null, modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                AtelierTextField(notes, { notes = it }, label = { Text("Notes") }, minLines = 2, modifier = Modifier.fillMaxWidth())
                MonoLabel("Priority")
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    CUSTOMER_ORDER_PRIORITIES.forEach { p -> TabChip(priority == p, { priority = p }, { Text(statusLabel(p)) }) }
                }
                if(initial == null) MonoLabel("Customer (optional)")
                val picked = customer
                if(initial != null) {
                    initial.customerName?.takeIf { it.isNotBlank() }?.let { Text("Customer: $it", style = MaterialTheme.typography.bodyMedium) }
                } else if(picked != null) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(picked.fullName, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                        TextButton({ customer = null }) { Text("Change") }
                    }
                } else {
                    AtelierTextField(customerQuery, { customerQuery = it; onSearch(it) }, singleLine = true, label = { Text("Search customers") }, modifier = Modifier.fillMaxWidth())
                    if(searching) LinearProgressIndicator(Modifier.fillMaxWidth())
                    searchError?.let { ErrorBanner(it) }
                    results.take(5).forEach { c ->
                        TextButton({ customer = c; customerQuery = ""; onSearch("") }, Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                            Text(listOfNotNull(c.fullName, c.phone?.takeIf { it.isNotBlank() }).joinToString(" � "), Modifier.fillMaxWidth(), textAlign = androidx.compose.ui.text.style.TextAlign.Start)
                        }
                    }
                }
                error?.let { ErrorBanner(it) }
            }
        },
        confirmButton = { PrimaryAction({ onSave(title, supplier, cents ?: 0, notes, priority, customer?.id) }, enabled = !saving && title.isNotBlank() && cents != null) { Text(if(initial != null) "Save" else "Create") } },
        dismissButton = { SecondaryAction(onDismiss) { Text("Cancel") } })
}

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
import au.mainspring.nativeapp.CUSTOMER_ORDER_STATUSES
import au.mainspring.nativeapp.CustomerOrdersViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.CustomerOrderRead
import au.mainspring.nativeapp.ui.*

@Composable fun CustomerOrdersScreen(onBack: () -> Unit, viewModel: CustomerOrdersViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    var selected by remember { mutableStateOf<CustomerOrderRead?>(null) }
    var creating by remember { mutableStateOf(false) }
    Scaffold(topBar = { BackLargeHeader("More", "Workshop", "Customer orders", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            item {
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    TabChip(state.filter == null, { viewModel.filter(null) }, { Text("All") })
                    CUSTOMER_ORDER_STATUSES.forEach { s -> TabChip(state.filter == s, { viewModel.filter(s) }, { Text(statusLabel(s)) }) }
                }
                PrimaryAction({ creating = true }, Modifier.fillMaxWidth().padding(top = 8.dp)) { Text("New order") }
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
                    val detail = listOfNotNull(order.supplier?.takeIf { it.isNotBlank() }, order.estimatedCostCents.takeIf { it > 0 }?.let { formatCents(it, currency) }).joinToString(" · ")
                    if(detail.isNotEmpty()) Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
    selected?.let { order ->
        AlertDialog(onDismissRequest = { selected = null }, title = { Text(order.title) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    MonoLabel("Set status")
                    CUSTOMER_ORDER_STATUSES.forEach { s ->
                        TabChip(order.status == s, { viewModel.setStatus(order, s) { selected = null } }, { Text(statusLabel(s)) }, enabled = !state.saving)
                    }
                    state.error?.let { ErrorBanner(it) }
                }
            },
            confirmButton = { TextButton({ selected = null }) { Text("Close") } })
    }
    if(creating) NewCustomerOrderDialog(state.saving, state.error, { creating = false }) { title, supplier, cents, notes ->
        viewModel.create(title, supplier, cents, notes) { creating = false }
    }
}

@Composable private fun NewCustomerOrderDialog(saving: Boolean, error: String?, onDismiss: () -> Unit, onSave: (String, String, Int, String) -> Unit) {
    var title by remember { mutableStateOf("") }
    var supplier by remember { mutableStateOf("") }
    var cost by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    val cents = cost.trim().ifBlank { "0" }.toBigDecimalOrNull()?.takeIf { it.signum() >= 0 }?.movePointRight(2)?.toInt()
    AlertDialog(onDismissRequest = onDismiss, title = { Text("New order") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                AtelierTextField(title, { title = it }, singleLine = true, label = { Text("Title") }, modifier = Modifier.fillMaxWidth())
                AtelierTextField(supplier, { supplier = it }, singleLine = true, label = { Text("Supplier") }, modifier = Modifier.fillMaxWidth())
                AtelierTextField(cost, { cost = it }, singleLine = true, label = { Text("Estimated cost") }, isError = cents == null, modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                AtelierTextField(notes, { notes = it }, label = { Text("Notes") }, minLines = 2, modifier = Modifier.fillMaxWidth())
                error?.let { ErrorBanner(it) }
            }
        },
        confirmButton = { PrimaryAction({ onSave(title, supplier, cents ?: 0, notes) }, enabled = !saving && title.isNotBlank() && cents != null) { Text("Create") } },
        dismissButton = { SecondaryAction(onDismiss) { Text("Cancel") } })
}

package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CustomersViewModel
import au.mainspring.nativeapp.ui.*

/** People tab: customers as Atelier cards under a large "People" header with a round + button. */
@Composable
fun CustomersScreen(
    onOpenCustomer: (String) -> Unit,
    onNewCustomer: () -> Unit,
    viewModel: CustomersViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    RefreshOnResume(viewModel::refresh)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { LargeHeader("Customers · Accounts · Team", "People", onAdd = onNewCustomer, addDescription = "New customer") }
        item {
            OutlinedTextField(
                value = state.query, onValueChange = viewModel::setQuery, singleLine = true,
                placeholder = { Text("Search customers") }, shape = MaterialTheme.shapes.small,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp),
                colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.surface, focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent, focusedBorderColor = MaterialTheme.colorScheme.primary),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { viewModel.refresh() }),
            )
        }
        if (state.loading && state.customers.isEmpty()) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        state.error?.let { item { ErrorBanner(it, Modifier.padding(horizontal = 20.dp), onRetry = { viewModel.refresh() }) } }
        if (!state.loading && state.error == null && state.customers.isEmpty()) item { EmptyState("No customers found", "Try a different name, or add a new customer with the + button.") }
        items(state.customers, key = { it.id }) { c ->
            ListCard({ onOpenCustomer(c.id) }, Modifier.padding(horizontal = 20.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(c.fullName, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, maxLines = 1)
                    Text("›", style = MaterialTheme.typography.titleLarge)
                }
                listOfNotNull(c.phone, c.email).filter { it.isNotBlank() }.takeIf { it.isNotEmpty() }?.let {
                    Text(it.joinToString(" · "), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                }
            }
        }
        if (state.canLoadMore) item {
            SecondaryAction(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp)) { Text("Load more customers") }
        }
    }
}

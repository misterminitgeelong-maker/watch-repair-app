package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CustomersViewModel

@Composable
fun CustomersScreen(
    onOpenCustomer: (String) -> Unit,
    onNewCustomer: () -> Unit,
    viewModel: CustomersViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    au.mainspring.nativeapp.ui.RefreshOnResume(viewModel::refresh)

    androidx.compose.foundation.layout.Box(Modifier.fillMaxSize()) {
    Column(Modifier.fillMaxSize()) {
        OutlinedTextField(
            value = state.query,
            onValueChange = viewModel::setQuery,
            modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 8.dp),
            singleLine = true,
            label = { Text("Search customers") },
            keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Search),
            keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSearch = { viewModel.refresh() }),
        )
        if (state.loading && state.customers.isEmpty()) {
            androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
        }
        state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp, vertical = 8.dp), onRetry = { viewModel.refresh() }) }
        if (!state.loading && state.error == null && state.customers.isEmpty()) {
            au.mainspring.nativeapp.ui.EmptyState("No customers found", "Try a different name, or add a new customer.")
        }
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxSize().weight(1f, fill = true),
        ) {
            items(state.customers, key = { it.id }) { c ->
                androidx.compose.material3.Surface(Modifier.fillMaxWidth().clickable { onOpenCustomer(c.id) },
                    color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
                    Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(c.fullName, style = MaterialTheme.typography.titleMedium)
                        c.phone?.let { p -> Text(p, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        c.email?.let { e -> Text(e, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
            }
            if(state.canLoadMore) item { androidx.compose.material3.OutlinedButton(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text("Load more customers") } }
        }
    }
    androidx.compose.material3.ExtendedFloatingActionButton(onClick = onNewCustomer, modifier = Modifier.align(Alignment.BottomEnd).padding(16.dp),
        containerColor = MaterialTheme.colorScheme.primary, contentColor = MaterialTheme.colorScheme.onPrimary) { Text("New customer", style = MaterialTheme.typography.labelLarge) }
    }
}

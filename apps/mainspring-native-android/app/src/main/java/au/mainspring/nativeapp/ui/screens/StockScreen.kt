package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import au.mainspring.nativeapp.StockViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

private fun quantityText(value: Double) = if(value % 1.0 == 0.0) value.toLong().toString() else "%.2f".format(value)

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun StockScreen(onBack: () -> Unit, model: StockViewModel = viewModel()) {
    val state by model.state.collectAsStateWithLifecycle()
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    Scaffold(topBar = { au.mainspring.nativeapp.ui.BackLargeHeader("More", "Stock & data", "Inventory", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    au.mainspring.nativeapp.ui.AtelierTextField(state.search, model::search, singleLine = true, label = { Text("Search items") }, modifier = Modifier.weight(2f),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search))
                    au.mainspring.nativeapp.ui.AtelierTextField(state.group, model::group, singleLine = true, label = { Text("Group") }, modifier = Modifier.weight(1f))
                }
                Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    au.mainspring.nativeapp.ui.AtelierChip(state.hideZero, { model.hideZero(!state.hideZero) }, label = { Text("Hide out of stock") })
                    TextButton(model::refresh, enabled = !state.loading) { Text("Refresh") }
                }
                if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            }
            state.error?.let { item { ErrorBanner(it, onRetry = model::refresh) } }
            if(!state.loading && state.error == null) item {
                Text(if(state.items.isEmpty()) "" else "${state.items.size} of ${state.total} items", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if(state.items.isEmpty()) EmptyState("No inventory matches", "Try a different search or clear the filters.")
            }
            items(state.items, key = { it.id }) { item ->
                Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
                    Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(item.code, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(item.fullDescription ?: item.description ?: "No description", style = MaterialTheme.typography.titleMedium)
                            Text(listOfNotNull("Group ${item.group}", item.groupName?.takeIf { it.isNotBlank() }).joinToString(" · ") + " · " + formatCents(item.retail.toInt(), currency),
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text(quantityText(item.quantity), style = MaterialTheme.typography.headlineSmall,
                                color = if(item.quantity <= 0) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
                            Text(item.unit?.takeIf { it.isNotBlank() } ?: "in stock", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            if(state.items.size < state.total) item { OutlinedButton(model::more, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text("Load more") } }
        }
    }
}

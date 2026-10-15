package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CatalogueViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

/** "Our cost $120.00 \u00b7 RRP" caption for a movement row; cost is shown only to owner/manager as on the web catalogue. */
internal fun catalogueMovementCaption(costCents: Int?, currency: String, canSeeCost: Boolean = TokenStore.canManageInvoices()): String =
    if(canSeeCost && costCents != null) "Our cost ${formatCents(costCents, currency)} \u00b7 RRP" else "RRP"

@Composable internal fun PriceRow(name: String, caption: String, price: String, note: String? = null) {
    val calibre = LocalCalibre.current
    if(calibre) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    Row(Modifier.fillMaxWidth().padding(vertical = if(calibre) 14.dp else 10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(name, style = MaterialTheme.typography.titleMedium)
            if(note != null) Text(note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if(caption.isNotBlank()) { if(calibre) MonoLabel(caption) else Text(caption, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        Text(price, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
    }
}

@Composable fun CatalogueScreen(onBack: () -> Unit, viewModel: CatalogueViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    val movementsTab = state.tab == "movements"
    val query = state.search.trim().lowercase()
    val movements = if(query.isEmpty()) state.movements else state.movements.filter { it.name.lowercase().contains(query) || it.key.lowercase().contains(query) }
    Scaffold(topBar = { BackLargeHeader("More", "Workshop", "Catalogue", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    TabChip(!movementsTab, { viewModel.tab("repairs") }, { Text("Repair services") })
                    TabChip(movementsTab, { viewModel.tab("movements") }, { Text("Movements") })
                }
                AtelierTextField(state.search, viewModel::search, singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    label = { Text(if(movementsTab) "Search name or calibre" else "Search repairs") })
                if(!movementsTab && state.groups.isNotEmpty()) Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    TabChip(state.group.isEmpty(), { viewModel.group("") }, { Text("All") })
                    state.groups.forEach { g -> TabChip(state.group == g.id, { viewModel.group(g.id) }, { Text(g.label ?: g.id) }) }
                }
                if(movementsTab && TokenStore.canManageInvoices()) state.defaultMargin?.let { Text("RRP = cost plus $it% (minimum floor applies). Cost is only shown to owners and managers.", Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 8.dp))
            }
            state.error?.let { item { ErrorBanner(it, onRetry = viewModel::refresh) } }
            if(!state.loading && state.error == null) {
                if(movementsTab && movements.isEmpty()) item { EmptyState("No movements found", "Try a different name or calibre.") }
                if(!movementsTab && state.items.isEmpty()) item { EmptyState("No repairs found", "Try a different search or category.") }
            }
            if(movementsTab) items(movements.take(500), key = { it.key }) { m ->
                PriceRow(m.name, catalogueMovementCaption(m.purchaseCostCents, currency), m.quoteCents?.let { formatCents(it, currency) } ?: "—")
            } else items(state.items, key = { it.key }) { item ->
                PriceRow(item.name, item.groupLabel ?: item.groupId.orEmpty(), formatCents(item.priceCents ?: 0, currency), item.notes?.takeIf { it.isNotBlank() })
            }
            if(movementsTab && movements.size > 500) item { Text("Showing 500 of ${movements.size} movements. Refine the search to see more.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

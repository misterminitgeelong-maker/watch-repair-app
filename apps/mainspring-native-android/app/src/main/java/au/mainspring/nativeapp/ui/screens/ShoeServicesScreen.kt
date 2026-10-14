package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ShoeServicesViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.CataloguePriceItem
import au.mainspring.nativeapp.ui.*

/** Mirrors formatShoePricingType on the web. */
internal fun shoePriceLabel(item: CataloguePriceItem, currency: String): String {
    val type = item.pricingType.orEmpty()
    if(type == "quoted_upon_inspection") return "Quoted upon inspection"
    val cents = item.priceCents ?: return "Price on enquiry"
    val amount = formatCents(cents, currency)
    return when(type) {
        "from" -> "From $amount"
        "pair_from" -> "From $amount / pair"
        "each_from" -> "From $amount each"
        "from_per_boot" -> "From $amount / boot"
        "from_per_strap" -> "From $amount / strap"
        "each" -> "$amount each"
        "pair" -> "$amount / pair"
        "per_cm" -> "$amount per cm"
        "per_elastic" -> "$amount per elastic"
        "single" -> "$amount (single)"
        else -> amount
    }
}

private fun durationText(item: CataloguePriceItem): String? {
    val min = item.daysMin; val max = item.daysMax
    return when {
        min != null && max != null && min != max -> "$min–$max days"
        max != null -> "$max days"
        min != null -> "$min days"
        else -> null
    }
}

@Composable fun ShoeServicesScreen(onBack: () -> Unit, viewModel: ShoeServicesViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    Scaffold(topBar = { BackLargeHeader("More", "Workshop", "Shoe services", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            item {
                AtelierTextField(state.search, viewModel::search, singleLine = true, modifier = Modifier.fillMaxWidth(), label = { Text("Search services") })
                if(state.groups.isNotEmpty()) Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    TabChip(state.group.isEmpty(), { viewModel.group("") }, { Text("All groups") })
                    state.groups.forEach { g -> TabChip(state.group == g.id, { viewModel.group(g.id) }, { Text(g.label ?: g.id) }) }
                }
                if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 8.dp))
            }
            state.error?.let { item { ErrorBanner(it, onRetry = viewModel::refresh) } }
            if(state.combos.isNotEmpty() || !state.guarantee.isNullOrBlank()) {
                item { SectionLabel("Combo pricing and guarantee") }
                items(state.combos, key = { "combo-${it.id}" }) { combo ->
                    FlatPanel {
                        Text(combo.name, style = MaterialTheme.typography.titleSmall)
                        (combo.discount ?: combo.discounts?.joinToString(", "))?.takeIf { it.isNotBlank() }?.let { MonoLabel(it) }
                        combo.rule?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
                state.guarantee?.takeIf { it.isNotBlank() }?.let { g -> item { FlatPanel { Text(g, style = MaterialTheme.typography.bodyMedium) } } }
            }
            item { SectionLabel("Service reference") }
            if(!state.loading && state.error == null && state.items.isEmpty()) item { EmptyState("No services match", "Try a different search or group.") }
            items(state.items, key = { it.key }) { item ->
                PriceRow(item.name, listOfNotNull(item.groupLabel ?: item.groupId, durationText(item)).joinToString(" · "),
                    shoePriceLabel(item, currency), item.notes?.takeIf { it.isNotBlank() })
            }
        }
    }
}

package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CatalogueViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

/** "Our cost $120.00 · RRP" caption for a movement row; cost is shown only to owner/manager as on the web catalogue. */
internal fun catalogueMovementCaption(costCents: Int?, currency: String, canSeeCost: Boolean = TokenStore.canManageInvoices()): String =
    if(canSeeCost && costCents != null) "Our cost ${formatCents(costCents, currency)} · RRP" else "RRP"

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

/** Standalone catalogue (More > Catalogue): the web "Watch Repairs" page with Catalogue selected; "Jobs" goes back. */
@Composable fun CatalogueScreen(onBack: () -> Unit, viewModel: CatalogueViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LazyColumn(Modifier.fillMaxSize().statusBarsPadding(), contentPadding = PaddingValues(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { FinTitle("Watch Repairs", onBack = onBack) }
        item {
            Column(Modifier.padding(horizontal = FinGutter), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Movement services, batteries, pressure testing, and full servicing.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(Modifier.background(FinSand, RoundedCornerShape(6.dp)).padding(4.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    TextToggle(listOf(ToggleOption("jobs", "Jobs", "tab-jobs"), ToggleOption("catalogue", "Catalogue", "tab-catalogue")), "catalogue", { if(it == "jobs") onBack() })
                }
            }
        }
        catalogueBody(state, viewModel)
    }
}

/** The catalogue content (caption, Repair Services card, Movement Database card), shared by the standalone screen and the Catalogue tab of the watch screen. */
internal fun LazyListScope.catalogueBody(state: au.mainspring.nativeapp.CatalogueState, viewModel: CatalogueViewModel) {
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    val gutter = Modifier.padding(horizontal = FinGutter)
    val query = state.movementSearch.trim().lowercase()
    val movements = if(query.isEmpty()) state.movements else state.movements.filter { it.name.lowercase().contains(query) || it.key.lowercase().contains(query) }
    item { Text("Repair services and movement database. Search by name or caliber.", gutter.padding(top = 4.dp), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    state.error?.let { e -> item { ErrorBanner(e, gutter, onRetry = viewModel::refresh) } }
    item {
        FinCard(gutter, contentPadding = 20.dp) {
            CardHeading("wrench", "Repair Services", MaterialTheme.colorScheme.primary)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                FinSearchField(state.search, viewModel::search, "Search...", Modifier.weight(0.8f).testTag("catalogue-search"))
                val groups = listOf<Pair<String?, String>>(null to "All categories") + state.groups.map { it.id to (it.label ?: it.id) }
                FinSelect(groups.firstOrNull { (it.first ?: "") == state.group }?.second ?: "All categories", groups, { viewModel.group(it ?: "") }, Modifier.weight(1.2f), tag = "catalogue-group", description = "Category")
            }
            if(state.loading && state.items.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
            CatalogueTable(listOf("Service", "Category", "Price")) {
                if(!state.loading && state.error == null && state.items.isEmpty()) Text("No repairs found. Try a different search or category.", Modifier.padding(14.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                state.items.forEach { item ->
                    TableRow(item.name, item.groupLabel ?: item.groupId.orEmpty(), formatCents(item.priceCents ?: 0, currency), item.notes?.takeIf { it.isNotBlank() })
                }
            }
        }
    }
    item {
        FinCard(gutter, contentPadding = 20.dp) {
            CardHeading("chip", "Movement Database", MaterialTheme.colorScheme.primary)
            if(TokenStore.canManageInvoices()) state.defaultMargin?.let { Text("RRP = cost plus $it% (minimum floor applies). Cost is only shown to owners and managers.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            FinSearchField(state.movementSearch, viewModel::movementSearch, "Search name or caliber...", Modifier.fillMaxWidth().testTag("movement-search"))
            state.movementsError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            var limit by remember { mutableStateOf(60) }
            CatalogueTable(listOf("Movement", "", "RRP")) {
                if(movements.isEmpty() && state.movementsError == null) Text("No movements found. Try a different name or calibre.", Modifier.padding(14.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                movements.take(limit).forEach { m ->
                    TableRow(m.name, catalogueMovementCaption(m.purchaseCostCents, currency), m.quoteCents?.let { formatCents(it, currency) } ?: "—")
                }
            }
            if(movements.size > limit) FinOutlinedLabel("Show more (${movements.size - limit} more)", { limit += 100 }, Modifier.fillMaxWidth())
        }
    }
}

@Composable private fun CardHeading(glyph: String, title: String, tint: androidx.compose.ui.graphics.Color) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        FinGlyph(glyph, tint, 24.dp)
        Text(title, style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold, fontSize = 18.sp))
    }
}

private val TableHeaderWeights = floatArrayOf(0.46f, 0.30f, 0.24f)

@Composable private fun CatalogueTable(headers: List<String>, rows: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().border(1.dp, finBorderColor(), RoundedCornerShape(4.dp))) {
        Row(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)).padding(horizontal = 14.dp, vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            headers.forEachIndexed { i, h -> Text(h, Modifier.weight(TableHeaderWeights[i]), style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.Bold), maxLines = 1, textAlign = if(i == 2) androidx.compose.ui.text.style.TextAlign.End else androidx.compose.ui.text.style.TextAlign.Start) }
        }
        rows()
    }
}

@Composable private fun TableRow(name: String, category: String, price: String, note: String? = null) {
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
        Column(Modifier.weight(TableHeaderWeights[0])) {
            Text(name, style = MaterialTheme.typography.bodyLarge)
            if(note != null) Text(note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        Text(category, Modifier.weight(TableHeaderWeights[1]), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(price, Modifier.weight(TableHeaderWeights[2]), style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.Medium), color = MaterialTheme.colorScheme.primary, textAlign = androidx.compose.ui.text.style.TextAlign.End)
    }
}

package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.QuotesViewModel
import au.mainspring.nativeapp.ui.formatCents
import au.mainspring.nativeapp.ui.statusLabel

private val QUOTE_STATUSES = listOf<Pair<String?, String>>(null to "All statuses", "draft" to "Draft", "sent" to "Sent", "approved" to "Approved", "declined" to "Declined", "expired" to "Expired")

/**
 * Quotes list in the web phone layout: title, "+ New Quote", an "All statuses" select, "More filters" (search, sort and
 * age live in its sheet) and the quotes as bordered cards (or one empty card).
 */
@Composable
fun QuotesScreen(
    onOpenQuote: (String) -> Unit,
    onBack: (() -> Unit)? = null,
    initialOlderThanDays: Int = 0,
    /** Starts a new quote. Quotes are built from a job, so without a handler the button explains that. */
    onNewQuote: (() -> Unit)? = null,
    viewModel: QuotesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var filter by rememberSaveable { mutableStateOf<String?>(null) }
    var query by rememberSaveable { mutableStateOf("") }
    var sort by rememberSaveable { mutableStateOf("newest") }
    var olderDays by rememberSaveable { mutableStateOf(initialOlderThanDays) }
    var filtersOpen by remember { mutableStateOf(false) }
    var newQuoteInfo by remember { mutableStateOf(false) }
    val shown = au.mainspring.nativeapp.visibleQuotes(state, filter, query, sort, olderDays)
    val activeFilters = (if(sort != "newest") 1 else 0) + (if(olderDays > 0) 1 else 0) + (if(query.isNotBlank()) 1 else 0)
    Column(Modifier.fillMaxSize()) {
        au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.weight(1f)) { LazyColumn(
            contentPadding = PaddingValues(start = FinGutter, end = FinGutter, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.fillMaxSize().testTag("quotes-list"),
        ) {
            item { FinTitle("Quotes", gutter = 0.dp) }
            item { FinPrimaryButton("+  New Quote", { if(onNewQuote != null) onNewQuote() else newQuoteInfo = true }, Modifier.testTag("new-quote")) }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    FinSelect(QUOTE_STATUSES.firstOrNull { it.first == filter }?.second ?: "All statuses", QUOTE_STATUSES, { filter = it }, Modifier.fillMaxWidth(), tag = "quote-status", description = "Status")
                    FinOutlinedButton({ filtersOpen = true }, Modifier.fillMaxWidth().testTag("more-filters")) {
                        FinGlyph("settings", MaterialTheme.colorScheme.onSurface, 20.dp)
                        Text(if(activeFilters > 0) "More filters ($activeFilters)" else "More filters", style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold))
                    }
                }
            }
            if(state.loading && state.quotes.isEmpty()) item { androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.error?.let { e -> item { au.mainspring.nativeapp.ui.ErrorBanner(e, onRetry = viewModel::refresh) } }
            if(!state.loading && state.error == null && shown.isEmpty()) item {
                FinEmptyCard(if(filter == null && query.isBlank() && olderDays == 0) "No quotes yet." else "No quotes match these filters.")
            }
            items(shown, key = { it.id }) { q ->
                val job = state.jobs[q.repairJobId]
                FinCard(onClick = { onOpenQuote(q.id) }) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        FinDocNumber(job?.jobNumber ?: "Quote")
                        au.mainspring.nativeapp.ui.StatusPill(q.status)
                        androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
                        Text(formatCents(q.totalCents, q.currency), style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold))
                    }
                    Text(au.mainspring.nativeapp.ui.formatShopDate(q.createdAt).substringBefore(' '), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(job?.title ?: "Repair quote", style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.Medium))
                    job?.customerName?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    Text("Subtotal ${formatCents(q.subtotalCents, q.currency)} · Tax ${formatCents(q.taxCents, q.currency)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        } }
    }
    if(filtersOpen) FiltersSheet({ filtersOpen = false }, onReset = { query = ""; sort = "newest"; olderDays = 0 }) {
        FilterSection("Search") {
            FinSearchField(query, { query = it }, "Search job, title or customer", Modifier.fillMaxWidth().testTag("quotes-search"))
        }
        FilterSection("Sort") {
            listOf("newest" to "Newest", "oldest" to "Oldest", "amount" to "Amount").forEach { (k, l) -> SheetChip(l, sort == k, { sort = k }) }
        }
        FilterSection("Sent age") {
            listOf(0 to "Any age", 7 to "Sent 7+ days", 14 to "Sent 14+ days", 21 to "Sent 21+ days").forEach { (k, l) -> SheetChip(l, olderDays == k, { olderDays = k }) }
        }
    }
    if(newQuoteInfo) AlertDialog(onDismissRequest = { newQuoteInfo = false }, title = { Text("New quote") },
        text = { Text("Quotes are created from a job. Open a job and choose Quote.") },
        confirmButton = { TextButton({ newQuoteInfo = false }) { Text("OK") } })
}

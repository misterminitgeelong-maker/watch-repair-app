package au.mainspring.nativeapp.ui.screens

import androidx.compose.runtime.setValue
import androidx.compose.runtime.getValue
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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.QuotesViewModel
import au.mainspring.nativeapp.ui.formatCents

@Composable
fun QuotesScreen(
    onOpenQuote: (String) -> Unit,
    onBack: (() -> Unit)? = null,
    initialOlderThanDays: Int = 0,
    viewModel: QuotesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var filter by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf<String?>(null) }
    var query by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("") }
    var sort by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("newest") }
    var olderDays by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf(initialOlderThanDays) }
    val shown = au.mainspring.nativeapp.visibleQuotes(state, filter, query, sort, olderDays)
    Column(Modifier.fillMaxSize()) {
        if(onBack != null) au.mainspring.nativeapp.ui.BackLargeHeader("More", "Money & performance", "Quotes", onBack)
        au.mainspring.nativeapp.ui.FilterRow(listOf(null to "All", "draft" to "Draft", "sent" to "Sent", "approved" to "Approved", "declined" to "Declined"), filter, { filter = it }, Modifier.padding(top = 4.dp))
        au.mainspring.nativeapp.ui.FilterRow(listOf<Pair<String?, String>>("newest" to "Newest", "oldest" to "Oldest", "amount" to "Amount"), sort, { sort = it ?: "newest" })
        au.mainspring.nativeapp.ui.FilterRow(listOf<Pair<String?, String>>("0" to "Any age", "7" to "Sent 7+ days", "14" to "Sent 14+ days", "21" to "Sent 21+ days"), olderDays.toString(), { olderDays = it?.toIntOrNull() ?: 0 })
        au.mainspring.nativeapp.ui.AtelierTextField(query, { query = it }, label = { Text("Search job, title or customer") }, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).testTag("quotes-search"), singleLine = true)
        if (state.loading && state.quotes.isEmpty()) androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
        state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp, vertical = 8.dp), onRetry = viewModel::refresh) }
        if (!state.loading && state.error == null && shown.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No quotes", if(filter == null && query.isBlank() && olderDays == 0) "Quotes you create from a job will show up here." else "No quotes match these filters.")
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(if(au.mainspring.nativeapp.ui.LocalCalibre.current) 0.dp else 8.dp),
            modifier = Modifier.fillMaxSize().weight(1f, fill = true),
        ) {
            items(shown, key = { it.id }) { q ->
                val job = state.jobs[q.repairJobId]
                au.mainspring.nativeapp.ui.ListCard({ onOpenQuote(q.id) }) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(job?.jobNumber ?: "Quote", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        au.mainspring.nativeapp.ui.StatusPill(q.status)
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(job?.title ?: "Repair quote", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                        Text(formatCents(q.totalCents, q.currency), style = MaterialTheme.typography.titleMedium)
                    }
                    Text(listOfNotNull(job?.customerName, au.mainspring.nativeapp.ui.formatShopDate(q.createdAt).substringBefore(' ')).joinToString(" · "),
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

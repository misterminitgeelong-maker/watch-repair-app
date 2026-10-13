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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.QuotesViewModel
import au.mainspring.nativeapp.ui.formatCents

@Composable
fun QuotesScreen(
    onOpenQuote: (String) -> Unit,
    viewModel: QuotesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var filter by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf<String?>(null) }
    val shown = state.quotes.filter { filter == null || it.status == filter }
    Column(Modifier.fillMaxSize()) {
        au.mainspring.nativeapp.ui.FilterRow(listOf(null to "All", "draft" to "Draft", "sent" to "Sent", "approved" to "Approved", "declined" to "Declined"), filter, { filter = it }, Modifier.padding(top = 4.dp))
        if (state.loading && state.quotes.isEmpty()) androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
        state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp, vertical = 8.dp), onRetry = viewModel::refresh) }
        if (!state.loading && state.error == null && shown.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No quotes", if(filter == null) "Quotes you create from a job will show up here." else "No $filter quotes right now.")
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
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

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
import au.mainspring.nativeapp.RevenueControlViewModel
import au.mainspring.nativeapp.api.RevenueItem
import au.mainspring.nativeapp.ui.*

private val kindLabels = linkedMapOf(
    "unpaid" to "Unpaid invoices", "uninvoiced" to "Completed, no invoice", "quote_followup" to "Quotes to follow up",
    "quote_draft" to "Quotes to prepare", "booking_confirmation" to "Unconfirmed bookings",
    "unscheduled" to "Needs scheduling", "unassigned" to "Needs a technician", "blocked" to "Bookings on hold",
)
private val queues = listOf("due" to "Due now", "scheduled" to "Scheduled", "all" to "All open")

@Composable fun RevenueControlScreen(onBack: () -> Unit, viewModel: RevenueControlViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val currency = au.mainspring.nativeapp.TokenStore.shopValue("currency") ?: "AUD"
    Scaffold(topBar = { BackLargeHeader("More", "Mobile services", "Revenue control", onBack) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            item {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    queues.forEach { (value, label) -> TabChip(state.queue == value, { viewModel.queue(value) }, { Text(label) }) }
                }
            }
            if(state.buckets.isNotEmpty()) {
                val open = state.buckets.sumOf { it.count }; val due = state.buckets.sumOf { it.dueCount }
                val unpaid = state.buckets.firstOrNull { it.kind == "unpaid" }?.amountCents ?: 0
                item { Spacer(Modifier.height(8.dp)); MetricStrip(listOf("OPEN" to open.toString(), "DUE NOW" to due.toString(), "UNPAID" to formatCents(unpaid, currency))) }
                item {
                    SectionLabel("Categories")
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        kindLabels.forEach { (kind, label) ->
                            val bucket = state.buckets.firstOrNull { it.kind == kind }
                            TabChip(state.kind == kind, { viewModel.kind(kind) }, { Text("$label ${bucket?.count ?: 0}") })
                        }
                    }
                }
                item { Text("Amounts are not additive across categories.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            item { SectionLabel(state.kind?.let { kindLabels[it] } ?: "Action queue") }
            if(state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.error?.let { message -> item { ErrorBanner(message, onRetry = viewModel::refresh) } }
            if(!state.loading && state.error == null && state.items.isEmpty())
                item { EmptyState(if(state.queue == "due") "Nothing needs action" else "No open items", "Check the other queues or change the category.") }
            items(state.items, key = { it.key }) { RevenueRow(it, currency) }
            if(state.items.size < state.total) item {
                OutlinedButton(viewModel::more, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text("Show more (${state.items.size} of ${state.total})") }
            }
            if(state.warnings.isNotEmpty()) item {
                SectionLabel("How to read these figures")
                state.warnings.forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }
}

@Composable private fun RevenueRow(item: RevenueItem, currency: String) {
    val money = item.currency.ifBlank { currency }
    FlatPanel {
        MonoLabel(((if(item.priority == "high") "HIGH PRIORITY · " else "") + (kindLabels[item.kind] ?: statusLabel(item.kind))).uppercase(),
            color = if(item.priority == "high") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.weight(1f)) {
                Text("${item.jobNumber} · ${item.title}", style = MaterialTheme.typography.titleSmall)
                if(item.customerName.isNotBlank()) Text(item.customerName, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(item.amountCents?.let { formatCents(it, money) } ?: "Unpriced", style = MaterialTheme.typography.titleMedium)
        }
        if(item.nextAction.isNotBlank()) Text(item.nextAction, style = MaterialTheme.typography.bodyMedium)
        item.note?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        MonoLabel(listOfNotNull("${item.ageDays} DAYS OLD", if(item.due) "DUE NOW" else item.dueAt?.let { "RETURNS ${formatShopDate(it)}".uppercase() },
            "OWNER ${(item.ownerName ?: "Unassigned").uppercase()}", item.depositCents.takeIf { it > 0 }?.let { "DEPOSIT ${formatCents(it, money)}" }).joinToString(" · "))
    }
}

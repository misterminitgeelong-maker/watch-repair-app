package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.RevenueControlViewModel
import au.mainspring.nativeapp.api.RevenueItem
import au.mainspring.nativeapp.api.RevenueOwner
import au.mainspring.nativeapp.ui.*

private val kindLabels = linkedMapOf(
    "unpaid" to "Unpaid invoices", "uninvoiced" to "Completed, no invoice", "quote_followup" to "Quotes to follow up",
    "quote_draft" to "Quotes to prepare", "booking_confirmation" to "Unconfirmed bookings",
    "unscheduled" to "Needs scheduling", "unassigned" to "Needs a technician", "blocked" to "Bookings on hold",
)
private val queues = listOf("due" to "Due now", "scheduled" to "Scheduled", "all" to "All open")

@Composable fun RevenueControlScreen(onBack: () -> Unit, onOpenJob: (String) -> Unit = {}, viewModel: RevenueControlViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val currency = au.mainspring.nativeapp.TokenStore.shopValue("currency") ?: "AUD"
    Scaffold(topBar = { BackLargeHeader("More", "Mobile services", "Revenue control", onBack) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            item {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    queues.forEach { (value, label) -> TabChip(state.queue == value, { viewModel.queue(value) }, { Text(label) }) }
                }
            }
            item {
                AtelierTextField(state.search, viewModel::search, label = { Text("Search job or customer") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
                SectionLabel("Owner")
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    (listOf<Pair<String?, String>>(null to "Everyone", "me" to "Me", "unassigned" to "Unassigned") + state.owners.map { it.id to it.name })
                        .forEach { (value, label) -> TabChip(state.owner == value, { viewModel.owner(value) }, { Text(label) }) }
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
            items(state.items, key = { it.key }) { RevenueRow(it, currency, onClick = { viewModel.edit(it) }) }
            if(state.items.size < state.total) item {
                OutlinedButton(viewModel::more, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text("Show more (${state.items.size} of ${state.total})") }
            }
            if(state.warnings.isNotEmpty()) item {
                SectionLabel("How to read these figures")
                state.warnings.forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }
    state.editing?.let { item ->
        FollowUpDialog(item, state.owners, saving = state.saving, error = state.saveError,
            onOpenJob = { viewModel.edit(null); onOpenJob(item.jobId) }, onDismiss = { viewModel.edit(null) },
            onSave = viewModel::saveFollowUp)
    }
}

private val scheduleOptions = listOf("keep" to "Keep current timing", "now" to "Now", "1" to "In 24 hours", "3" to "In 3 days", "7" to "In 7 days", "14" to "In 14 days")

@Composable private fun FollowUpDialog(item: RevenueItem, owners: List<RevenueOwner>, saving: Boolean, error: String?,
    onOpenJob: () -> Unit, onDismiss: () -> Unit, onSave: (String?, String, String, Boolean) -> Unit) {
    var owner by rememberSaveable(item.key) { mutableStateOf(item.ownerUserId.orEmpty()) }
    var schedule by rememberSaveable(item.key) { mutableStateOf("keep") }
    var note by rememberSaveable(item.key) { mutableStateOf(item.note.orEmpty()) }
    var contacted by rememberSaveable(item.key) { mutableStateOf(false) }
    AlertDialog(onDismissRequest = { if(!saving) onDismiss() },
        title = { Text("Follow up · ${item.jobNumber}") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("${item.nextAction}. Saving records an internal task. It does not send a customer message or mark an invoice paid.", style = MaterialTheme.typography.bodySmall)
                SectionLabel("Responsible team member")
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    (listOf("" to "Unassigned") + owners.map { it.id to it.name }).forEach { (id, name) -> TabChip(owner == id, { owner = id }, { Text(name) }, enabled = !saving) }
                }
                SectionLabel("Return to the due queue")
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    scheduleOptions.forEach { (value, label) ->
                        val text = if(value == "keep") (if(item.due) "$label · due now" else item.dueAt?.let { "$label · ${formatShopDate(it)}" } ?: label) else label
                        TabChip(schedule == value, { schedule = value }, { Text(text) }, enabled = !saving)
                    }
                }
                AtelierTextField(note, { note = it.take(2000) }, label = { Text("Next action / conversation notes") }, minLines = 3, enabled = !saving, modifier = Modifier.fillMaxWidth())
                Row(Modifier.fillMaxWidth().toggleable(value = contacted, enabled = !saving, role = androidx.compose.ui.semantics.Role.Checkbox, onValueChange = { contacted = it }).heightIn(min = 48.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Checkbox(contacted, null, enabled = !saving); Text("I contacted the customer")
                }
                error?.let { ErrorBanner(it) }
                TextButton(onOpenJob, enabled = !saving, modifier = Modifier.heightIn(min = 48.dp)) { Text("Open job") }
            }
        },
        confirmButton = { PrimaryAction({ onSave(owner.ifBlank { null }, schedule, note, contacted) }, enabled = !saving, modifier = Modifier.heightIn(min = 48.dp)) { Text(if(saving) "Saving…" else "Save follow-up") } },
        dismissButton = { TextButton(onDismiss, enabled = !saving, modifier = Modifier.heightIn(min = 48.dp)) { Text("Cancel") } })
}

@Composable private fun RevenueRow(item: RevenueItem, currency: String, onClick: () -> Unit) {
    val money = item.currency.ifBlank { currency }
    ListCard(onClick) {
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

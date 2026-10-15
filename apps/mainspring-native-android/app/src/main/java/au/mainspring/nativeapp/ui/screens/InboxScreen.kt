package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.InboxViewModel
import au.mainspring.nativeapp.api.TenantEventLogRead
import au.mainspring.nativeapp.inboxRoute
import au.mainspring.nativeapp.ui.formatCents

private data class PendingCardAction(val issueId: String, val action: InboxViewModel.CardAction, val title: String, val text: String, val confirm: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InboxScreen(
    onBack: () -> Unit,
    viewModel: InboxViewModel = viewModel(),
    embedded: Boolean = false,
    onOpenEntity: (route: String) -> Unit = {},
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var pendingDelete by remember { mutableStateOf<TenantEventLogRead?>(null) }
    var pendingCard by remember { mutableStateOf<PendingCardAction?>(null) }

    pendingDelete?.let { ev ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("Delete this alert?") },
            text = { Text(ev.eventSummary) },
            confirmButton = { TextButton(onClick = { viewModel.delete(ev.id); pendingDelete = null }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { pendingDelete = null }) { Text("Keep") } },
        )
    }
    pendingCard?.let { p ->
        AlertDialog(
            onDismissRequest = { pendingCard = null },
            title = { Text(p.title) },
            text = { Text(p.text) },
            confirmButton = { TextButton(onClick = { viewModel.resolveIssue(p.issueId, p.action); pendingCard = null }) { Text(p.confirm) } },
            dismissButton = { TextButton(onClick = { pendingCard = null }) { Text("Cancel") } },
        )
    }

    Scaffold(
        contentWindowInsets = androidx.compose.foundation.layout.WindowInsets(0, 0, 0, 0),
        containerColor = if (embedded) androidx.compose.ui.graphics.Color.Transparent else MaterialTheme.colorScheme.background,
        topBar = {
            if (!embedded) au.mainspring.nativeapp.ui.LargeHeader("Messages · Activity", "Inbox")
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = { viewModel.refresh() }, enabled = !state.loading, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") }
            }
            if (state.loading && state.events.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(16.dp), onRetry = { viewModel.refresh() }) }
            state.actionError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp)) }
            if (!state.loading && state.error == null && state.events.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("You're all caught up", "Customer replies and booking activity will show up here.")
            au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.weight(1f)) { LazyColumn(
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 112.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxSize(),
            ) {
                items(state.events, key = { it.id }) { ev ->
                    val route = inboxRoute(ev)
                    val isCard = ev.eventType == "card_payment_needs_attention"
                    val issue = if (isCard) ev.entityId?.let { state.issues[it] } else null
                    val busy = issue != null && state.busyIssueId == issue.id
                    au.mainspring.nativeapp.ui.FlatPanel(
                        Modifier.padding(horizontal = 4.dp).let { m -> if (route != null) m.clickable(role = androidx.compose.ui.semantics.Role.Button) { onOpenEntity(route) } else m },
                    ) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(au.mainspring.nativeapp.ui.statusLabel(ev.eventType), style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                            Text(au.mainspring.nativeapp.ui.formatShopDate(ev.createdAt).substringBefore(' '), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text(ev.eventSummary, style = MaterialTheme.typography.bodyMedium)
                        if (issue != null) {
                            val amount = formatCents(issue.amountCents, issue.currency)
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
                                if (issue.canRefund) TextButton(enabled = !busy, modifier = Modifier.heightIn(min = 48.dp), onClick = {
                                    pendingCard = PendingCardAction(issue.id, InboxViewModel.CardAction.Refund, "Refund $amount?",
                                        "This returns $amount to the customer's card through Stripe and cannot be undone.", "Refund $amount")
                                }) { Text("Refund") }
                                if (issue.canApply) TextButton(enabled = !busy, modifier = Modifier.heightIn(min = 48.dp), onClick = {
                                    pendingCard = PendingCardAction(issue.id, InboxViewModel.CardAction.Apply, "Apply payment?",
                                        "Record $amount as a payment on invoice ${issue.invoiceNumber.orEmpty()}.".trim(), "Apply payment")
                                }) { Text("Apply") }
                                TextButton(enabled = !busy, modifier = Modifier.heightIn(min = 48.dp), onClick = {
                                    pendingCard = PendingCardAction(issue.id, InboxViewModel.CardAction.Dismiss, "Dismiss this payment?",
                                        "Only dismiss if it has already been sorted out in Stripe. No money moves.", "Dismiss")
                                }) { Text("Dismiss") }
                                if (busy) LinearProgressIndicator(Modifier.weight(1f))
                            }
                        }
                        if (!isCard) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                                TextButton(enabled = state.deletingId == null, modifier = Modifier.heightIn(min = 48.dp), onClick = { pendingDelete = ev }) { Text("Delete") }
                            }
                        }
                    }
                }
                if (state.canLoadMore) {
                    item(key = "load-more") {
                        TextButton(onClick = { viewModel.loadMore() }, enabled = !state.loadingMore, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                            Text(if (state.loadingMore) "Loading…" else "Load older alerts")
                        }
                    }
                }
            } }
        }
    }
}

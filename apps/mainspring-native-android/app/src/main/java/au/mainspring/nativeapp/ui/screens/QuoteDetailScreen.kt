package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.QuoteDetailViewModel
import au.mainspring.nativeapp.ui.formatCents

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuoteDetailScreen(
    quoteId: String,
    onBack: () -> Unit,
) {
    val vm: QuoteDetailViewModel = viewModel(key = quoteId, factory = QuoteDetailViewModel.factory(quoteId))
    val state by vm.state.collectAsStateWithLifecycle()
    val q = state.quote
    var confirmSend by remember { mutableStateOf(false) }
    val canSend = q?.status == "draft"

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(q?.status?.uppercase() ?: "Quote") },
                navigationIcon = {
                    TextButton(onClick = onBack) { Text("Back") }
                },
            )
        },
    ) { padding ->
        when {
            state.loading && q == null && state.lines.isEmpty() -> CircularProgressIndicator(Modifier.padding(padding).padding(24.dp))
            state.error != null && q == null -> Text(state.error ?: "", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(padding).padding(16.dp))
            else -> {
                LazyColumn(Modifier.padding(padding).padding(16.dp)) {
                    item {
                        if (q != null) {
                            Text(
                                formatCents(q.totalCents, q.currency),
                                style = MaterialTheme.typography.headlineSmall,
                            )
                            Text("Repair job ${q.repairJobId}", style = MaterialTheme.typography.bodyMedium)
                            Text("Created ${q.createdAt}", style = MaterialTheme.typography.bodySmall)
                            q.sentAt?.let { Text("Sent $it", style = MaterialTheme.typography.bodySmall) }
                            if (canSend) {
                                OutlinedButton(
                                    onClick = { confirmSend = true },
                                    enabled = !state.sendBusy,
                                    modifier = Modifier.padding(top = 12.dp),
                                ) {
                                    Text(if (state.sendBusy) "Sending…" else "Send to customer")
                                }
                            }
                            state.error?.let {
                                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
                            }
                        }
                    }
                    item { HorizontalDivider(Modifier.padding(vertical = 12.dp)) }
                    itemsIndexed(state.lines, key = { i, line -> line.id ?: "line_$i" }) { _, line ->
                        Column(Modifier.padding(vertical = 8.dp)) {
                            Text(line.description ?: "(line)", style = MaterialTheme.typography.bodyLarge)
                            Text(
                                "${line.quantity} × ${formatCents(line.unitPriceCents, q?.currency ?: "AUD")}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        HorizontalDivider()
                    }
                }
            }
        }
    }

    if (confirmSend) {
        AlertDialog(
            onDismissRequest = { confirmSend = false },
            title = { Text("Send quote") },
            text = {
                Text(
                    "This marks the quote as sent, updates the repair job where applicable, and notifies the customer by SMS and email when contact details exist.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        vm.sendQuote()
                        confirmSend = false
                    },
                    enabled = !state.sendBusy,
                ) {
                    Text("Send")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmSend = false }) { Text("Cancel") }
            },
        )
    }
}

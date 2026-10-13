package au.mainspring.nativeapp.ui.screens

import androidx.compose.material3.*
import androidx.compose.foundation.layout.*
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
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
import au.mainspring.nativeapp.ui.formatShopDate

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuoteDetailScreen(
    quoteId: String,
    onBack: () -> Unit,
    onOpenInvoice: (String) -> Unit,
) {
    val vm: QuoteDetailViewModel = viewModel(key = quoteId, factory = QuoteDetailViewModel.factory(quoteId))
    val state by vm.state.collectAsStateWithLifecycle()
    val q = state.quote
    var confirmSend by remember { mutableStateOf(false) }
    var confirmInvoice by remember { mutableStateOf(false) }
    val canSend = q?.status == "draft"

    Scaffold(
        topBar = {
            au.mainspring.nativeapp.ui.AtelierTopAppBar(
                title = { Text("Quote", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
                actions = { TextButton(onClick = vm::load, enabled = !state.loading, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") } },
            )
        },
        bottomBar = {
            val showSend = q != null && canSend
            val showInvoice = q != null && q.status == "approved" && state.invoiceId == null && au.mainspring.nativeapp.TokenStore.canManageInvoices()
            val openInvoice = state.invoiceId
            if (showSend || showInvoice || openInvoice != null) Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 2.dp) {
                Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp)) {
                    if (showSend) au.mainspring.nativeapp.ui.PrimaryAction(onClick = { confirmSend = true }, enabled = !state.sendBusy, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text(if (state.sendBusy) "Sending…" else "Send to customer", style = MaterialTheme.typography.titleMedium) }
                    if (showInvoice) au.mainspring.nativeapp.ui.PrimaryAction(onClick = { confirmInvoice = true }, enabled = !state.invoiceBusy, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text(if (state.invoiceBusy) "Creating…" else "Create invoice", style = MaterialTheme.typography.titleMedium) }
                    if (openInvoice != null) au.mainspring.nativeapp.ui.PrimaryAction(onClick = { onOpenInvoice(openInvoice) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("Open invoice", style = MaterialTheme.typography.titleMedium) }
                }
            }
        },
    ) { padding ->
        when {
            state.loading && q == null && state.lines.isEmpty() -> LinearProgressIndicator(Modifier.padding(padding).fillMaxWidth())
            state.error != null && q == null -> au.mainspring.nativeapp.ui.ErrorBanner(state.error ?: "", Modifier.padding(padding).padding(16.dp), onRetry = vm::load)
            else -> {
                LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    if (q != null) item {
                        au.mainspring.nativeapp.ui.FlatPanel {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                au.mainspring.nativeapp.ui.StatusPill(q.status)
                                Text(formatShopDate(q.createdAt).substringBefore(' '), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Text(formatCents(q.totalCents, q.currency), style = MaterialTheme.typography.headlineMedium)
                            Text("Subtotal ${formatCents(q.subtotalCents, q.currency)} \u00b7 GST ${formatCents(q.taxCents, q.currency)}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            q.sentAt?.let { Text("Sent ${formatShopDate(it)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                    }
                    state.error?.let { item { au.mainspring.nativeapp.ui.ErrorBanner(it) } }
                    if (state.lines.isNotEmpty()) item {
                        au.mainspring.nativeapp.ui.SectionLabel("Line items")
                        au.mainspring.nativeapp.ui.FlatPanel {
                            state.lines.forEachIndexed { i, line ->
                                if (i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Column(Modifier.weight(1f)) {
                                        Text(line.description ?: "(line)", style = MaterialTheme.typography.bodyLarge)
                                        Text("${java.math.BigDecimal.valueOf(line.quantity).stripTrailingZeros().toPlainString()} \u00d7 ${formatCents(line.unitPriceCents, q?.currency ?: "AUD")}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    Text(formatCents((line.unitPriceCents * line.quantity).toInt(), q?.currency ?: "AUD"), style = MaterialTheme.typography.bodyLarge)
                                }
                            }
                        }
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
    if (confirmInvoice) AlertDialog(onDismissRequest = { confirmInvoice = false }, title = { Text("Create invoice?") },
        text = { Text("Create an invoice from this approved quote using the shop's saved totals.") },
        confirmButton = { TextButton(onClick = { confirmInvoice = false; vm.createInvoice() }) { Text("Create") } },
        dismissButton = { TextButton(onClick = { confirmInvoice = false }) { Text("Cancel") } })
}

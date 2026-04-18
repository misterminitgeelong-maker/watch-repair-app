package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import au.mainspring.nativeapp.InvoiceDetailViewModel
import au.mainspring.nativeapp.ui.formatCents

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InvoiceDetailScreen(
    invoiceId: String,
    onBack: () -> Unit,
) {
    val vm: InvoiceDetailViewModel = viewModel(key = invoiceId, factory = InvoiceDetailViewModel.factory(invoiceId))
    val state by vm.state.collectAsStateWithLifecycle()
    val inv = state.data?.invoice
    var paymentOpen by remember { mutableStateOf(false) }
    var amountDraft by remember { mutableStateOf("") }
    var refDraft by remember { mutableStateOf("") }

    val paidCents = state.data?.payments?.sumOf { it.amountCents } ?: 0
    val remainingCents = (inv?.totalCents ?: 0) - paidCents
    val canRecordPayment = inv != null && remainingCents > 0 && inv.status != "paid"

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(inv?.invoiceNumber ?: "Invoice") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
            )
        },
    ) { padding ->
        when {
            state.loading && state.data == null -> CircularProgressIndicator(Modifier.padding(padding).padding(24.dp))
            state.error != null && state.data == null -> Text(state.error ?: "", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(padding).padding(16.dp))
            state.data != null -> {
                val d = state.data!!
                LazyColumn(Modifier.padding(padding).padding(16.dp)) {
                    item {
                        Text(d.invoice.status.uppercase(), style = MaterialTheme.typography.titleMedium)
                        Text(formatCents(d.invoice.totalCents, d.invoice.currency), style = MaterialTheme.typography.headlineSmall)
                        Text("Subtotal ${formatCents(d.invoice.subtotalCents, d.invoice.currency)} · Tax ${formatCents(d.invoice.taxCents, d.invoice.currency)}")
                        Text(
                            "Paid ${formatCents(paidCents, d.invoice.currency)} · Remaining ${formatCents(remainingCents.coerceAtLeast(0), d.invoice.currency)}",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Text("Created ${d.invoice.createdAt}", style = MaterialTheme.typography.bodySmall)
                        state.paymentInfo?.let {
                            Text(it, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
                        }
                        state.error?.let {
                            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
                        }
                        if (canRecordPayment) {
                            OutlinedButton(
                                onClick = {
                                    amountDraft = ""
                                    refDraft = ""
                                    paymentOpen = true
                                },
                                enabled = !state.paymentBusy,
                                modifier = Modifier.padding(top = 12.dp),
                            ) {
                                Text(if (state.paymentBusy) "Saving…" else "Record payment")
                            }
                        }
                    }
                    if (state.lineItems.isNotEmpty()) {
                        item {
                            HorizontalDivider(Modifier.padding(vertical = 12.dp))
                            Text("Line items", style = MaterialTheme.typography.titleSmall)
                        }
                        itemsIndexed(state.lineItems, key = { i, line -> line.id ?: "inv_line_$i" }) { _, line ->
                            Column(Modifier.padding(vertical = 8.dp)) {
                                Text(line.description ?: "(line)", style = MaterialTheme.typography.bodyLarge)
                                Text(
                                    "${line.quantity} × ${formatCents(line.unitPriceCents, d.invoice.currency)}",
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                            HorizontalDivider()
                        }
                    }
                    item {
                        HorizontalDivider(Modifier.padding(vertical = 12.dp))
                        Text("Payments", style = MaterialTheme.typography.titleSmall)
                    }
                    items(d.payments, key = { it.id }) { p ->
                        Column(Modifier.padding(vertical = 6.dp)) {
                            Text("${p.status} · ${formatCents(p.amountCents, p.currency)} via ${p.provider}")
                            p.providerReference?.takeIf { it.isNotBlank() }?.let {
                                Text("Ref $it", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        HorizontalDivider()
                    }
                }
            }
        }
    }

    if (paymentOpen && inv != null) {
        val cents = InvoiceDetailViewModel.parseDollarsToCents(amountDraft)
        AlertDialog(
            onDismissRequest = { paymentOpen = false },
            title = { Text("Record payment") },
            text = {
                Column {
                    Text(
                        "Remaining ${formatCents(remainingCents.coerceAtLeast(0), inv.currency)}",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(bottom = 8.dp),
                    )
                    OutlinedTextField(
                        value = amountDraft,
                        onValueChange = { amountDraft = it },
                        label = { Text("Amount") },
                        singleLine = true,
                        placeholder = { Text("e.g. 50.00") },
                    )
                    OutlinedTextField(
                        value = refDraft,
                        onValueChange = { refDraft = it },
                        label = { Text("Reference (optional)") },
                        singleLine = true,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (cents != null) {
                            vm.recordPayment(cents, refDraft)
                            paymentOpen = false
                        }
                    },
                    enabled = !state.paymentBusy && cents != null && cents <= remainingCents,
                ) {
                    Text("Save")
                }
            },
            dismissButton = {
                TextButton(onClick = { paymentOpen = false }) { Text("Cancel") }
            },
        )
    }
}

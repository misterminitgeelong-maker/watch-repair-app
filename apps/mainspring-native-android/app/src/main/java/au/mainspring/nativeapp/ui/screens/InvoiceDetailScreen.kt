package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
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
import au.mainspring.nativeapp.ui.formatShopDate

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InvoiceDetailScreen(
    invoiceId: String,
    onBack: () -> Unit,
    vm: InvoiceDetailViewModel = viewModel(key = invoiceId, factory = InvoiceDetailViewModel.factory(invoiceId)),
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val inv = state.data?.invoice
    val context = androidx.compose.ui.platform.LocalContext.current
    var printError by remember { mutableStateOf<String?>(null) }
    var paymentOpen by remember { mutableStateOf(false) }
    var sendOpen by remember { mutableStateOf(false) }
    var amountDraft by remember { mutableStateOf("") }
    var refDraft by remember { mutableStateOf("") }

    val paidCents = state.data?.payments?.sumOf { it.amountCents } ?: 0
    val remainingCents = (inv?.totalCents ?: 0) - paidCents
    val canRecordPayment = inv != null && remainingCents > 0 && inv.status == "unpaid" && !state.paymentUnknown && au.mainspring.nativeapp.TokenStore.canManageInvoices()

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
                        OutlinedButton(onClick = vm::load, enabled = !state.loading && !state.paymentBusy) { Text("Refresh invoice and payments") }
                        if(state.paymentUnknown) OutlinedButton(onClick = vm::acknowledgePaymentHistory, enabled = !state.loading && state.historyChecked) { Text("I checked the payment history") }
                        if(au.mainspring.nativeapp.TokenStore.canManageInvoices()) OutlinedButton(onClick = { sendOpen = true }, enabled = !state.sendBusy) { Text(if(state.sendBusy) "Sending…" else "Email invoice to customer") }
                        state.sendInfo?.let { Text(it) }
                        OutlinedButton(onClick = {
                            try {
                                val invoice = d.invoice
                                au.mainspring.nativeapp.printInvoiceSummary(context,au.mainspring.nativeapp.InvoiceSummary(invoice.invoiceNumber,invoice.status,
                                    details = listOf("Created ${formatShopDate(invoice.createdAt)}"),
                                    items = state.lineItems.map { "${it.description.orEmpty()}\n${java.math.BigDecimal.valueOf(it.quantity).stripTrailingZeros().toPlainString()} × ${formatCents(it.unitPriceCents,invoice.currency)}" },
                                    totals = listOf("Subtotal" to formatCents(invoice.subtotalCents,invoice.currency),"Tax / GST" to formatCents(invoice.taxCents,invoice.currency),
                                        "Total" to formatCents(invoice.totalCents,invoice.currency),"Paid" to formatCents(paidCents,invoice.currency),"Remaining" to formatCents(remainingCents.coerceAtLeast(0),invoice.currency))))
                            } catch(e: Exception) { printError = e.message ?: "Could not open printing." }
                        },enabled = !state.loading && !state.paymentBusy) { Text("Print / save invoice summary") }
                        printError?.let { Text(it,color = MaterialTheme.colorScheme.error) }
                        Text(d.invoice.status.uppercase(), style = MaterialTheme.typography.titleMedium)
                        Text(formatCents(d.invoice.totalCents, d.invoice.currency), style = MaterialTheme.typography.headlineSmall)
                        Text("Subtotal ${formatCents(d.invoice.subtotalCents, d.invoice.currency)} · Tax ${formatCents(d.invoice.taxCents, d.invoice.currency)}")
                        Text(
                            "Paid ${formatCents(paidCents, d.invoice.currency)} · Remaining ${formatCents(remainingCents.coerceAtLeast(0), d.invoice.currency)}",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Text("Created ${formatShopDate(d.invoice.createdAt)}", style = MaterialTheme.typography.bodySmall)
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

    if(sendOpen) AlertDialog(onDismissRequest = { sendOpen = false }, title = { Text("Email invoice?", style = MaterialTheme.typography.headlineSmall) }, text = { Text("Send this invoice to the customer's saved email address.") },
        confirmButton = { Button(onClick = { sendOpen = false; vm.sendInvoice() }) { Text("Send invoice") } }, dismissButton = { TextButton(onClick = { sendOpen = false }) { Text("Cancel") } })

    if (paymentOpen && inv != null) {
        val cents = InvoiceDetailViewModel.parseDollarsToCents(amountDraft)
        AlertDialog(
            onDismissRequest = { paymentOpen = false },
            title = { Text("Record payment", style = MaterialTheme.typography.headlineSmall) },
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

package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.material3.*
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
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.launch
import au.mainspring.nativeapp.userMessage
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
    val calibre = au.mainspring.nativeapp.ui.LocalCalibre.current
    val context = androidx.compose.ui.platform.LocalContext.current
    var printError by remember { mutableStateOf<String?>(null) }
    var paymentOpen by remember { mutableStateOf(false) }
    var sendOpen by remember { mutableStateOf(false) }
    var amountDraft by remember { mutableStateOf("") }
    var refDraft by remember { mutableStateOf("") }
    var xero by remember(invoiceId) { mutableStateOf<au.mainspring.nativeapp.api.InvoiceXeroInfo?>(null) }
    var xeroRetryBusy by remember(invoiceId) { mutableStateOf(false) }
    var xeroRetryError by remember(invoiceId) { mutableStateOf<String?>(null) }
    val xeroScope = androidx.compose.runtime.rememberCoroutineScope()
    androidx.compose.runtime.LaunchedEffect(invoiceId, state.data?.invoice?.status) {
        xero = runCatching { au.mainspring.nativeapp.api.ApiClient.service(au.mainspring.nativeapp.api.InvoiceExtrasApi::class.java).invoiceXero(invoiceId).invoice }.getOrNull()
    }

    val paidCents = state.data?.payments?.sumOf { it.amountCents } ?: 0
    val remainingCents = (inv?.totalCents ?: 0) - paidCents
    val canRecordPayment = inv != null && remainingCents > 0 && inv.status == "unpaid" && !state.paymentUnknown && au.mainspring.nativeapp.TokenStore.canManageInvoices()

    Scaffold(
        topBar = {
            if(calibre) FinTitle(inv?.invoiceNumber ?: "Invoice", onBack = onBack, insets = true, actions = { TextButton(onClick = vm::load, enabled = !state.loading && !state.paymentBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") } })
            else au.mainspring.nativeapp.ui.AtelierTopAppBar(
                title = { Text(inv?.invoiceNumber ?: "Invoice") },
                navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
                actions = { TextButton(onClick = vm::load, enabled = !state.loading && !state.paymentBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") } },
            )
        },
    ) { padding ->
        when {
            state.loading && state.data == null -> androidx.compose.material3.LinearProgressIndicator(Modifier.padding(padding).fillMaxWidth())
            state.error != null && state.data == null -> au.mainspring.nativeapp.ui.ErrorBanner(state.error ?: "", Modifier.padding(padding).padding(16.dp), onRetry = vm::load)
            state.data != null -> {
                val d = state.data!!
                val currency = d.invoice.currency
                LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item {
                        if(calibre) FinCard(contentPadding = 20.dp) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                                Text(if (remainingCents > 0) "OUTSTANDING" else "PAID IN FULL", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium.copy(letterSpacing = 0.8.sp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                                FinStatusPill(d.invoice.status)
                            }
                            Text(formatCents(remainingCents.coerceAtLeast(0), currency), style = MaterialTheme.typography.headlineLarge.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Medium, fontSize = 34.sp))
                            Text("Total ${formatCents(d.invoice.totalCents, currency)} · Paid ${formatCents(paidCents, currency)} · ${formatShopDate(d.invoice.createdAt).substringBefore(' ')}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text("Subtotal ${formatCents(d.invoice.subtotalCents, currency)} · Tax ${formatCents(d.invoice.taxCents, currency)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        } else au.mainspring.nativeapp.ui.HeroCard {
                            Text((if (remainingCents > 0) "OUTSTANDING" else "PAID IN FULL"), style = MaterialTheme.typography.labelSmall)
                            Text(formatCents(remainingCents.coerceAtLeast(0), currency), style = MaterialTheme.typography.displaySmall.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.Light))
                            Text("Total ${formatCents(d.invoice.totalCents, currency)} · Paid ${formatCents(paidCents, currency)} · ${formatShopDate(d.invoice.createdAt).substringBefore(' ')}", style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                    state.paymentInfo?.let { item { if(calibre) CalibreNotice(it) else Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onPrimaryContainer, style = MaterialTheme.typography.bodyMedium) } } }
                    state.error?.let { item { au.mainspring.nativeapp.ui.ErrorBanner(it) } }
                    state.sendInfo?.let { item { if(calibre) CalibreNotice(it) else Text(it, style = MaterialTheme.typography.bodyMedium) } }
                    printError?.let { item { au.mainspring.nativeapp.ui.ErrorBanner(it) } }
                    xero?.takeIf { !it.onlineUrl.isNullOrBlank() || !it.syncStatus.isNullOrBlank() }?.let { x ->
                        item {
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                x.syncStatus?.takeIf { it.isNotBlank() }?.let {
                                    Text("Xero: ${it.replace('_', ' ')}" + (x.syncError?.takeIf { e -> e.isNotBlank() && it == "failed" }?.let { e -> " - $e" } ?: ""), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                if(x.syncStatus == "failed" && au.mainspring.nativeapp.TokenStore.canManageInvoices()) {
                                    OutlinedButton(onClick = {
                                        xeroRetryBusy = true; xeroRetryError = null
                                        xeroScope.launch {
                                            try { xero = au.mainspring.nativeapp.api.ApiClient.service(au.mainspring.nativeapp.api.InvoiceExtrasApi::class.java).retryXero(invoiceId) }
                                            catch(e: kotlinx.coroutines.CancellationException) { throw e }
                                            catch(e: Exception) { xeroRetryError = e.userMessage() }
                                            finally { xeroRetryBusy = false }
                                        }
                                    }, enabled = !xeroRetryBusy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("xero-retry")) { Text(if(xeroRetryBusy) "Retrying Xero\u2026" else "Retry Xero sync") }
                                    xeroRetryError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
                                }
                                x.onlineUrl?.takeIf { it.isNotBlank() }?.let { url ->
                                    OutlinedButton(onClick = { runCatching { context.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url))) } }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Pay online") }
                                }
                            }
                        }
                    }
                    if(state.paymentUnknown) item { OutlinedButton(onClick = vm::acknowledgePaymentHistory, enabled = !state.loading && state.historyChecked, modifier = Modifier.fillMaxWidth()) { Text("I checked the payment history") } }
                    item {
                        val printAction: () -> Unit = {
                                    try {
                                        val invoice = d.invoice
                                        au.mainspring.nativeapp.printInvoiceSummary(context,au.mainspring.nativeapp.InvoiceSummary(invoice.invoiceNumber,invoice.status,
                                            details = listOf("Created ${formatShopDate(invoice.createdAt)}"),
                                            items = state.lineItems.map { "${it.description.orEmpty()}\n${java.math.BigDecimal.valueOf(it.quantity).stripTrailingZeros().toPlainString()} × ${formatCents(it.unitPriceCents,invoice.currency)}" },
                                            totals = listOf("Subtotal" to formatCents(invoice.subtotalCents,invoice.currency),"Tax / GST" to formatCents(invoice.taxCents,invoice.currency),
                                                "Total" to formatCents(invoice.totalCents,invoice.currency),"Paid" to formatCents(paidCents,invoice.currency),"Remaining" to formatCents(remainingCents.coerceAtLeast(0),invoice.currency))))
                                    } catch(e: Exception) { printError = e.message ?: "Could not open printing." }
                        }
                        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (canRecordPayment) Button(
                                onClick = { amountDraft = ""; refDraft = ""; paymentOpen = true },
                                enabled = !state.paymentBusy,
                                modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                            ) { Text(if (state.paymentBusy) "Saving…" else "Record payment", style = MaterialTheme.typography.titleMedium) }
                            if(calibre) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                if(au.mainspring.nativeapp.TokenStore.canManageInvoices()) FinOutlinedLabel(if(state.sendBusy) "Sending…" else "Email invoice", { sendOpen = true }, Modifier.weight(1f), enabled = !state.sendBusy)
                                FinOutlinedLabel("Print / PDF", printAction, Modifier.weight(1f), enabled = !state.loading && !state.paymentBusy)
                            } else Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                if(au.mainspring.nativeapp.TokenStore.canManageInvoices()) OutlinedButton(onClick = { sendOpen = true }, enabled = !state.sendBusy, modifier = Modifier.weight(1f).heightIn(min = 48.dp)) { Text(if(state.sendBusy) "Sending…" else "Email invoice") }
                                OutlinedButton(onClick = printAction, enabled = !state.loading && !state.paymentBusy, modifier = Modifier.weight(1f).heightIn(min = 48.dp)) { Text("Print / PDF") }
                            }
                        }
                    }
                    if (state.lineItems.isNotEmpty()) {
                        item {
                            au.mainspring.nativeapp.ui.SectionLabel("Line items")
                            au.mainspring.nativeapp.ui.FlatPanel {
                                state.lineItems.forEachIndexed { i, line ->
                                    if(i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                        Column(Modifier.weight(1f)) {
                                            Text(line.description ?: "(line)", style = MaterialTheme.typography.bodyLarge)
                                            Text("${java.math.BigDecimal.valueOf(line.quantity).stripTrailingZeros().toPlainString()} × ${formatCents(line.unitPriceCents, currency)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                        Text(formatCents((line.unitPriceCents * line.quantity).toInt(), currency), style = MaterialTheme.typography.bodyLarge)
                                    }
                                }
                            }
                        }
                    }
                    item {
                        au.mainspring.nativeapp.ui.SectionLabel("Payments")
                        if(d.payments.isEmpty()) Text("No payments recorded yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    items(d.payments, key = { it.id }) { p ->
                        au.mainspring.nativeapp.ui.FlatPanel {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(p.provider.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.bodyLarge)
                                Text(formatCents(p.amountCents, p.currency), style = MaterialTheme.typography.bodyLarge)
                            }
                            Text(listOfNotNull(p.status.replaceFirstChar { it.uppercase() }, p.providerReference?.takeIf { it.isNotBlank() }?.let { "Ref $it" }).joinToString(" · "),
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }

    if(sendOpen) AlertDialog(onDismissRequest = { sendOpen = false }, title = { Text("Email invoice?") }, text = { Text("Send this invoice to the customer's saved email address.") },
        confirmButton = { Button(onClick = { sendOpen = false; vm.sendInvoice() }) { Text("Send invoice") } }, dismissButton = { TextButton(onClick = { sendOpen = false }) { Text("Cancel") } })

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
                    au.mainspring.nativeapp.ui.AtelierTextField(
                        value = amountDraft,
                        onValueChange = { amountDraft = it },
                        label = { Text("Amount") },
                        singleLine = true,
                        placeholder = { Text("e.g. 50.00") },
                    )
                    au.mainspring.nativeapp.ui.AtelierTextField(
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

/** Calibre notice: grey block with a forest rule on the left. */
@Composable internal fun CalibreNotice(text: String, modifier: Modifier = Modifier) {
    androidx.compose.foundation.layout.Row(modifier.fillMaxWidth().height(androidx.compose.foundation.layout.IntrinsicSize.Min).background(MaterialTheme.colorScheme.surfaceVariant)) {
        androidx.compose.foundation.layout.Box(Modifier.width(3.dp).fillMaxHeight().background(MaterialTheme.colorScheme.primary))
        Text(text, Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
    }
}

/** Calibre secondary action: plain text link with a trailing arrow. */
@Composable internal fun CalibreLink(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    androidx.compose.foundation.layout.Row(
        modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(enabled = enabled, role = androidx.compose.ui.semantics.Role.Button, onClick = onClick),
        horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyLarge, color = if(enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
        Text("→", style = MaterialTheme.typography.bodyLarge, color = if(enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.foundation.layout.Box
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.InvoicesViewModel
import kotlinx.coroutines.launch
import au.mainspring.nativeapp.ui.formatCents

/** Invoices list in the web phone layout: search, two segmented rows, then one bordered card per invoice. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun InvoicesScreen(
    onOpenInvoice: (String) -> Unit,
    onBack: (() -> Unit)? = null,
    /** Called with the mobile job id; expected route: "mobileFinance/{jobId}?business=false". */
    onOpenMobileInvoice: (jobId: String) -> Unit = {},
    viewModel: InvoicesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var filter by rememberSaveable { mutableStateOf<String?>(null) }
    var type by rememberSaveable { mutableStateOf<String?>(null) }
    var query by rememberSaveable { mutableStateOf("") }
    val shown = au.mainspring.nativeapp.mergedInvoices(state, type, filter, query)
    val clipboard = LocalClipboardManager.current
    val context = androidx.compose.ui.platform.LocalContext.current
    val printScope = androidx.compose.runtime.rememberCoroutineScope()
    var printError by remember { mutableStateOf<String?>(null) }
    var amountDraft by remember { mutableStateOf("") }
    var refDraft by remember { mutableStateOf("") }
    val payTarget = state.payTarget
    androidx.compose.runtime.LaunchedEffect(payTarget?.invoice?.id) { amountDraft = payTarget?.let { au.mainspring.nativeapp.ui.plainDollars(viewModel.remainingCents(it)) } ?: ""; refDraft = "" }
    Column(Modifier.fillMaxSize()) {
        au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.weight(1f)) { LazyColumn(
            contentPadding = PaddingValues(start = FinGutter, end = FinGutter, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.fillMaxSize().testTag("invoices-list"),
        ) {
            item { FinTitle("Invoices", gutter = 0.dp) }
            item { FinSearchField(query, { query = it }, "Search invoice number...", Modifier, onSearch = null, fieldTag = "invoices-search") }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    FinSegmentRow(listOf(null to "All", "unpaid" to "Unpaid", "paid" to "Paid"), filter, { filter = it })
                    FinSegmentRow(listOf(null to "All types", "watch" to "Watch", "mobile" to "Mobile"), type, { type = it })
                }
            }
            if(state.loading && state.invoices.isEmpty()) item { androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.error?.let { e -> item { au.mainspring.nativeapp.ui.ErrorBanner(e, onRetry = viewModel::refresh) } }
            (state.notice ?: printError)?.let { n -> item { au.mainspring.nativeapp.ui.ErrorBanner(n, onRetry = { viewModel.clearNotice(); printError = null }) } }
            if(!state.loading && state.error == null && shown.isEmpty()) item {
                FinEmptyCard(if(query.isBlank() && type == null && filter == null) "No invoices yet." else "No invoices match these filters.")
            }
            items(shown, key = { (if(it.mobile) "m-" else "w-") + it.id }) { inv ->
                val open = { if(inv.mobile) onOpenMobileInvoice(inv.jobId) else onOpenInvoice(inv.id) }
                var menu by remember { mutableStateOf(false) }
                FinCard(onClick = open) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
                        FlowRow(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            FinDocNumber(inv.number)
                            FinStatusPill(inv.status)
                            if(inv.mobile) FinChip("MOBILE")
                        }
                        Text(formatCents(inv.totalCents, inv.currency), style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold))
                    }
                    Spacer(Modifier.heightIn(min = 4.dp))
                    Text(au.mainspring.nativeapp.ui.formatShopDate(inv.createdAt).substringBefore(' '), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    inv.customerName?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.Medium)) }
                    if(inv.subtotalCents != null && inv.taxCents != null)
                        Text("Subtotal ${formatCents(inv.subtotalCents, inv.currency)} Â· Tax ${formatCents(inv.taxCents, inv.currency)}", style = MaterialTheme.typography.bodySmall)
                    else Text(inv.title, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.heightIn(min = 6.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if(!inv.mobile && inv.status == "unpaid" && au.mainspring.nativeapp.TokenStore.canManageInvoices())
                            FinOutlinedLabel(if(state.payBusy) "Loading…" else "Record payment", { viewModel.beginPay(inv.id) }, Modifier.weight(1f).testTag("invoice-row-pay"), enabled = !state.payBusy)
                        else FinOutlinedLabel(if(inv.mobile) "Open job invoice" else "Open invoice", open, Modifier.weight(1f))
                        Box {
                            FinOutlinedButton({ menu = true }, Modifier.width(56.dp).testTag("invoice-more")) { FinGlyph("dots", MaterialTheme.colorScheme.onSurface, 20.dp) }
                            DropdownMenu(menu, { menu = false }) {
                                DropdownMenuItem({ Text("Open invoice") }, { menu = false; open() })
                                DropdownMenuItem({ Text("Print / PDF") }, { menu = false; printScope.launch { try { au.mainspring.nativeapp.printInvoiceSummary(context, viewModel.summaryFor(inv)) } catch(e: kotlinx.coroutines.CancellationException) { throw e } catch(e: Exception) { printError = e.message ?: "Could not open printing." } } }, modifier = Modifier.testTag("invoice-row-print"))
                                DropdownMenuItem({ Text("Copy invoice number") }, { menu = false; clipboard.setText(AnnotatedString(inv.number)) })
                            }
                        }
                    }
                }
            }
            if(state.invoices.size < state.total) item {
                FinOutlinedLabel(if(state.loading) "Loadingâ€¦" else "Load more invoices", viewModel::loadMore, Modifier.fillMaxWidth(), enabled = !state.loading)
            }
        } }
    }
    if(payTarget != null) {
        val cents = au.mainspring.nativeapp.InvoiceDetailViewModel.parseDollarsToCents(amountDraft)
        val remaining = viewModel.remainingCents(payTarget)
        androidx.compose.material3.AlertDialog(onDismissRequest = viewModel::dismissPay, title = { Text("Record payment") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("#${payTarget.invoice.invoiceNumber} · Remaining ${formatCents(remaining, payTarget.invoice.currency)}", style = MaterialTheme.typography.bodySmall)
                au.mainspring.nativeapp.ui.AtelierTextField(value = amountDraft, onValueChange = { amountDraft = it }, label = { Text("Amount") }, singleLine = true, modifier = Modifier.testTag("invoice-row-pay-amount"))
                au.mainspring.nativeapp.ui.AtelierTextField(value = refDraft, onValueChange = { refDraft = it }, label = { Text("Reference (optional)") }, singleLine = true)
            } },
            confirmButton = { androidx.compose.material3.Button(onClick = { cents?.let { viewModel.submitPay(it, refDraft) } }, enabled = !state.payBusy && cents != null && cents <= remaining) { Text(if(state.payBusy) "Saving…" else "Save") } },
            dismissButton = { androidx.compose.material3.TextButton(onClick = viewModel::dismissPay) { Text("Cancel") } })
    }
}

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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.InvoicesViewModel
import au.mainspring.nativeapp.ui.formatCents

@Composable
fun InvoicesScreen(
    onOpenInvoice: (String) -> Unit,
    onBack: (() -> Unit)? = null,
    /** Called with the mobile job id; expected route: "mobileFinance/{jobId}?business=false". */
    onOpenMobileInvoice: (jobId: String) -> Unit = {},
    viewModel: InvoicesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var filter by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf<String?>(null) }
    var type by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf<String?>(null) }
    var query by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("") }
    val shown = au.mainspring.nativeapp.mergedInvoices(state, type, filter, query)
    Column(Modifier.fillMaxSize()) {
        if(onBack != null) au.mainspring.nativeapp.ui.BackLargeHeader("More", "Money & performance", "Invoices", onBack)
        au.mainspring.nativeapp.ui.FilterRow(listOf(null to "All", "unpaid" to "Unpaid", "paid" to "Paid"), filter, { filter = it }, Modifier.padding(top = 4.dp))
        if (state.mobile.isNotEmpty()) au.mainspring.nativeapp.ui.FilterRow(listOf<Pair<String?, String>>(null to "All types", "watch" to "Watch", "mobile" to "Mobile"), type, { type = it })
        au.mainspring.nativeapp.ui.AtelierTextField(query, { query = it }, label = { Text("Search invoice number or customer") }, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).testTag("invoices-search"), singleLine = true)
        if (state.loading && state.invoices.isEmpty()) androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
        state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp, vertical = 8.dp), onRetry = viewModel::refresh) }
        if (!state.loading && state.error == null && shown.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No invoices yet", if (query.isBlank() && type == null && filter == null) "Invoices appear here once a quote is approved and invoiced." else "No invoices match these filters.")
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(if(au.mainspring.nativeapp.ui.LocalCalibre.current) 0.dp else 8.dp),
            modifier = Modifier.fillMaxSize().weight(1f, fill = true),
        ) {
            items(shown, key = { (if (it.mobile) "m-" else "w-") + it.id }) { inv ->
                au.mainspring.nativeapp.ui.ListCard({ if (inv.mobile) onOpenMobileInvoice(inv.jobId) else onOpenInvoice(inv.id) }) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(inv.number, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        au.mainspring.nativeapp.ui.StatusPill(inv.status)
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(inv.title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                        Text(formatCents(inv.totalCents, inv.currency), style = MaterialTheme.typography.titleMedium)
                    }
                    Text(listOfNotNull(if (inv.mobile) "Mobile" else null, inv.customerName, au.mainspring.nativeapp.ui.formatShopDate(inv.createdAt).substringBefore(' ')).joinToString(" · "),
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            if(state.invoices.size < state.total) item {
                androidx.compose.material3.OutlinedButton(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text(if(state.loading) "Loading…" else "Load more invoices") }
            }
        }
    }
}

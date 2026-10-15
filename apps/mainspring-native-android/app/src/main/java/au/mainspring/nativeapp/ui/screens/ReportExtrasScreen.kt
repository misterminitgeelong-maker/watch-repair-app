package au.mainspring.nativeapp.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ReportExtrasViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.CategorySales
import au.mainspring.nativeapp.saveReportExport
import au.mainspring.nativeapp.ui.*
import au.mainspring.nativeapp.userMessage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.math.BigDecimal

private fun money(cents: Long) = "$" + BigDecimal.valueOf(cents, 2).toPlainString()

/** Sales by category with CSV export, plus the shop audit log. Not yet linked from the shell. */
@Composable fun ReportExtrasScreen(onBack: () -> Unit, viewModel: ReportExtrasViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var category by remember { mutableStateOf("all") }
    var generation by remember { mutableStateOf(0L) }
    val saver = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        if(uri == null) { viewModel.setExportBusy(false); return@rememberLauncherForActivityResult }
        scope.launch {
            viewModel.setExportBusy(true)
            try {
                check(TokenStore.sessionGeneration() == generation) { "The signed-in shop changed. Choose the export again." }
                saveReportExport(context, uri, viewModel.downloadSales(category))
                viewModel.setExportBusy(false, "Sales CSV saved.")
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { viewModel.setExportBusy(false, e.userMessage()) }
        }
    }
    Scaffold(topBar = { BackLargeHeader("More", "Reports", "Sales & activity", onBack) }) { padding ->
        if(!state.allowed) {
            Box(Modifier.fillMaxSize().padding(padding).padding(16.dp)) { EmptyState("Owner or manager only", "Sales and activity reports need an owner or manager account.") }
            return@Scaffold
        }
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("report-extras"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { SectionLabel("Sales by category") }
            item {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("day", "week", "month", "quarter").forEach { p -> TabChip(state.period == p, { viewModel.selectPeriod(p) }, label = { Text(p.replaceFirstChar { it.uppercase() }) }) }
                }
            }
            if(state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.summaryError?.let { item { ErrorBanner(it, onRetry = viewModel::loadSummary) } }
            state.summary?.let { s ->
                item { CategoryPanel("Watch repairs", s.watch) }
                item { CategoryPanel("Shoe repairs", s.shoe) }
                item { CategoryPanel("Mobile services", s.mobile) }
            }
            item {
                FlatPanel {
                    Text("Download the sales rows for this period. Choose where to save the file.", style = MaterialTheme.typography.bodySmall)
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("all" to "All", "watch" to "Watch", "shoe" to "Shoe", "mobile" to "Mobile").forEach { (key, label) -> TabChip(category == key, { category = key }, label = { Text(label) }) }
                    }
                    SecondaryAction({ generation = TokenStore.sessionGeneration(); saver.launch("mainspring-sales-$category-${state.period}.csv") }, Modifier.fillMaxWidth().testTag("sales-export"), enabled = !state.exportBusy) {
                        Text(if(state.exportBusy) "Preparing…" else "Download sales CSV")
                    }
                    state.exportInfo?.let { Text(it, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.testTag("sales-export-info")) }
                }
            }
            item { SectionLabel("Shop activity") }
            state.activityError?.let { item { ErrorBanner(it, onRetry = viewModel::refresh) } }
            if(state.activity.isEmpty() && state.activityError == null && !state.loading) item { EmptyState("No activity yet", "Changes made by your team will be listed here.") }
            items(state.activity, key = { it.id }) { event ->
                FlatPanel {
                    Text(event.summary, style = MaterialTheme.typography.bodyMedium)
                    MonoLabel(listOfNotNull(event.actorEmail, formatShopDate(event.createdAt)).joinToString(" · "))
                }
            }
        }
    }
}

@Composable private fun CategoryPanel(title: String, sales: CategorySales?) {
    if(sales == null) return
    FlatPanel {
        Text(title, style = MaterialTheme.typography.titleMedium)
        MetricStrip(listOf("Jobs" to sales.jobs.toString(), "Billed" to money(sales.billedCents), "Received" to money(sales.revenueCents)))
        DetailRow("Outstanding", money(sales.outstandingCents))
        if(sales.costCents > 0) DetailRow("Recorded cost", money(sales.costCents))
    }
}

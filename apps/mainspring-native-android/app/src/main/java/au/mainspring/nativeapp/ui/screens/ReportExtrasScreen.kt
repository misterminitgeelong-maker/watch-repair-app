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
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ReportExtrasViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.CategorySales
import au.mainspring.nativeapp.saveReportExport
import au.mainspring.nativeapp.statusRows
import au.mainspring.nativeapp.ui.*
import au.mainspring.nativeapp.userMessage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import au.mainspring.nativeapp.ReportRange
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

private fun money(cents: Long) = "$" + BigDecimal.valueOf(cents, 2).toPlainString()

/** Sales by category (calendar period or custom range) with CSV export, GST, technician and trend breakdowns, plus the shop audit log. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun ReportExtrasScreen(onBack: () -> Unit, viewModel: ReportExtrasViewModel = viewModel(), embedded: Boolean = false) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var category by remember { mutableStateOf("all") }
    var generation by remember { mutableStateOf(0L) }
    var rangeOpen by remember { mutableStateOf(false) }
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
    Scaffold(contentWindowInsets = if(embedded) WindowInsets(0, 0, 0, 0) else ScaffoldDefaults.contentWindowInsets, containerColor = MaterialTheme.colorScheme.background,
        topBar = { if(!embedded) FinTitle("Sales & activity", onBack = onBack, insets = true) }) { padding ->
        if(!state.allowed) {
            Box(Modifier.fillMaxSize().padding(padding).padding(16.dp)) { EmptyState("Owner or manager only", "Sales and activity reports need an owner or manager account.") }
            return@Scaffold
        }
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("report-extras"), contentPadding = PaddingValues(start = FinGutter, end = FinGutter, top = 12.dp, bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            state.summary?.let { sm ->
                val all = listOfNotNull(sm.watch, sm.shoe, sm.mobile)
                val rev = all.sumOf { it.revenueCents }; val cost = all.sumOf { it.costCents }; val out = all.sumOf { it.outstandingCents }
                item { FinKpiCard("Revenue", money(rev), "dollar", FinKpi.RevenueTint, FinKpi.RevenueBg, valueTag = "kpi-Revenue") }
                item { FinKpiCard("Cost", money(cost), "wallet", FinKpi.CostTint, FinKpi.CostBg, valueTag = "kpi-Cost") }
                item { FinKpiCard("Gross profit", money(rev - cost), "scales", FinKpi.ProfitTint, FinKpi.ProfitBg, valueTag = "kpi-Profit") }
                item { FinKpiCard("Outstanding", money(out), "bars", FinKpi.OutstandingTint, FinKpi.OutstandingBg, valueTag = "kpi-Outstanding") }
            }
            item { Text("Sales by Category", Modifier.padding(top = 8.dp).semantics { heading() }, style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold)) }
            item {
                FinPillSwitch(listOf("day", "week", "month", "quarter").map { it to it.replaceFirstChar { c -> c.uppercase() } } + (ReportRange.CUSTOM to "Custom"), state.period, { p ->
                    viewModel.selectPeriod(p); if(p == ReportRange.CUSTOM) rangeOpen = true
                })
            }
            if(state.period == ReportRange.CUSTOM) item {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    SecondaryAction({ rangeOpen = true }, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("range-pick")) {
                        Text(if(state.customFrom != null && state.customTo != null) "${formatShopDate(state.customFrom!!)} to ${formatShopDate(state.customTo!!)}" else "Choose start and end dates")
                    }
                    state.rangeError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                }
            }
            if(state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.summaryError?.let { item { ErrorBanner(it, onRetry = viewModel::loadSummary) } }
            state.summary?.let { s ->
                item { CategoryPanel("Watch repairs", s.watch) }
                item { CategoryPanel("Shoe repairs", s.shoe) }
                item { CategoryPanel("Mobile services", s.mobile) }
            }
            state.gst?.let { g -> item { GstBreakdownPanel(g) } }
            state.gstError?.let { item { ErrorBanner("GST summary: $it", onRetry = viewModel::loadSummary) } }
            item { SectionLabel("Technicians and trends") }
            state.techsError?.let { item { ErrorBanner("Technician breakdown: $it", onRetry = viewModel::refresh) } }
            if(state.techs.isNotEmpty()) item { TechLeaderboardPanel(state.techs) }
            item {
                FinPillSwitch(listOf(6, 12).map { it.toString() to "$it months" }, state.trendMonths.toString(), { viewModel.selectTrendMonths(it.toInt()) })
            }
            state.trendsError?.let { item { ErrorBanner("Trends: $it", onRetry = viewModel::refresh) } }
            if(state.trends.isNotEmpty()) item { TrendsPanel(state.trends) }
            item {
                FlatPanel {
                    Text("Download the sales rows for this period. Choose where to save the file.", style = MaterialTheme.typography.bodySmall)
                    FinPillSwitch(listOf("all" to "All", "watch" to "Watch", "shoe" to "Shoe", "mobile" to "Mobile"), category, { category = it })
                    SecondaryAction({ generation = TokenStore.sessionGeneration(); saver.launch("mainspring-sales-$category-${state.range.fileLabel()}.csv") }, Modifier.fillMaxWidth().testTag("sales-export"), enabled = !state.exportBusy && state.range.validate() == null) {
                        Text(if(state.exportBusy) "Preparing…" else "Download sales CSV")
                    }
                    state.exportInfo?.let { Text(it, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.testTag("sales-export-info")) }
                }
            }
            item { SectionLabel("Status breakdown") }
            state.statusError?.let { item { ErrorBanner("Status panels: $it", onRetry = viewModel::refresh) } }
            state.statusSummary?.let { st ->
                item { StatusPanel("Job status", statusRows(st.jobsByStatus), "No jobs yet.", "status-jobs") }
                item { StatusPanel("Quote status", statusRows(st.quotesByStatus), "No quotes sent yet.", "status-quotes") }
                if(st.counts.shoeJobs > 0 && st.shoeJobsByStatus != null) {
                    item { StatusPanel("Shoe job status", statusRows(st.shoeJobsByStatus), "No shoe jobs yet.", "status-shoe-jobs") }
                    st.shoeQuotes?.let { sq -> item { StatusPanel("Shoe quote status", statusRows(sq.byStatus), "No shoe quotes sent yet.", "status-shoe-quotes", footer = "Approval rate ${"%.0f".format(sq.approvalRatePercent)}%") } }
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
    if(rangeOpen) {
        val picker = rememberDateRangePickerState(
            initialSelectedStartDateMillis = state.customFrom?.let { LocalDate.parse(it).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli() },
            initialSelectedEndDateMillis = state.customTo?.let { LocalDate.parse(it).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli() },
        )
        DatePickerDialog(onDismissRequest = { rangeOpen = false }, confirmButton = {
            TextButton(onClick = {
                val from = picker.selectedStartDateMillis; val to = picker.selectedEndDateMillis ?: from
                if(from != null && to != null) viewModel.setCustomRange(pickerDate(from), pickerDate(to))
                rangeOpen = false
            }, enabled = picker.selectedStartDateMillis != null, modifier = Modifier.heightIn(min = 48.dp)) { Text("Apply range") }
        }, dismissButton = { TextButton({ rangeOpen = false }, Modifier.heightIn(min = 48.dp)) { Text("Cancel") } }) {
            DateRangePicker(picker, Modifier.height(480.dp))
        }
    }
}

private fun pickerDate(millis: Long): String = Instant.ofEpochMilli(millis).atZone(ZoneOffset.UTC).toLocalDate().toString()

@Composable private fun CategoryPanel(title: String, sales: CategorySales?) {
    if(sales == null) return
    FlatPanel {
        Text(title, style = MaterialTheme.typography.titleMedium)
        MetricStrip(listOf("Jobs" to sales.jobs.toString(), "Billed" to money(sales.billedCents), "Received" to money(sales.revenueCents)))
        DetailRow("Outstanding", money(sales.outstandingCents))
        if(sales.costCents > 0) DetailRow("Recorded cost", money(sales.costCents))
    }
}

@Composable private fun StatusPanel(title: String, rows: List<au.mainspring.nativeapp.StatusRow>, empty: String, tag: String, footer: String? = null) {
    FlatPanel(Modifier.testTag(tag)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        if(rows.isEmpty()) Text(empty, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        rows.forEach { DetailRow(it.label, it.count.toString()) }
        footer?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

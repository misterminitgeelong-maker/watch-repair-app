package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.screens.LinkAction as OutlinedButton
import au.mainspring.nativeapp.ui.FlatPanel
import au.mainspring.nativeapp.ui.MetricStrip
import au.mainspring.nativeapp.ui.SectionLabel
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.userMessage
import au.mainspring.nativeapp.saveReportExport
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import au.mainspring.nativeapp.PeriodReportsViewModel
import au.mainspring.nativeapp.ui.formatShopDate
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneOffset
import java.util.Locale

private fun reportAmount(cents: Long) = BigDecimal.valueOf(cents, 2).toPlainString()
private fun reportPercent(value: Double) = String.format(Locale.UK, "%.1f%%", value)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PeriodReportsScreen(onBack: () -> Unit, model: PeriodReportsViewModel = viewModel(), embedded: Boolean = false) {
    val state by model.state.collectAsStateWithLifecycle()
    var dateOpen by remember { mutableStateOf(false) }
    var exportPeriod by rememberSaveable { mutableStateOf("week") }
    var exportDate by rememberSaveable { mutableStateOf("") }
    var exportGeneration by rememberSaveable { mutableStateOf(0L) }
    var exportBusy by remember { mutableStateOf(false) }
    var exportInfo by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        if(uri != null) scope.launch {
            exportBusy = true; exportInfo = null
            try {
                check(TokenStore.sessionGeneration() == exportGeneration) { "The signed-in shop changed. Open the report and choose an export location again." }
                val bytes = model.exportCsv(exportPeriod, exportDate)
                try { saveReportExport(context, uri, bytes) }
                catch(e: java.io.IOException) { throw IllegalStateException("Could not save the CSV. Choose another file location.", e) }
                exportInfo = "CSV saved for ${formatShopDate(exportDate)} ($exportPeriod)."
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { exportInfo = e.userMessage() }
            finally { exportBusy = false }
        }
    }
    Scaffold(contentWindowInsets=if(embedded) WindowInsets(0,0,0,0) else ScaffoldDefaults.contentWindowInsets,topBar = { if(!embedded) au.mainspring.nativeapp.ui.BackLargeHeader("More", "Money & performance", "Reports", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("period-report-list"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("day", "week", "month", "quarter").forEach { period ->
                        au.mainspring.nativeapp.ui.TabChip(state.period == period, { model.select(period = period) }, label = { Text(period.replaceFirstChar { it.uppercase() }) })
                    }
                }
                Spacer(Modifier.height(8.dp))
                OutlinedButton({ dateOpen = true },modifier=Modifier.fillMaxWidth()) { Text("Report date: ${formatShopDate(state.date)}") }
                Row(Modifier.fillMaxWidth().padding(top=8.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(model::refresh, enabled = !state.loading, modifier=Modifier.weight(1f)) { Text("Refresh") }
                    OutlinedButton(onClick = {
                        exportPeriod = state.period; exportDate = state.date; exportGeneration = TokenStore.sessionGeneration()
                        export.launch("mainspring-report-${state.period}-${state.date}.csv")
                    }, enabled = !state.loading && state.current != null && !exportBusy, modifier=Modifier.weight(1f)) { Text(if(exportBusy) "Preparing…" else "Export CSV") }
                }
                exportInfo?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            }
            if(state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.error?.let { item { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = model::refresh) } }
            state.current?.let { current ->
                item {
                    if(au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.MonoLabel(state.period.replaceFirstChar { it.uppercase() } + " report")
                    Text("${formatShopDate(current.start)} – ${formatShopDate(current.end)}", style = if(au.mainspring.nativeapp.ui.LocalCalibre.current) MaterialTheme.typography.headlineSmall else MaterialTheme.typography.titleLarge)
                    state.previous?.let { Text("Compared with ${formatShopDate(it.start)} – ${formatShopDate(it.end)}", style = MaterialTheme.typography.bodySmall) }
                    state.comparisonError?.let { Text("Previous period unavailable: $it", color = MaterialTheme.colorScheme.error) }
                }
                item { MetricStrip(listOf("Revenue" to reportAmount(current.financials.revenue),"Jobs" to current.jobs.toString(),"Avg / job" to reportAmount(current.operations.averageRevenue))) }
                item { RevenueComparison(current.financials.revenue,state.previous?.financials?.revenue) }
                item { FlatPanel {
                    SectionLabel("Jobs by service")
                    val max=maxOf(current.watchJobs,current.shoeJobs,current.mobileJobs,1L)
                    listOf("Watch" to current.watchJobs,"Shoe" to current.shoeJobs,"Mobile services" to current.mobileJobs).forEach {(label,value)->
                        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {Text(label,style=MaterialTheme.typography.bodySmall);Text(value.toString(),style=MaterialTheme.typography.labelLarge)}
                        LinearProgressIndicator(progress={value.toFloat()/max.toFloat()},modifier=Modifier.fillMaxWidth(),color=MaterialTheme.colorScheme.onSurface)
                    }
                } }
                item {
                    ReportGroup("Jobs and customers", listOf(
                        Triple("Jobs opened", current.jobs.toString(), state.previous?.jobs?.toString()),
                        Triple("Watch jobs", current.watchJobs.toString(), state.previous?.watchJobs?.toString()),
                        Triple("Shoe jobs", current.shoeJobs.toString(), state.previous?.shoeJobs?.toString()),
                        Triple("Mobile jobs", current.mobileJobs.toString(), state.previous?.mobileJobs?.toString()),
                        Triple("New customers", current.customers.toString(), state.previous?.customers?.toString()),
                    ))
                }
                item {
                    val previous = state.previous?.financials
                    ReportGroup("Financial performance", listOf(
                        Triple("Billed", reportAmount(current.financials.billed), previous?.let { reportAmount(it.billed) }),
                        Triple("Revenue", reportAmount(current.financials.revenue), previous?.let { reportAmount(it.revenue) }),
                        Triple("Cost", reportAmount(current.financials.cost), previous?.let { reportAmount(it.cost) }),
                        Triple("Gross profit", reportAmount(current.financials.profit), previous?.let { reportAmount(it.profit) }),
                        Triple("Gross margin", reportPercent(current.financials.margin), previous?.let { reportPercent(it.margin) }),
                    ))
                }
                item {
                    val previous = state.previous?.funnel
                    ReportGroup("Sales funnel", listOf(
                        Triple("Quotes sent", current.funnel.sent.toString(), previous?.sent?.toString()),
                        Triple("Quotes approved", current.funnel.approved.toString(), previous?.approved?.toString()),
                        Triple("Quotes declined", current.funnel.declined.toString(), previous?.declined?.toString()),
                        Triple("Approval rate", reportPercent(current.funnel.approvalRate), previous?.let { reportPercent(it.approvalRate) }),
                    ))
                }
                item {
                    ReportGroup("Operations", listOf(
                        Triple("Work minutes", current.operations.minutes.toString(), state.previous?.operations?.minutes?.toString()),
                        Triple("Average revenue per job", reportAmount(current.operations.averageRevenue), state.previous?.operations?.let { reportAmount(it.averageRevenue) }),
                    ))
                }
                item { Text("Periods follow the server's UTC reporting days, so the current period may be incomplete.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }
    if(dateOpen) {
        val picker = rememberDatePickerState(initialSelectedDateMillis = LocalDate.parse(state.date).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli())
        DatePickerDialog(onDismissRequest = { dateOpen = false }, confirmButton = {
            TextButton(onClick = { picker.selectedDateMillis?.let { model.select(date = java.time.Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate().toString()) }; dateOpen = false }) { Text("Show report") }
        }, dismissButton = { TextButton({ dateOpen = false }) { Text("Cancel") } }) { DatePicker(picker) }
    }
}

@Composable
private fun RevenueComparison(current: Long,previous: Long?) {
    FlatPanel {
        Text("Revenue comparison",style=MaterialTheme.typography.titleMedium)
        if(current == 0L && (previous ?: 0L) == 0L) {
            Text("No revenue recorded in either period yet.",style=MaterialTheme.typography.bodyMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            val maximum=maxOf(current,previous ?: 0,1).toFloat()
            Row(Modifier.fillMaxWidth().height(130.dp),horizontalArrangement=Arrangement.spacedBy(16.dp),verticalAlignment=androidx.compose.ui.Alignment.Bottom) {
                listOf("Previous period" to previous,"Current period" to current).forEach {(label,value)->Column(Modifier.weight(1f),horizontalAlignment=androidx.compose.ui.Alignment.CenterHorizontally) {
                    Text(value?.let(::reportAmount) ?: "Unavailable",style=MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(4.dp))
                    Box(Modifier.fillMaxWidth().height((maxOf(value ?: 0,0).toFloat()/maximum*80).dp).background(if(label=="Current period") MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface))
                    Text(label,style=MaterialTheme.typography.labelSmall)
                } }
            }
        }
        Text("The current period may still be in progress.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
@Composable
private fun ReportGroup(title: String, rows: List<Triple<String, String, String?>>) {
    FlatPanel {
        Text(title, style = MaterialTheme.typography.titleMedium)
        rows.forEach { (label, current, previous) ->
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                Text(label,Modifier.weight(1f),style=MaterialTheme.typography.bodySmall)
                Column(horizontalAlignment=androidx.compose.ui.Alignment.End) {
                    Text(current,modifier=Modifier.testTag("report-value-$label"),style=MaterialTheme.typography.titleSmall)
                    previous?.let {Text("Previous: $it",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                }
            }
            HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

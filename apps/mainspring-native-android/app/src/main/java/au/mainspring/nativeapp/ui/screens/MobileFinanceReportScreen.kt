package au.mainspring.nativeapp.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.*
import kotlinx.coroutines.launch

private fun cents(value: Long, currency: String) = formatCents(value.coerceIn(Int.MIN_VALUE.toLong(), Int.MAX_VALUE.toLong()).toInt(), currency)
private fun amount(value: Double?, unit: String, currency: String): String = when {
    value == null -> "-"
    unit == "cents" -> cents(Math.round(value), currency)
    unit == "pct" -> String.format("%.1f%%", value)
    unit == "minutes" -> "${Math.round(value)} min"
    else -> Math.round(value).toString()
}

@Composable fun MobileFinanceReportScreen(onBack: () -> Unit, viewModel: MobileFinanceReportViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var exportKind by rememberSaveable { mutableStateOf("summary") }
    var exportPeriod by rememberSaveable { mutableStateOf("week") }
    var exportGeneration by rememberSaveable { mutableStateOf(0L) }
    var exportBusy by remember { mutableStateOf(false) }
    var exportInfo by remember { mutableStateOf<String?>(null) }
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        if(uri != null) scope.launch {
            exportBusy = true; exportInfo = null
            try {
                check(TokenStore.sessionGeneration() == exportGeneration) { "The signed-in shop changed. Open the report and choose an export location again." }
                val bytes = viewModel.exportCsv(exportPeriod, exportKind)
                saveReportExport(context, uri, bytes)
                exportInfo = "CSV saved ($exportKind, ${mobileFinancePeriods[exportPeriod]})."
            } catch(e: kotlinx.coroutines.CancellationException) { throw e }
            catch(e: Exception) { exportInfo = e.userMessage() }
            finally { exportBusy = false }
        }
    }
    Scaffold(topBar = { BackLargeHeader("More", "Mobile services", "Finance report", onBack) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    TabChip(state.mode == "operations", { viewModel.mode("operations") }, { Text("Operations") })
                    TabChip(state.mode == "finance", { viewModel.mode("finance") }, { Text("Finance") })
                }
            }
            if(state.mode == "finance") item {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    mobileFinancePeriods.forEach { (value, label) -> TabChip(state.period == value, { viewModel.period(value) }, { Text(label) }) }
                }
            }
            if(state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.error?.let { message -> item { ErrorBanner(message, onRetry = viewModel::refresh) } }
            if(state.mode == "operations") state.cockpit?.let { operations(it, currency) }
            else state.finance?.let { finance(it, currency) }
            if(state.mode == "finance" && state.finance != null) {
                item {
                    SectionLabel("Export")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("summary" to "Summary CSV", "invoices" to "Invoices CSV").forEach { (kind, label) ->
                            OutlinedButton(onClick = {
                                exportKind = kind; exportPeriod = state.period; exportGeneration = TokenStore.sessionGeneration()
                                export.launch("mainspring-mobile-finance-$kind-${state.period}.csv")
                            }, enabled = !state.loading && !exportBusy, modifier = Modifier.weight(1f)) { Text(if(exportBusy) "Preparing…" else label) }
                        }
                    }
                    exportInfo?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                }
            }
        }
    }
}

private fun LazyListScope.operations(data: MobileCockpitResponse, currency: String) {
    val late = data.attention.firstOrNull { it.key == "late" }
    item {
        Spacer(Modifier.height(8.dp))
        MetricStrip(listOf("LATE" to (late?.count ?: 0).toString(), "OUTSTANDING" to cents(data.outstanding.current, currency),
            "OVERDUE" to cents(data.outstanding.overdueCents, currency)))
    }
    item { SectionLabel("Week money") }
    items(data.metrics.filter { it.unit == "cents" }, key = { "m-" + it.key }) { m ->
        ReportRow(m.label, "LAST WEEK ${amount(m.previous, m.unit, currency)}${if(m.partial) " · WEEK IN PROGRESS" else ""}", amount(m.current, m.unit, currency))
    }
    data.weeklyTargetCents?.let { target -> item { MonoLabel("WEEKLY TARGET ${cents(target, currency)}") } }
    item {
        SectionLabel("Capacity today")
        MetricStrip(listOf("TECHS" to data.capacity.technicians.toString(), "BOOKED" to "${data.capacity.bookedMinutes / 60}h",
            "AVAILABLE" to "${data.capacity.availableMinutes / 60}h", "CONFLICTS" to data.capacity.conflicts.toString()))
        if(data.capacity.unassignedToday > 0) MonoLabel("${data.capacity.unassignedToday} JOBS TODAY HAVE NO TECHNICIAN")
    }
    item { SectionLabel("Late runs") }
    if(late == null || late.items.isEmpty()) item { EmptyState("No late runs", "Nothing booked has slipped past its time.") }
    else {
        items(late.items, key = { "late-" + it.id }) { job ->
            FlatPanel {
                Text("${job.jobNumber} · ${job.title}", style = MaterialTheme.typography.titleSmall)
                job.customerName?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                MonoLabel(listOfNotNull(job.scheduledAt?.let { "BOOKED ${formatShopDate(it)}" }, "TECH ${job.assignedName ?: "Unassigned"}").joinToString(" · ").uppercase())
            }
        }
        if(late.count > late.items.size) item { MonoLabel("SHOWING ${late.items.size} OF ${late.count}") }
    }
    item { SectionLabel("Receivables ageing") }
    val aging = data.outstanding
    items(listOf(
        Triple("Current", aging.agingCents.current, aging.agingCounts.current),
        Triple("8 to 30 days", aging.agingCents.d8To30, aging.agingCounts.d8To30),
        Triple("31+ days", aging.agingCents.d31Plus, aging.agingCounts.d31Plus),
    ), key = { "age-" + it.first }) { (label, c, n) -> ReportRow(label, "$n invoices", cents(c, currency)) }
    item {
        SectionLabel("Follow-ups")
        ReportRow("Quotes awaiting reply", "", "${data.followUps.quotes.count} · ${cents(data.followUps.quotes.valueCents, currency)}")
        ReportRow("Unconfirmed bookings", "", data.followUps.confirmations.count.toString())
        ReportRow("Completed, unpaid", "", "${data.followUps.completedUnpaid.count} · ${cents(data.followUps.completedUnpaid.valueCents, currency)}")
        ReportRow("Overdue invoices", "", "${data.followUps.overdueInvoices.count} · ${cents(data.followUps.overdueInvoices.valueCents, currency)}")
    }
}

private fun LazyListScope.finance(data: MobileFinanceResponse, currency: String) {
    val headlineKeys = listOf("collected", "invoiced", "outstanding")
    item {
        Spacer(Modifier.height(8.dp))
        MonoLabel(data.period.label.uppercase() + if(data.period.complete) "" else " · IN PROGRESS")
        val headline = headlineKeys.mapNotNull { key -> data.metrics.firstOrNull { it.key == key } }
        if(headline.isNotEmpty()) MetricStrip(headline.map { it.label.uppercase() to amount(it.current, it.unit, currency) })
    }
    item { SectionLabel("Figures") }
    items(data.metrics.filter { it.key !in headlineKeys }, key = { "fm-" + it.key }) { m ->
        ReportRow(m.label, "PREVIOUS ${amount(m.previous, m.unit, currency)}", amount(m.current, m.unit, currency))
    }
    data.target?.let { t ->
        item {
            SectionLabel("Target")
            ReportRow("Collected against target", "TARGET ${cents(t.periodCents, currency)}",
                "${cents(t.collectedCents, currency)}${t.attainmentPct?.let { " · ${Math.round(it)}%" } ?: ""}")
        }
    }
    if(data.conversion.isNotEmpty()) {
        item { SectionLabel("Conversion") }
        items(data.conversion, key = { "cv-" + it.key }) { c ->
            ReportRow(c.label, "${c.numerator} OF ${c.denominator}${c.previousPct?.let { " · PREVIOUS ${Math.round(it)}%" } ?: ""}", c.pct?.let { "${Math.round(it)}%" } ?: "-")
        }
    }
    item { SectionLabel("Receivables ageing"); MonoLabel("TOTAL ${cents(data.arAgeing.totalCents, currency)} · OVERDUE ${cents(data.arAgeing.overdueCents, currency)}") }
    if(data.arAgeing.buckets.isEmpty()) item { EmptyState("No open invoices") }
    items(data.arAgeing.buckets, key = { "ab-" + it.key }) { b -> ReportRow(b.label, "${b.count} invoices", cents(b.cents, currency)) }
    if(data.technicians.isNotEmpty()) {
        item { SectionLabel("Technicians") }
        items(data.technicians, key = { "t-" + it.name }) { t ->
            ReportRow(t.name, "${t.jobsCompleted} COMPLETED · INVOICED ${cents(t.invoicedCents, currency)}${t.utilisationPct?.let { " · ${Math.round(it)}% BUSY" } ?: ""}", cents(t.collectedCents, currency))
        }
    }
    if(data.dataQuality.isNotEmpty()) item {
        SectionLabel("How to read these figures")
        data.dataQuality.forEach { Text(it.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable private fun ReportRow(title: String, detail: String, value: String) {
    FlatPanel {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleSmall)
                if(detail.isNotBlank()) MonoLabel(detail.uppercase())
            }
            Text(value, style = MaterialTheme.typography.titleMedium)
        }
    }
}

package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.DashboardViewModel
import au.mainspring.nativeapp.ui.formatCents

@Composable
fun DashboardScreen(sessionSummary: String?,apiBaseUrl: String,onLogout: () -> Unit,features: Set<String>,
    onNewMobileJob: () -> Unit,onOpenWatchJobs: () -> Unit,onOpenQuotes: () -> Unit,onOpenInvoices: () -> Unit,
    onOpenShoeJobs: () -> Unit,onOpenAutoJobs: () -> Unit,onOpenAutoJob: (String) -> Unit) {
    if(!au.mainspring.nativeapp.TokenStore.canManageInvoices()) {
        LegacyDashboardScreen(sessionSummary,apiBaseUrl,onLogout,features,onNewMobileJob,onOpenWatchJobs,onOpenQuotes,onOpenInvoices,onOpenShoeJobs,onOpenAutoJobs,onOpenAutoJob)
        return
    }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal=16.dp,vertical=8.dp)) {
            Text("Operations dashboard",style=MaterialTheme.typography.headlineMedium)
            au.mainspring.nativeapp.TokenStore.shopValue("name")?.let {Text(it,style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                if("auto_key" in features) OutlinedButton(onOpenAutoJobs,modifier=Modifier.weight(1f)) {Text("Mobile jobs")}
                if("watch" in features) OutlinedButton(onOpenWatchJobs,modifier=Modifier.weight(1f)) {Text("Watch jobs")}
                if("shoe" in features) OutlinedButton(onOpenShoeJobs,modifier=Modifier.weight(1f)) {Text("Shoe jobs")}
            }
        }
        Box(Modifier.weight(1f)) {PeriodReportsScreen({},embedded=true)}
    }
}

@Composable
private fun LegacyDashboardScreen(
    sessionSummary: String?,
    apiBaseUrl: String,
    onLogout: () -> Unit,
    features: Set<String>,
    onNewMobileJob: () -> Unit,
    onOpenWatchJobs: () -> Unit,
    onOpenQuotes: () -> Unit,
    onOpenInvoices: () -> Unit,
    onOpenShoeJobs: () -> Unit,
    onOpenAutoJobs: () -> Unit,
    onOpenAutoJob: (String) -> Unit,
) {
    val vm: DashboardViewModel = viewModel()
    val state by vm.state.collectAsStateWithLifecycle()

    LazyColumn(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("Home", style = MaterialTheme.typography.headlineSmall)
            sessionSummary?.let {
                Card(colors = CardDefaults.cardColors()) {
                    Text(it, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyLarge)
                }
            }
            Text(
                "Your shop workspace",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = { vm.refresh() }, enabled = !state.loading) {
                    Text(if (state.loading) "Refreshing…" else "Refresh")
                }
            }
        }

        if (state.loading && state.summary == null) {
            item { CircularProgressIndicator() }
        }

        state.error?.let { msg ->
            item {
                Text(msg, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }
        }

        state.widgets?.takeIf { "watch" in features }?.let { w ->
            item {
                Text("Follow-ups", style = MaterialTheme.typography.titleMedium)
            }
            item {
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Jobs stuck 14+ days (awaiting go-ahead / parts): ${w.overdueJobsCount}")
                        TextButton(onClick = onOpenWatchJobs) { Text("Open watch jobs") }
                        HorizontalDivider()
                        Text("Quotes sent 7+ days ago (still sent): ${w.quotesPending7dCount}")
                        TextButton(onClick = onOpenQuotes) { Text("Open quotes") }
                        HorizontalDivider()
                        Text("Unpaid invoices: ${w.overdueInvoicesCount}")
                        TextButton(onClick = onOpenInvoices) { Text("Open invoices") }
                        HorizontalDivider()
                        Text("Past collection date (not collected): ${w.overdueCollectionCount}")
                        TextButton(onClick = onOpenWatchJobs) { Text("Watch jobs") }
                    }
                }
            }
        }

        state.summary?.let { s ->
            item {
                Text("Totals", style = MaterialTheme.typography.titleMedium)
            }
            item {
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Watch jobs: ${s.counts.jobs}")
                        Text("Customers: ${s.counts.customers}")
                        Text("Watches: ${s.counts.watches}")
                        Text("Quotes: ${s.counts.quotes}")
                        Text("Invoices: ${s.counts.invoices}")
                        if (s.counts.shoeJobs > 0) {
                            Text("Shoe jobs: ${s.counts.shoeJobs}")
                        }
                    }
                }
            }
            item {
                Text("Money (tenant-wide)", style = MaterialTheme.typography.titleMedium)
            }
            item {
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        val cur = "AUD"
                        Text("Billed ${formatCents(s.financials.billedCents, cur)}")
                        Text("Revenue ${formatCents(s.financials.revenueCents, cur)}")
                        Text("Cost ${formatCents(s.financials.costCents, cur)}")
                        Text("Outstanding ${formatCents(s.financials.outstandingCents, cur)}")
                        Text("Gross profit ${formatCents(s.financials.grossProfitCents, cur)} (${s.financials.grossMarginPercent}%)")
                    }
                }
            }
            item {
                Text("Operations", style = MaterialTheme.typography.titleMedium)
            }
            item {
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Work logged: ${s.operations.workMinutes} min")
                        Text("Avg revenue / watch job: ${formatCents(s.operations.avgRevenuePerJobCents, "AUD")}")
                        s.operations.avgTurnaroundDays?.let {
                            Text("Avg turnaround (days to collected): $it")
                        }
                        Text("Quote → invoice: ${s.operations.quoteToInvoicePct}%")
                        s.operations.avgQuoteResponseHours?.let {
                            Text("Avg hours to first quote sent: $it")
                        }
                    }
                }
            }
            item {
                Text("Quote funnel", style = MaterialTheme.typography.titleMedium)
            }
            item {
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text("Approval rate: ${s.salesFunnel.approvalRatePercent}%")
                        Text("Approved ${s.salesFunnel.approvedQuotes} · Sent ${s.salesFunnel.sentQuotes} · Declined ${s.salesFunnel.declinedQuotes}")
                    }
                }
            }
        }

        if("auto_key" in features) item { Button(onClick = onNewMobileJob, modifier = Modifier.fillMaxWidth()) { Text("New mobile service job") } }

        item {
            Text("Shortcuts", style = MaterialTheme.typography.titleMedium)
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if("watch" in features) OutlinedButton(onClick = onOpenWatchJobs, modifier = Modifier.weight(1f)) { Text("Watch") }
                if("shoe" in features) OutlinedButton(onClick = onOpenShoeJobs, modifier = Modifier.weight(1f)) { Text("Shoe") }
                if("auto_key" in features) OutlinedButton(onClick = onOpenAutoJobs, modifier = Modifier.weight(1f)) { Text("Mobile") }
            }
        }

        item {
            Spacer(Modifier.height(8.dp))
            Button(onClick = onLogout, modifier = Modifier.fillMaxWidth()) {
                Text("Sign out")
            }
        }
    }
}



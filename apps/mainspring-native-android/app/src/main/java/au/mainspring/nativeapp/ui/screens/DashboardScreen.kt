package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
fun DashboardScreen(
    sessionSummary: String?,
    apiBaseUrl: String,
    onLogout: () -> Unit,
    onOpenWatchJobs: () -> Unit,
    onOpenQuotes: () -> Unit,
    onOpenInvoices: () -> Unit,
    onOpenShoeJobs: () -> Unit,
    onOpenAutoJobs: () -> Unit,
    onOpenAutoJob: (String) -> Unit,
) {
    val vm: DashboardViewModel = viewModel()
    val state by vm.state.collectAsStateWithLifecycle()
    var intakeName by remember { mutableStateOf("") }
    var intakePhone by remember { mutableStateOf("") }

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
                "API $apiBaseUrl",
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

        state.widgets?.let { w ->
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

        item {
            Text("Mobile quick intake", style = MaterialTheme.typography.titleMedium)
        }
        item {
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Creates a customer (if new), mobile job in awaiting_quote, and sends the intake SMS when configured.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    OutlinedTextField(
                        value = intakeName,
                        onValueChange = { intakeName = it },
                        label = { Text("Customer name") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = intakePhone,
                        onValueChange = { intakePhone = it },
                        label = { Text("Phone") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    state.quickIntakeMessage?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall)
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(
                            onClick = {
                                vm.quickIntake(intakeName, intakePhone) { jobId ->
                                    intakeName = ""
                                    intakePhone = ""
                                    onOpenAutoJob(jobId)
                                }
                            },
                            enabled = !state.quickIntakeBusy && intakeName.isNotBlank() && intakePhone.isNotBlank(),
                        ) {
                            Text(if (state.quickIntakeBusy) "Creating…" else "Create & open job")
                        }
                        TextButton(onClick = onOpenAutoJobs) { Text("All mobile jobs") }
                    }
                }
            }
        }

        item {
            Text("Shortcuts", style = MaterialTheme.typography.titleMedium)
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onOpenWatchJobs, modifier = Modifier.weight(1f)) { Text("Watch") }
                OutlinedButton(onClick = onOpenShoeJobs, modifier = Modifier.weight(1f)) { Text("Shoe") }
                OutlinedButton(onClick = onOpenAutoJobs, modifier = Modifier.weight(1f)) { Text("Mobile") }
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

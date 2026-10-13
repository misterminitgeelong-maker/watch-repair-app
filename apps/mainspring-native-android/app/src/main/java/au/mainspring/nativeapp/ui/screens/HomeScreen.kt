package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.DashboardViewModel
import au.mainspring.nativeapp.TodayViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** What the shop can do right now. Each entry is a quick action tile. */
private data class QuickAction(val label: String, val hint: String, val onClick: () -> Unit)

/** One thing that needs the owner's attention; hidden when its count is zero. */
private data class Attention(val count: Int, val label: String, val onClick: () -> Unit)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    features: Set<String>,
    shopName: String? = null,
    onNewWatch: () -> Unit,
    onNewMobileJob: () -> Unit,
    onNewShoe: () -> Unit,
    onCounterSale: () -> Unit,
    onOpenWatchJobs: () -> Unit,
    onOpenQuotes: () -> Unit,
    onOpenInvoices: () -> Unit,
    onOpenAutoJobs: () -> Unit,
    onOpenShoeJobs: () -> Unit,
    onOpenReports: () -> Unit,
    dashboard: DashboardViewModel = viewModel(),
    today: TodayViewModel = viewModel(),
) {
    val dash by dashboard.state.collectAsStateWithLifecycle()
    val day by today.state.collectAsStateWithLifecycle()
    RefreshOnResume { dashboard.refresh(); if ("auto_key" in features) today.refresh() }
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    val zone = runCatching { ZoneId.of(TokenStore.calendarTimezone()) }.getOrDefault(ZoneId.systemDefault())
    val hour = LocalTime.now(zone).hour
    val greeting = when { hour < 12 -> "Good morning"; hour < 17 -> "Good afternoon"; else -> "Good evening" }
    val canWatch = "watch" in features
    val canMobile = "auto_key" in features
    val canShoe = "shoe" in features
    val canWork = TokenStore.canWorkJobs()
    val owner = TokenStore.canManageInvoices()

    val actions = buildList {
        if (canWatch && canWork) add(QuickAction("New watch repair", "Book a watch in", onNewWatch))
        if (canMobile && canWork) add(QuickAction("New mobile job", "Locks, keys, call-outs", onNewMobileJob))
        if (canShoe && canWork) add(QuickAction("New shoe repair", "Book a pair in", onNewShoe))
        if (canMobile) add(QuickAction("Counter sale", "Sell or quote at the counter", onCounterSale))
    }
    val attention = buildList {
        if (canMobile) {
            day.todayCount?.takeIf { it > 0 }?.let { add(Attention(it, if (it == 1) "mobile job today" else "mobile jobs today", onOpenAutoJobs)) }
            day.unscheduledCount?.takeIf { it > 0 }?.let { add(Attention(it, if (it == 1) "mobile job without a booking time" else "mobile jobs without a booking time", onOpenAutoJobs)) }
            day.unpaidCount?.takeIf { it > 0 }?.let { add(Attention(it, if (it == 1) "completed mobile job not yet paid" else "completed mobile jobs not yet paid", onOpenAutoJobs)) }
        }
        dash.widgets?.takeIf { canWatch }?.let { w ->
            if (w.overdueJobsCount > 0) add(Attention(w.overdueJobsCount, if (w.overdueJobsCount == 1) "watch repair stuck 14+ days" else "watch repairs stuck 14+ days", onOpenWatchJobs))
            if (w.quotesPending7dCount > 0) add(Attention(w.quotesPending7dCount, if (w.quotesPending7dCount == 1) "quote waiting 7+ days for an answer" else "quotes waiting 7+ days for an answer", onOpenQuotes))
            if (w.overdueInvoicesCount > 0) add(Attention(w.overdueInvoicesCount, if (w.overdueInvoicesCount == 1) "unpaid invoice" else "unpaid invoices", onOpenInvoices))
            if (w.overdueCollectionCount > 0) add(Attention(w.overdueCollectionCount, if (w.overdueCollectionCount == 1) "repair past its collection date" else "repairs past their collection date", onOpenWatchJobs))
        }
    }
    val loading = dash.loading || (canMobile && day.loading)

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Text(greeting, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(TokenStore.shopValue("name") ?: shopName ?: "Your shop", style = MaterialTheme.typography.headlineMedium)
            Text(LocalDate.now(zone).format(DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.forLanguageTag("en-AU"))), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 8.dp))
        }
        dash.error?.let { item { ErrorBanner(it, onRetry = dashboard::refresh) } }
        if (actions.isNotEmpty()) {
            item { SectionLabel("Start something") }
            items(actions.chunked(2)) { pair ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    pair.forEach { action ->
                        Surface(onClick = action.onClick, modifier = Modifier.weight(1f).heightIn(min = 88.dp), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(action.label, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                                Text(action.hint, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    if (pair.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
        item { SectionLabel("Needs your attention") }
        if (attention.isEmpty()) {
            item {
                if (loading) Text("Checking…", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                else EmptyState("You're all caught up", "Nothing is overdue or waiting on you right now.")
            }
        } else {
            items(attention) { a ->
                ListCard(a.onClick) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        Text(a.count.toString(), style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.primary)
                        Text(a.label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                        Text("›", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        dash.summary?.takeIf { owner }?.let { s ->
            item { SectionLabel("Business snapshot") }
            item {
                MetricStrip(listOf(
                    "Revenue" to formatCents(s.financials.revenueCents, currency),
                    "Outstanding" to formatCents(s.financials.outstandingCents, currency),
                ))
            }
            item { OutlinedButton(onClick = onOpenReports, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text("See full reports") } }
        }
        if (canWatch || canMobile || canShoe) {
            item { SectionLabel("Browse") }
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (canMobile) OutlinedButton(onClick = onOpenAutoJobs, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Mobile") }
                    if (canWatch) OutlinedButton(onClick = onOpenWatchJobs, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Watch") }
                    if (canShoe) OutlinedButton(onClick = onOpenShoeJobs, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Shoe") }
                }
            }
        }
    }
}

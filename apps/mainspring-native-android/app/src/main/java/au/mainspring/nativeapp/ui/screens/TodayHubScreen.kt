package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.DashboardViewModel
import au.mainspring.nativeapp.HubJob
import au.mainspring.nativeapp.JobsHubViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Atelier "Today": hero card, two key counts, what needs attention, and one dark call to action. */
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
fun TodayHubScreen(
    features: Set<String>,
    shopName: String?,
    onNewIntake: () -> Unit,
    onOpenJob: (HubJob) -> Unit,
    onViewAll: () -> Unit,
    onOpenQuotes: () -> Unit,
    onOpenInvoices: () -> Unit,
    onOpenRoute: (String) -> Unit = {},
    jobs: JobsHubViewModel = viewModel(factory = JobsHubFactory(features)),
    dashboard: DashboardViewModel = viewModel(),
) {
    val hub by jobs.state.collectAsStateWithLifecycle()
    val dash by dashboard.state.collectAsStateWithLifecycle()
    RefreshOnResume { jobs.refresh(); dashboard.refresh() }
    val zone = runCatching { ZoneId.of(TokenStore.calendarTimezone()) }.getOrDefault(ZoneId.systemDefault())
    val date = LocalDate.now(zone).format(DateTimeFormatter.ofPattern("EEEE, d MMMM", Locale.forLanguageTag("en-AU")))
    val canWork = TokenStore.canWorkJobs()
    val attention = hub.jobs.filter { it.needsAttention && it.active }.sortedBy { it.sortKey }.take(4)
    val widgets = dash.widgets
    val summary = dash.summary?.takeIf { TokenStore.canManageInvoices() }
    val calibre = LocalCalibre.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if(calibre) {
            item {
                Column {
                    if(androidx.compose.ui.platform.LocalConfiguration.current.screenWidthDp < 840) CalibreWordmark(shopName ?: TokenStore.shopValue("name"))
                    Column(Modifier.padding(horizontal = 20.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        MonoLabel(LocalDate.now(zone).format(DateTimeFormatter.ofPattern("EEEE / d MMMM", Locale.forLanguageTag("en-AU"))))
                        Row(verticalAlignment = Alignment.Top) {
                            Text("Today, at the bench.", Modifier.weight(1f), style = MaterialTheme.typography.headlineLarge)
                            if(canWork) RoundPlusButton(onNewIntake, "New intake")
                        }
                    }
                }
            }
            item {
                var q by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("") }
                Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    AtelierTextField(q, { q = it }, singleLine = true, placeholder = { Text("Search jobs, customers or references") }, modifier = Modifier.fillMaxWidth())
                    val term = q.trim()
                    if(term.isNotEmpty()) {
                        val hits = hub.jobs.filter { "${it.title} ${it.number} ${it.customer.orEmpty()}".contains(term, true) }.take(5)
                        hits.forEach { job -> HubJobCard(job, { onOpenJob(job) }) }
                        if(hits.isEmpty()) Text("No open jobs match \"$term\".", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        ListCard({ onOpenRoute("people") }) { Text("Look for \"$term\" in Customers", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary) }
                    }
                }
            }
            item {
                Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    MonoLabel("Quick actions")
                    androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        if(canWork) AtelierChip(false, onNewIntake, { Text("New intake") })
                        AtelierChip(false, { onOpenRoute("newCustomer") }, { Text("New customer") })
                        if("auto_key" in features) AtelierChip(false, { onOpenRoute("counterSale") }, { Text("Counter sale") })
                        if("auto_key" in features || "shop_mobile_booking" in features) AtelierChip(false, { onOpenRoute("bookingRequests") }, { Text("Book mobile services") })
                        AtelierChip(false, { onOpenRoute("quotes") }, { Text("Quotes") })
                        AtelierChip(false, { onOpenRoute("invoices") }, { Text("Invoices") })
                    }
                }
            }
            item {
                val recent by RecentItems.items.collectAsStateWithLifecycle()
                val resolved = recent.mapNotNull { key -> hub.jobs.firstOrNull { "${it.service}/${it.id}" == key } }.take(3)
                if(resolved.isNotEmpty()) Column(Modifier.padding(horizontal = 20.dp)) {
                    SectionLabel("Recent")
                    resolved.forEach { job -> HubJobCard(job, { onOpenJob(job) }) }
                }
            }
            if(summary != null) item { RevenueKpis(summary, Modifier.padding(horizontal = 20.dp)) }
            item { MetricStrip(listOf("On the bench" to hub.activeCount.toString(), "Mine" to hub.mineCount.toString(), "Ready to collect" to hub.readyCount.toString()), Modifier.padding(horizontal = 20.dp)) }
            item {
                val tiles = buildList {
                    if("watch" in features) add(Triple("Watch jobs", "Bench and counter", "watch_jobs"))
                    if("shoe" in features) add(Triple("Shoe jobs", "Repairs and collections", "shoe_jobs"))
                    if("auto_key" in features) { add(Triple("Mobile jobs", "On the road", "auto_jobs")); add(Triple("Dispatch", "Today's route", "dispatch")) }
                }
                if(tiles.isNotEmpty()) Column(Modifier.padding(horizontal = 20.dp)) {
                    SectionLabel("Your workspaces")
                    tiles.forEach { (title, sub, route) ->
                        ListCard({ onOpenRoute(route) }) {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                                    Text(sub, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                                }
                                Text("\u2197", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                            }
                        }
                    }
                }
            }
        } else {
        item { LargeHeader((shopName ?: TokenStore.shopValue("name") ?: "Your shop") + " · Shop workspace", "Today", onAdd = if(canWork) onNewIntake else null, addDescription = "New intake") }
            item {
                HeroCard(Modifier.padding(horizontal = 20.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(date.uppercase(), style = MaterialTheme.typography.labelSmall)
                            Text("A good day\nfor good work.", style = MaterialTheme.typography.headlineSmall)
                            Text(when(hub.readyCount) { 0 -> "Nothing waiting for collection"; 1 -> "1 customer ready to collect"; else -> "${hub.readyCount} customers ready to collect" }, style = MaterialTheme.typography.bodyMedium)
                        }
                        WatchArt()
                    }
                }
            }
            if(summary != null) item { RevenueKpis(summary, Modifier.padding(horizontal = 20.dp)) }
            item { MetricStrip(listOf("On the bench" to hub.activeCount.toString(), "Ready to collect" to hub.readyCount.toString()), Modifier.padding(horizontal = 20.dp)) }
            item {
                val tiles = buildList {
                    if("watch" in features) add(Triple("Watch jobs", "Bench and counter", "watch_jobs"))
                    if("shoe" in features) add(Triple("Shoe jobs", "Repairs", "shoe_jobs"))
                    if("auto_key" in features) { add(Triple("Mobile jobs", "On the road", "auto_jobs")); add(Triple("Dispatch", "Today's route", "dispatch")) }
                }
                if(tiles.isNotEmpty()) {
                    Text("Your workspaces", Modifier.padding(horizontal = 24.dp, vertical = 4.dp), style = MaterialTheme.typography.titleMedium)
                    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        tiles.forEach { (title, sub, route) ->
                            ListCard({ onOpenRoute(route) }, Modifier.width(172.dp)) {
                                Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                                Text(sub, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                            }
                        }
                    }
                }
            }
        }
        if(hub.error != null) item { ErrorBanner(hub.error.orEmpty(), Modifier.padding(horizontal = 20.dp), onRetry = jobs::refresh) }
        item {
            Row(Modifier.fillMaxWidth().padding(horizontal = if(calibre) 20.dp else 24.dp), verticalAlignment = Alignment.CenterVertically) {
                if(calibre) MonoLabel("Needs your attention", Modifier.weight(1f)) else Text("Needs your attention", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                TextButton(onClick = onViewAll, modifier = Modifier.heightIn(min = 44.dp)) { Text("View all", style = MaterialTheme.typography.labelLarge) }
            }
        }
        val actions = buildList {
            widgets?.let { w ->
                if(w.overdueJobsCount > 0) add(Triple("Jobs awaiting go-ahead", "${w.overdueJobsCount} waiting 14+ days", "watch_jobs"))
                if(w.overdueCollectionCount > 0) add(Triple("Jobs past collection date", "${w.overdueCollectionCount} overdue for collection", "watch_jobs"))
                if(w.quotesPending7dCount > 0) add(Triple("Quotes waiting for an answer", "${w.quotesPending7dCount} sent more than 7 days ago", "quotes"))
                if(w.overdueInvoicesCount > 0) add(Triple("Unpaid invoices", "${w.overdueInvoicesCount} outstanding", "invoices"))
            }
        }
        if(attention.isEmpty() && actions.isEmpty()) item {
            if(hub.loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp))
            else EmptyState("You're all caught up", "Nothing is overdue or waiting on you right now.")
        }
        items(attention, key = { "${it.service}/${it.id}" }) { job -> HubJobCard(job, { onOpenJob(job) }, Modifier.padding(horizontal = 20.dp)) }
        if(actions.isNotEmpty()) item {
            Column(Modifier.padding(horizontal = 20.dp)) {
                if(calibre) SectionLabel("Action needed") else Text("Action needed", style = MaterialTheme.typography.titleMedium)
            }
        }
        items(actions, key = { it.first }) { (title, detail, route) ->
            AttentionCard(title, detail) {
                when(route) { "quotes" -> onOpenQuotes(); "invoices" -> onOpenInvoices(); else -> onOpenRoute(route) }
            }
        }
        dash.inboxCount?.takeIf { it > 0 }?.let { n ->
            item { AttentionCard("Inbox", if(n == 1) "1 unread alert" else "$n unread alerts") { onOpenRoute("inbox") } }
        }
        if(canWork) item {
            PrimaryAction(onClick = onNewIntake, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).heightIn(min = 52.dp)) {
                Text("New intake", style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@Suppress("USELESS_CAST", "SENSELESS_COMPARISON")
@Composable private fun RevenueKpis(s: au.mainspring.nativeapp.api.ReportsSummaryResponse, modifier: Modifier = Modifier) {
    fun money(c: Int) = String.format(Locale.US, "$%,.2f", c / 100.0)
    val f = s.financials as au.mainspring.nativeapp.api.ReportsFinancials?
    if(f == null) return
    val approval = (s.salesFunnel as au.mainspring.nativeapp.api.SalesFunnelSummary?)?.approvalRatePercent?.toInt() ?: 0
    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        MonoLabel("Business this period")
        MetricStrip(listOf("Revenue" to money(f.revenueCents), "Gross profit" to money(f.grossProfitCents), "Approval rate" to "$approval%"))
        MetricStrip(listOf("Outstanding" to money(f.outstandingCents), "Billed" to money(f.billedCents)))
    }
}

@Composable private fun AttentionCard(title: String, detail: String, onClick: () -> Unit) {
    ListCard(onClick, Modifier.padding(horizontal = 20.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            Text("›", style = MaterialTheme.typography.titleLarge)
        }
        Text(detail, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
    }
}

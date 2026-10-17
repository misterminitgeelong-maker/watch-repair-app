package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
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
    val attentionAll = hub.jobs.filter { it.needsAttention && it.active && true }.sortedBy { it.sortKey }
    val attention = attentionAll.take(4)
    val widgets = dash.widgets
    val summary = dash.summary?.takeIf { TokenStore.canManageInvoices() }
    val calibre = LocalCalibre.current
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if(calibre) {
            item { CalibreHomeTop(shopName, hub, canWork, features, TokenStore.canManageInvoices(), TokenStore.canManageTeam(), widgets, summary, onNewIntake, onViewAll, onOpenQuotes, onOpenInvoices, onOpenRoute) }
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
                            SoftCard({ onOpenRoute(route) }, Modifier.width(172.dp)) {
                                Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                                Text(sub, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                            }
                        }
                    }
                }
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
        if(hub.error != null) item { ErrorBanner(hub.error.orEmpty(), Modifier.padding(horizontal = 20.dp), onRetry = jobs::refresh) }
        item {
            if(calibre) Box(Modifier.padding(horizontal = 20.dp)) { BlockHeader("Needs your attention", count = attentionAll.size + actions.size + (dash.inboxCount?.takeIf { it > 0 }?.let { 1 } ?: 0), onSeeAll = onViewAll, seeAllDescription = "See all jobs needing attention") }
            else Row(Modifier.fillMaxWidth().padding(horizontal = 24.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Needs your attention", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                TextButton(onClick = onViewAll, modifier = Modifier.heightIn(min = 44.dp)) { Text("View all", style = MaterialTheme.typography.labelLarge) }
            }
        }
        if(attention.isEmpty() && actions.isEmpty()) item {
            if(hub.loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp))
            else EmptyState("You're all caught up", "Nothing is overdue or waiting on you right now.", icon = "check")
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
        if(calibre) {
            item {
                val queue = hub.jobs.filter { it.active }.sortedBy { it.sortKey }.take(6)
                Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    BlockHeader("Live Service Queue", onSeeAll = onViewAll, seeAllDescription = "See all jobs")
                    if(queue.isEmpty() && !hub.loading) Text("No active jobs right now.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    queue.forEach { job -> QueueRow(job) { onOpenJob(job) } }
                }
            }
        }
        if(canWork && !calibre) item {
            PrimaryAction(onClick = onNewIntake, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).heightIn(min = 52.dp)) {
                Text("New intake", style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@Suppress("USELESS_CAST", "SENSELESS_COMPARISON")
@Composable private fun RevenueKpis(s: au.mainspring.nativeapp.api.ReportsSummaryResponse, modifier: Modifier = Modifier, showLabel: Boolean = true) {
    fun money(c: Int) = String.format(Locale.US, "$%,.2f", c / 100.0)
    val f = s.financials as au.mainspring.nativeapp.api.ReportsFinancials?
    if(f == null) return
    val approval = (s.salesFunnel as au.mainspring.nativeapp.api.SalesFunnelSummary?)?.approvalRatePercent?.toInt() ?: 0
    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if(showLabel) MonoLabel("Business this period")
        MetricStrip(listOf("Revenue" to money(f.revenueCents), "Gross profit" to money(f.grossProfitCents), "Approval rate" to "$approval%"))
        MetricStrip(listOf("Outstanding" to money(f.outstandingCents), "Billed" to money(f.billedCents)))
    }
}

@Composable private fun AttentionCard(title: String, detail: String, onClick: () -> Unit) {
    SoftCard(onClick, Modifier.padding(horizontal = 20.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            Text("›", style = MaterialTheme.typography.titleLarge)
        }
        Text(detail, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
    }
}

/** Calibre block header: title, optional count, and an optional "See all" link on the right. */
@Composable private fun BlockHeader(title: String, count: Int? = null, onSeeAll: (() -> Unit)? = null, seeAllDescription: String = "See all") {
    Row(Modifier.fillMaxWidth().heightIn(min = 44.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleMedium)
        if(count != null) { Spacer(Modifier.width(8.dp)); MonoLabel(count.toString()) }
        Spacer(Modifier.weight(1f))
        if(onSeeAll != null) TextButton(onClick = onSeeAll, modifier = Modifier.heightIn(min = 44.dp).semantics { contentDescription = seeAllDescription }) { Text("See all", style = MaterialTheme.typography.labelLarge) }
    }
}

private val HomeBorder @Composable get() = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)

@OptIn(ExperimentalMaterial3Api::class)
@Composable private fun HomeCard(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    val body: @Composable () -> Unit = { Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(6.dp), content = content) }
    if(onClick != null) Surface(onClick, modifier, color = MaterialTheme.colorScheme.surface, shape = CalibreCardShape, border = HomeBorder) { body() }
    else Surface(modifier, color = MaterialTheme.colorScheme.surface, shape = CalibreCardShape, border = HomeBorder) { body() }
}

@Composable private fun HomeTile(label: String, value: String, caption: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    HomeCard(modifier, onClick) {
        MonoLabel(label.uppercase())
        KpiNumber(value)
        Text(caption, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
    }
}

@Composable private fun QueueRow(job: HubJob, onClick: () -> Unit) {
    HomeCard(Modifier.fillMaxWidth(), onClick) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                MonoLabel(job.reference())
                Text(job.title, style = MaterialTheme.typography.titleMedium, maxLines = 1)
            }
            StatusPill(job.status)
        }
        job.dueDate?.take(10)?.takeIf { it.isNotBlank() }?.let { Text("Due ${formatShopDate(it)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

/** Calibre Home, matching the web phone view: title, one overview card, then a two-column grid of tappable tiles. */
@Suppress("USELESS_CAST", "SENSELESS_COMPARISON")
@Composable private fun CalibreHomeTop(
    shopName: String?, hub: au.mainspring.nativeapp.JobsHubState, canWork: Boolean, features: Set<String>, canMoney: Boolean, isOwner: Boolean,
    widgets: au.mainspring.nativeapp.api.DashboardWidgetsResponse?, summary: au.mainspring.nativeapp.api.ReportsSummaryResponse?,
    onNewIntake: () -> Unit, onViewAll: () -> Unit, onOpenQuotes: () -> Unit, onOpenInvoices: () -> Unit, onOpenRoute: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(Modifier.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Home", Modifier.weight(1f).semantics { heading() }, style = calibreDisplayStyle(MaterialTheme.typography.headlineLarge))
            if(canWork) PrimaryAction(onNewIntake, Modifier.semantics { contentDescription = "New intake" }) { Text("New intake") }
        }
        HomeCard(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
            MonoLabel("SHOP-WIDE OVERVIEW")
            Text("All your repairs, one place.", style = calibreDisplayStyle(MaterialTheme.typography.headlineMedium))
            Text("${hub.activeCount} active ${if(hub.activeCount == 1) "job" else "jobs"} across your service lines.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        val by = hub.jobs.filter { it.active }.groupingBy { it.service }.eachCount()
        val caption = listOfNotNull(
            "watch".takeIf { it in features }?.let { "Watch: ${by[it] ?: 0}" }, "shoe".takeIf { it in features }?.let { "Shoe: ${by[it] ?: 0}" },
            "auto_key".takeIf { "auto_key" in features }?.let { "Mobile: ${by.entries.filter { e -> e.key != "watch" && e.key != "shoe" }.sumOf { e -> e.value }}" },
        ).joinToString(" · ").ifBlank { "On the bench" }
        val revenue = (summary?.financials as au.mainspring.nativeapp.api.ReportsFinancials?)?.let { String.format(Locale.US, "$%,.0f", it.revenueCents / 100.0) }
        val tiles = buildList<@Composable (Modifier) -> Unit> {
            add { m -> HomeTile("Active jobs", hub.activeCount.toString(), caption, m, onViewAll) }
            add { m -> HomeTile("Customers", "All", "Directory and history", m) { onOpenRoute("people") } }
            add { m -> HomeTile("Quotes", (widgets?.quotesPending7dCount ?: 0).toString(), "waiting 7+ days", m, onOpenQuotes) }
            add { m -> HomeTile("Invoices", (widgets?.overdueInvoicesCount ?: 0).toString(), "overdue", m, onOpenInvoices) }
            if(canMoney) add { m -> HomeTile("Work value", revenue ?: "Reports", "Revenue this period", m) { onOpenRoute("reports") } }
            if(isOwner) add { m -> HomeTile("Team", "Manage", "Staff and roles", m) { onOpenRoute("team") } }
        }
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            tiles.chunked(2).forEach { pair ->
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Max), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    pair.forEach { t -> t(Modifier.weight(1f).fillMaxHeight()) }
                    if(pair.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
    }
}

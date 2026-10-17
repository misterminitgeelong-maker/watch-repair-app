package au.mainspring.nativeapp.ui.screens

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
    val todayIso = LocalDate.now(zone).toString()
    val dueAll = hub.jobs.filter { it.active && it.dueDate?.take(10)?.let { d -> d <= todayIso } == true }.sortedBy { it.sortKey }
    val dueToday = dueAll.take(5)
    val attentionAll = hub.jobs.filter { it.needsAttention && it.active && (!LocalCalibre.current || dueToday.none { d -> d.id == it.id }) }.sortedBy { it.sortKey }
    val attention = attentionAll.take(4)
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
                            Text("Today, at the bench.", Modifier.weight(1f), style = calibreDisplayStyle(MaterialTheme.typography.headlineLarge))
                            if(canWork) RoundPlusButton(onNewIntake, "New intake")
                        }
                    }
                }
            }
            item {
                var q by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf("") }
                Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.fillMaxWidth()) {
                        AtelierTextField("", {}, singleLine = true, readOnly = true, placeholder = { Text("Search jobs, customers or invoices") }, modifier = Modifier.fillMaxWidth())
                        Box(Modifier.matchParentSize().semantics { contentDescription = "Search jobs, customers or invoices" }.clickable(role = androidx.compose.ui.semantics.Role.Button) { onOpenRoute("search") })
                    }
                    val term = q.trim()
                    if(term.isNotEmpty()) {
                        val hits = hub.jobs.filter { "${it.title} ${it.number} ${it.customer.orEmpty()}".contains(term, true) }.take(5)
                        hits.forEach { job -> HubJobCard(job, { onOpenJob(job) }) }
                        if(hits.isEmpty()) Text("No open jobs match \"$term\".", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        ListCard({ onOpenRoute("people") }) { Text("Look for \"$term\" in Customers", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary) }
                    }
                }
            }
            item { MetricStrip(listOf("On the bench" to hub.activeCount.toString(), "Mine" to hub.mineCount.toString(), "Ready to collect" to hub.readyCount.toString()), Modifier.padding(horizontal = 20.dp), onItemClick = { onViewAll() }) }
            item {
                Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    BlockHeader("Shortcuts")
                    androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        if(canWork) AtelierChip(false, onNewIntake, { Text("New intake") })
                        AtelierChip(false, { onOpenRoute("newCustomer") }, { Text("New customer") })
                        AtelierChip(false, { onOpenRoute("customers") }, { Text("Customers") })
                        if("auto_key" in features) AtelierChip(false, { onOpenRoute("counterSale") }, { Text("Counter sale") })
                        if("auto_key" in features) AtelierChip(false, { onOpenRoute("sendBookingRequest") }, { Text("Booking request") })
                    }
                }
            }
            item {
                Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    BlockHeader("Due today", count = dueAll.size, onSeeAll = onViewAll, seeAllDescription = "See all jobs")
                    if(dueToday.isEmpty()) Text("Nothing due today.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    dueToday.forEach { job -> HubJobCard(job, { onOpenJob(job) }) }
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
            if(summary != null) item {
                Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    BlockHeader("Money", onSeeAll = { onOpenRoute("reports") }, seeAllDescription = "See all reports")
                    RevenueKpis(summary, showLabel = false)
                }
            }
            item {
                val recent by RecentItems.items.collectAsStateWithLifecycle()
                val resolved = recent.mapNotNull { key -> hub.jobs.firstOrNull { "${it.service}/${it.id}" == key } }.filter { r -> dueToday.none { it.id == r.id } }.take(3)
                if(resolved.isNotEmpty()) Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    BlockHeader("Recent")
                    resolved.forEach { job -> HubJobCard(job, { onOpenJob(job) }) }
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

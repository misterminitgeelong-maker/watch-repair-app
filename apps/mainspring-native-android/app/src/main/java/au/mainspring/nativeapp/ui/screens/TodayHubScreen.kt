package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.sp
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
    planName: String? = null,
    siteCount: Int = 1,
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
    var refreshedAt by remember { mutableLongStateOf(System.currentTimeMillis()) }
    androidx.compose.runtime.LaunchedEffect(hub.loading, dash.loading) { if(!hub.loading && !dash.loading) refreshedAt = System.currentTimeMillis() }
    LazyColumn(Modifier.fillMaxSize().testTag("home-list"), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if(calibre) {
            item { CalibreHomeTop(hub, canWork, features, TokenStore.canManageInvoices(), TokenStore.canManageTeam(), widgets, summary, planName, siteCount, dash.teamCount, refreshedAt, hub.loading || dash.loading,
                { jobs.refresh(); dashboard.refresh() }, onNewIntake, onViewAll, onOpenQuotes, onOpenInvoices, onOpenRoute, onOpenJob) }
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

/** Small bold uppercase sans caption, as on the web tiles. [spacing] widens the tracking for the overview eyebrow. */
@Composable private fun CapsLabel(text: String, modifier: Modifier = Modifier, spacing: Float = 0.6f) {
    Text(text.uppercase(), modifier, style = MaterialTheme.typography.labelMedium.copy(fontSize = 12.sp, fontWeight = FontWeight.SemiBold, letterSpacing = spacing.sp),
        color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
}

/** Web stat tile: caps label with a line icon at the right, bold sans value, muted caption. */
@Composable private fun HomeTile(label: String, value: String, caption: String, icon: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    HomeCard(modifier, onClick) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            CapsLabel(label, Modifier.weight(1f))
            ToolIcon(icon, size = 20.dp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text(value, Modifier.padding(top = 4.dp), style = MaterialTheme.typography.headlineMedium.copy(fontWeight = FontWeight.SemiBold, fontSize = 28.sp, lineHeight = 34.sp), color = MaterialTheme.colorScheme.onSurface, maxLines = 1)
        Text(caption, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
    }
}

@Composable private fun KpiCell(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier.padding(horizontal = 16.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        CapsLabel(label)
        Text(value, style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.SemiBold, fontSize = 24.sp, lineHeight = 30.sp), color = MaterialTheme.colorScheme.onSurface, maxLines = 1)
    }
}

private fun queueServiceLabel(service: String) = when(service) { "watch" -> "Watch"; "shoe" -> "Shoe"; else -> "Mobile" }

/** Web Live Service Queue: one card with a header and divided rows (SERVICE · #REF, title, date, status pill). */
@Composable private fun LiveServiceQueue(queue: List<HubJob>, loading: Boolean, onOpenWorkflow: () -> Unit, onOpenJob: (HubJob) -> Unit) {
    HomeCardFlush(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Live Service Queue", Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.SemiBold))
                Text("Newest activity across your service lines.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("OPEN WORKFLOW", Modifier.clickable(role = androidx.compose.ui.semantics.Role.Button, onClick = onOpenWorkflow).heightIn(min = 44.dp).wrapContentHeight(Alignment.CenterVertically).padding(start = 12.dp)
                .semantics { contentDescription = "See all jobs" },
                style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp), color = MaterialTheme.colorScheme.primary)
        }
        if(queue.isEmpty() && !loading) {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Text("No recent jobs yet.", Modifier.padding(18.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        queue.forEach { job ->
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth().clickable(role = androidx.compose.ui.semantics.Role.Button) { onOpenJob(job) }.padding(horizontal = 18.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    CapsLabel(queueServiceLabel(job.service) + " \u00b7 " + job.number.let { if(it.startsWith("#")) it else "#$it" }, spacing = 0.5f)
                    Text(job.title, style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium), maxLines = 2)
                    (job.createdAt.takeIf { it.isNotBlank() } ?: job.dueDate)?.let { Text(formatShopDate(it).substringBefore(' '), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
                StatusPill(job.status)
            }
        }
    }
}

@Composable private fun HomeCardFlush(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier, color = MaterialTheme.colorScheme.surface, shape = CalibreCardShape, border = HomeBorder) { Column(Modifier.fillMaxWidth(), content = content) }
}

internal data class ChecklistItem(val label: String, val done: Boolean, val route: String)

/** Launch checklist as on the web. "Set up team accounts" needs the user count, so it only appears once that is known (owners). */
internal fun launchChecklistItems(customers: Int, jobs: Int, quotesSent: Boolean, invoices: Int, teamCount: Int?): List<ChecklistItem> = buildList {
    add(ChecklistItem("Add your first customer", customers > 0, "customers"))
    add(ChecklistItem("Create a watch repair", jobs > 0, "watch_jobs"))
    add(ChecklistItem("Send a quote", quotesSent, "quotes"))
    add(ChecklistItem("Raise an invoice", invoices > 0, "invoices"))
    if(teamCount != null) add(ChecklistItem("Set up team accounts", teamCount > 1, "team"))
}

internal fun checklistProgressLabel(items: List<ChecklistItem>) = "Progress ${items.count { it.done }}/${items.size} completed"

private fun checklistKey() = "launch_checklist_dismissed_" + (TokenStore.shopValue("name") ?: "shop")
private fun checklistPrefs() = TokenStore.context()?.getSharedPreferences("mainspring_home", android.content.Context.MODE_PRIVATE)

/** Web launch checklist: progress, Dismiss (remembered per shop on this device) and Done / Next rows. */
@Composable private fun LaunchChecklist(items: List<ChecklistItem>, onOpenRoute: (String) -> Unit) {
    var dismissed by remember { mutableStateOf(runCatching { checklistPrefs()?.getBoolean(checklistKey(), false) }.getOrNull() ?: false) }
    if(dismissed) return
    HomeCard(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Launch checklist", Modifier.semantics { heading() }, style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold))
                Text(checklistProgressLabel(items), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            TextButton({ dismissed = true; runCatching { checklistPrefs()?.edit()?.putBoolean(checklistKey(), true)?.apply() } }, Modifier.heightIn(min = 44.dp), contentPadding = PaddingValues(horizontal = 8.dp)) {
                Text("Dismiss", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            }
        }
        Spacer(Modifier.height(6.dp))
        items.forEach { item ->
            val shape = androidx.compose.foundation.shape.RoundedCornerShape(10.dp)
            Surface({ onOpenRoute(item.route) }, Modifier.fillMaxWidth().padding(bottom = 8.dp), shape = shape,
                color = if(item.done) androidx.compose.ui.graphics.Color(0xFFEAF4EA) else MaterialTheme.colorScheme.background, border = HomeBorder) {
                Text(androidx.compose.ui.text.buildAnnotatedString { withStyle(androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.SemiBold)) { append(if(item.done) "Done" else "Next") }; append(" \u00b7 ${item.label}") },
                    Modifier.padding(horizontal = 14.dp, vertical = 14.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
            }
        }
    }
}

/** Calibre Home, matching the web phone view: title, refresh row, overview card with KPIs, launch checklist, stat tiles and the live queue. */
@Suppress("USELESS_CAST", "SENSELESS_COMPARISON")
@Composable private fun CalibreHomeTop(
    hub: au.mainspring.nativeapp.JobsHubState, canWork: Boolean, features: Set<String>, canMoney: Boolean, isOwner: Boolean,
    widgets: au.mainspring.nativeapp.api.DashboardWidgetsResponse?, summary: au.mainspring.nativeapp.api.ReportsSummaryResponse?,
    planName: String?, siteCount: Int, teamCount: Int?, refreshedAt: Long, refreshing: Boolean, onRefresh: () -> Unit,
    onNewIntake: () -> Unit, onViewAll: () -> Unit, onOpenQuotes: () -> Unit, onOpenInvoices: () -> Unit, onOpenRoute: (String) -> Unit, onOpenJob: (HubJob) -> Unit,
) {
    val financials = summary?.financials as au.mainspring.nativeapp.api.ReportsFinancials?
    fun money(c: Int) = String.format(Locale.US, "$%,.2f", c / 100.0)
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Column { PageTitle("Operations Dashboard") }
        Row(Modifier.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Last refreshed " + java.time.Instant.ofEpochMilli(refreshedAt).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("h:mm:ss a", Locale.US)),
                Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SecondaryAction(onRefresh, Modifier.heightIn(min = 44.dp), enabled = !refreshing, shape = androidx.compose.foundation.shape.RoundedCornerShape(6.dp)) {
                Text(if(refreshing) "Refreshing\u2026" else "Refresh now", style = MaterialTheme.typography.labelLarge)
            }
        }
        if(canWork) PrimaryAction(onNewIntake, Modifier.padding(horizontal = 20.dp).fillMaxWidth().semantics { contentDescription = "New intake" }) { Text("New intake") }
        HomeCardFlush(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
            Column(Modifier.padding(horizontal = 24.dp, vertical = 24.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CapsLabel("SHOP-WIDE OVERVIEW", spacing = 3f)
                Text("All your repairs, one place.", style = calibreDisplayStyle(MaterialTheme.typography.headlineMedium))
                Text("${hub.activeCount} active ${if(hub.activeCount == 1) "job" else "jobs"} across your service lines.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    listOfNotNull(planName?.let { it.replace('_', ' ').replaceFirstChar { c -> c.uppercase() } + " plan" }, "$siteCount ${if(siteCount == 1) "site" else "sites"} linked").forEach { chip ->
                        Text(chip, Modifier.background(MaterialTheme.colorScheme.primary.copy(alpha = 0.10f), androidx.compose.foundation.shape.CircleShape).padding(horizontal = 14.dp, vertical = 8.dp),
                            style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurface)
                    }
                }
            }
            if(financials != null) {
                val approval = ((summary?.salesFunnel as au.mainspring.nativeapp.api.SalesFunnelSummary?)?.approvalRatePercent ?: 0.0).let { if(it % 1.0 == 0.0) it.toInt().toString() else String.format(Locale.US, "%.1f", it) }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
                    KpiCell("Revenue", money(financials.revenueCents), Modifier.weight(1f)); VerticalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    KpiCell("Gross profit", money(financials.grossProfitCents), Modifier.weight(1f))
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
                    KpiCell("Approval rate", "$approval%", Modifier.weight(1f)); VerticalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    KpiCell("Avg / job", money(summary?.operations?.avgRevenuePerJobCents ?: 0), Modifier.weight(1f))
                }
            }
        }
        if(summary != null) {
            val funnel = summary.salesFunnel as au.mainspring.nativeapp.api.SalesFunnelSummary?
            LaunchChecklist(launchChecklistItems(summary.counts.customers, summary.counts.jobs, (funnel?.sentQuotes ?: 0) > 0 || summary.counts.quotes > 0, summary.counts.invoices, teamCount), onOpenRoute)
        }
        val by = hub.jobs.filter { it.active }.groupingBy { it.service }.eachCount()
        val caption = listOfNotNull(
            "watch".takeIf { it in features }?.let { "Watch: ${by[it] ?: 0}" }, "shoe".takeIf { it in features }?.let { "Shoe: ${by[it] ?: 0}" },
            "auto_key".takeIf { "auto_key" in features }?.let { "Mobile: ${by.entries.filter { e -> e.key != "watch" && e.key != "shoe" }.sumOf { e -> e.value }}" },
        ).joinToString(" \u00b7 ").ifBlank { "On the bench" }
        val revenue = financials?.let { String.format(Locale.US, "$%,.0f", it.revenueCents / 100.0) }
        val tiles = buildList<@Composable (Modifier) -> Unit> {
            add { m -> HomeTile("Active jobs", hub.activeCount.toString(), caption, "jobs", m, onViewAll) }
            add { m -> HomeTile("Customers", "All", "Directory and history", "customers", m) { onOpenRoute("people") } }
            add { m -> HomeTile("Quotes", (widgets?.quotesPending7dCount ?: 0).toString(), "waiting 7+ days", "quotes", m, onOpenQuotes) }
            add { m -> HomeTile("Invoices", (widgets?.overdueInvoicesCount ?: 0).toString(), "overdue", "invoices", m, onOpenInvoices) }
            if(canMoney) add { m -> HomeTile("Work value", revenue ?: "Reports", "Revenue this period", "money", m) { onOpenRoute("reports") } }
            if(isOwner) add { m -> HomeTile("Team", "Manage", "Staff and roles", "team", m) { onOpenRoute("team") } }
        }
        Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            tiles.chunked(2).forEach { pair ->
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Max), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    pair.forEach { t -> t(Modifier.weight(1f).fillMaxHeight()) }
                    if(pair.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
        LiveServiceQueue(hub.jobs.filter { it.active }.sortedBy { it.sortKey }.take(6), hub.loading, onViewAll, onOpenJob)
    }
}

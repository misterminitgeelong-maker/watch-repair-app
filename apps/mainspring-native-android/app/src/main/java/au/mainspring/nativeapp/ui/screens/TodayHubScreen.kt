package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
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
import au.mainspring.nativeapp.HubJob
import au.mainspring.nativeapp.JobsHubViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Atelier "Today": hero card, two key counts, what needs attention, and one dark call to action. */
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
    RefreshOnResume { jobs.refresh(); if("watch" in features) dashboard.refresh() }
    val zone = runCatching { ZoneId.of(TokenStore.calendarTimezone()) }.getOrDefault(ZoneId.systemDefault())
    val date = LocalDate.now(zone).format(DateTimeFormatter.ofPattern("EEEE, d MMMM", Locale.forLanguageTag("en-AU")))
    val canWork = TokenStore.canWorkJobs()
    val attention = hub.jobs.filter { it.needsAttention && it.active }.sortedBy { it.sortKey }.take(4)
    val widgets = dash.widgets?.takeIf { "watch" in features }
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
        if(attention.isEmpty() && widgets == null) item {
            if(hub.loading) LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp))
            else EmptyState("You're all caught up", "Nothing is overdue or waiting on you right now.")
        }
        items(attention, key = { "${it.service}/${it.id}" }) { job -> HubJobCard(job, { onOpenJob(job) }, Modifier.padding(horizontal = 20.dp)) }
        widgets?.let { w ->
            if(w.quotesPending7dCount > 0) item { AttentionCard("Quotes waiting for an answer", "${w.quotesPending7dCount} sent more than 7 days ago", onOpenQuotes) }
            if(w.overdueInvoicesCount > 0) item { AttentionCard("Unpaid invoices", "${w.overdueInvoicesCount} outstanding", onOpenInvoices) }
        }
        if(canWork) item {
            PrimaryAction(onClick = onNewIntake, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).heightIn(min = 52.dp)) {
                Text("New intake", style = MaterialTheme.typography.titleMedium)
            }
        }
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

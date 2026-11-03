package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.ui.platform.testTag
import au.mainspring.nativeapp.JOB_SORTS
import au.mainspring.nativeapp.countLabel
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.HubJob
import au.mainspring.nativeapp.JobsHubViewModel
import au.mainspring.nativeapp.ui.*
import java.time.LocalDate

/** Tab and screen name for the Jobs area: a one-service shop sees its own kind of work, not a generic "Jobs". */
internal fun jobsTabLabel(features: Set<String>): String {
    val services = listOf("watch", "shoe", "auto_key").filter { it in features }
    return if(services.size == 1 && services.single() != "auto_key") "Repairs" else "Jobs"
}

internal fun serviceLabel(service: String) = when(service) { "watch" -> "Watch"; "shoe" -> "Shoe"; else -> "Mobile" }

/** "JOB-00142 · Amelia Wright" */
internal fun HubJob.reference() = listOfNotNull(number, customer?.takeIf { it.isNotBlank() }).joinToString(" · ")

/** Blue status line, e.g. "Awaiting collection · Due today". */
internal fun HubJob.statusLine(): String {
    val today = LocalDate.now().toString()
    val due = dueDate?.take(10)?.let { d -> when { d == today -> "Due today"; d < today -> "Overdue"; else -> "Due ${formatShopDate(d)}" } }
    return listOfNotNull(statusLabel(status), if(urgent) "Urgent" else null, due).joinToString(" · ")
}

/** One Atelier job card: bold title with chevron, reference line, blue status line. */
@Composable fun HubJobCard(job: HubJob, onClick: () -> Unit, modifier: Modifier = Modifier) {
    if(LocalCalibre.current) {
        ListCard(onClick, modifier) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                JobThumb(job.service, job.id)
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(job.title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, maxLines = 1)
                        Text("›", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
                    }
                    MonoLabel(job.reference())
                    StatusLinePill(job.statusLine(), job.status, job.urgent)
                }
            }
        }
        return
    }
    ListCard(onClick, modifier) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(job.title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, maxLines = 1)
            Text("›", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
        }
        Text(job.reference(), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
        Text(job.statusLine(), style = MaterialTheme.typography.labelMedium, color = if(job.urgent) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
    }
}

fun hubJobRoute(job: HubJob) = when(job.service) { "watch" -> "watchJob/${job.id}"; "shoe" -> "shoeJob/${job.id}"; else -> "autoKeyJob/${job.id}" }

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun AtelierJobsScreen(
    features: Set<String>,
    shopName: String?,
    onOpenJob: (HubJob) -> Unit,
    onNew: () -> Unit,
    viewModel: JobsHubViewModel = viewModel(factory = JobsHubFactory(features)),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    RefreshOnResume(viewModel::refresh)
    val services = buildList {
        if("watch" in features) add("watch" to "Watch")
        if("shoe" in features) add("shoe" to "Shoe")
        if("auto_key" in features) add("auto_key" to "Mobile")
    }
    val shown = state.visible
    var filtersOpen by remember { mutableStateOf(false) }
    val today = LocalDate.now().toString()
    val dueToday = shown.filter { it.dueDate?.take(10)?.let { d -> d <= today } == true }
    val rest = shown - dueToday.toSet()
    val filterCount = (if(state.sort != "default") 1 else 0) + (if(state.service != "all") 1 else 0)
    Box(Modifier.fillMaxSize()) {
    au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) { LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Column(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                ServiceTitle("All jobs", Modifier.padding(top = 8.dp))
                SegmentedPills(listOf("active" to "Active ${state.activeCount}", "mine" to "Mine ${state.mineCount}", "ready" to "Ready ${state.readyCount}"), state.segment, viewModel::setSegment)
                SearchFiltersRow(state.query, viewModel::setQuery, "Job, customer or reference", { filtersOpen = true }, filterCount)
            }
        }
        if(state.loading && state.jobs.isEmpty()) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) }
        state.error?.let { item { ErrorBanner(it, Modifier.padding(horizontal = 16.dp), onRetry = viewModel::refresh) } }
        if(!state.loading && state.error == null && shown.isEmpty()) item {
            EmptyState(if(state.query.isNotBlank()) "Nothing matches that search" else "No jobs here yet", "Try another filter, or start a new intake with the New Job button.")
        }
        if(dueToday.isNotEmpty()) item { Text("DUE TODAY", Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(dueToday, key = { "${it.service}/${it.id}" }) { job -> HubJobCard(job, { onOpenJob(job) }, Modifier.padding(horizontal = 16.dp)) }
        if(rest.isNotEmpty() && dueToday.isNotEmpty()) item { Text("LATER", Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(rest, key = { "${it.service}/${it.id}" }) { job -> HubJobCard(job, { onOpenJob(job) }, Modifier.padding(horizontal = 16.dp)) }
    } }
    NewJobFab(onNew, Modifier.align(Alignment.BottomEnd).padding(end = 16.dp, bottom = 16.dp))
    }
    if(filtersOpen) FiltersSheet(onDismiss = { filtersOpen = false }, onReset = { viewModel.setSort("default"); viewModel.setService("all") }) {
        Text(countLabel(shown.size, "job"), Modifier.testTag("jobs-count"), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        FilterSection("Sort by") { JOB_SORTS.forEach { (key, label) -> SheetChip(label, state.sort == key, { viewModel.setSort(key) }, "jobs-sort-$key") } }
        if(services.size > 1) FilterSection("Service") { (listOf("all" to "All") + services).forEach { (key, label) -> SheetChip(label, state.service == key, { viewModel.setService(key) }) } }
    }
}

class JobsHubFactory(private val features: Set<String>) : androidx.lifecycle.ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T =
        JobsHubViewModel(features.intersect(setOf("watch", "shoe", "auto_key"))) as T
}

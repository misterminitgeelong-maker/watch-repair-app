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

/** "13 jobs" on the left, a compact Sort menu on the right. */
@Composable private fun JobsCountSortRow(count: Int, sort: String, onSort: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(start = 20.dp, end = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(countLabel(count, "job"), Modifier.weight(1f).testTag("jobs-count"), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box {
            TextButton({ open = true }, Modifier.heightIn(min = 48.dp).testTag("jobs-sort")) { Text("Sort: " + (JOB_SORTS.firstOrNull { it.first == sort }?.second ?: "Default") + " ▾") }
            DropdownMenu(open, { open = false }) {
                JOB_SORTS.forEach { (key, label) -> DropdownMenuItem({ Text(label) }, { onSort(key); open = false }, Modifier.testTag("jobs-sort-$key")) }
            }
        }
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
    au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) { LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { LargeHeader((shopName ?: "Your shop") + (if(services.size == 1) " \u00b7 " + services.single().second else " \u00b7 All services"), jobsTabLabel(features), onAdd = onNew, addDescription = "New job") }
        stickyHeader(key = "filters", contentType = "filters") {
            Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background).padding(top = 4.dp, bottom = 4.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            au.mainspring.nativeapp.ui.AtelierTextField(state.query, viewModel::setQuery, singleLine = true, placeholder = { Text("Job, customer or reference") },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp), shape = MaterialTheme.shapes.small,
                colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.surface, focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent, focusedBorderColor = MaterialTheme.colorScheme.primary),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search))
            SegmentedPills(listOf("active" to "Active ${state.activeCount}", "mine" to "Mine ${state.mineCount}", "ready" to "Ready ${state.readyCount}"),
                state.segment, viewModel::setSegment, Modifier.padding(horizontal = 20.dp))
            if(services.size > 1) SegmentedPills(listOf("all" to "All") + services, state.service, viewModel::setService, Modifier.padding(horizontal = 20.dp))
            JobsCountSortRow(shown.size, state.sort, viewModel::setSort)
            }
        }
        if(state.loading && state.jobs.isEmpty()) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        state.error?.let { item { ErrorBanner(it, Modifier.padding(horizontal = 20.dp), onRetry = viewModel::refresh) } }
        if(!state.loading && state.error == null && shown.isEmpty()) item {
            EmptyState(if(state.query.isNotBlank()) "Nothing matches that search" else "No jobs here yet", "Try another filter, or start a new intake with the + button.")
        }
        val today = LocalDate.now().toString()
        val dueToday = shown.filter { it.dueDate?.take(10)?.let { d -> d <= today } == true }
        val rest = shown - dueToday.toSet()
        if(dueToday.isNotEmpty()) item { Text("DUE TODAY", Modifier.padding(horizontal = 24.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(dueToday, key = { "${it.service}/${it.id}" }) { job -> HubJobCard(job, { onOpenJob(job) }, Modifier.padding(horizontal = 20.dp)) }
        if(rest.isNotEmpty() && dueToday.isNotEmpty()) item { Text("LATER", Modifier.padding(horizontal = 24.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(rest, key = { "${it.service}/${it.id}" }) { job -> HubJobCard(job, { onOpenJob(job) }, Modifier.padding(horizontal = 20.dp)) }
    } }
}

class JobsHubFactory(private val features: Set<String>) : androidx.lifecycle.ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T =
        JobsHubViewModel(features.intersect(setOf("watch", "shoe", "auto_key"))) as T
}

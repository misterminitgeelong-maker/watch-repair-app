package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.launch
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CatalogueViewModel
import au.mainspring.nativeapp.JobSort
import au.mainspring.nativeapp.JobsViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.WATCH_PICKER_STATUSES
import au.mainspring.nativeapp.isWatchCompleted
import au.mainspring.nativeapp.ui.JobThumb
import au.mainspring.nativeapp.ui.SecondaryAction
import au.mainspring.nativeapp.ui.formatCents
import au.mainspring.nativeapp.watchStatusLabel

/** CSV of the loaded watch jobs for the Export CSV button. */
internal fun watchJobsCsv(jobs: List<au.mainspring.nativeapp.api.RepairJobRead>, currency: String): String {
    fun q(v: String?): String = "\"" + (v ?: "").replace("\"", "\"\"") + "\""
    val rows = jobs.map { j -> listOf(j.jobNumber, j.title, j.customerName, j.customerPhone, j.customerEmail, listOfNotNull(j.watchBrand, j.watchModel).joinToString(" "),
        watchStatusLabel(j.status), j.priority, j.preQuoteCents.takeIf { it > 0 }?.let { formatCents(it, currency) }, j.createdAt).joinToString(",") { q(it) } }
    return (listOf(listOf("Job", "Title", "Customer", "Phone", "Email", "Watch", "Status", "Priority", "Quote", "Created").joinToString(",") { q(it) }) + rows).joinToString("\r\n") + "\r\n"
}

private val URGENT_STATUSES = setOf("no_go", "failed_job", "job_delayed", "declined", "overdue", "urgent")

/**
 * Watch service screen, top to bottom like the web: title, Board | List (+ Queue), one primary button, Jobs | Catalogue,
 * Active | Completed, search + Filters, the list or board, and a floating "New Job" button.
 * [onOpenQueue] shows the Queue button (the repair queue) when given.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun JobsScreen(
    onOpenJob: (String) -> Unit,
    onNewJob: () -> Unit,
    onOpenQueue: (() -> Unit)? = null,
    viewModel: JobsViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, viewModel) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) viewModel.refresh()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    LaunchedEffect(state.visibleJobs) { au.mainspring.nativeapp.JobNavContext.set("watch", state.visibleJobs.map { it.id }) }
    var tab by rememberSaveable { mutableStateOf("jobs") }
    var filtersOpen by remember { mutableStateOf(false) }
    val currency = TokenStore.shopValue("currency") ?: "AUD"

    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    var exportInfo by remember { mutableStateOf<String?>(null) }
    var deleting by remember { mutableStateOf<au.mainspring.nativeapp.api.RepairJobRead?>(null) }
    val csvSaver = androidx.activity.compose.rememberLauncherForActivityResult(androidx.activity.result.contract.ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        if (uri != null) scope.launch {
            exportInfo = try { au.mainspring.nativeapp.saveReportExport(context, uri, watchJobsCsv(state.jobs, currency).toByteArray(Charsets.UTF_8)); "CSV saved (${state.jobs.size} jobs)." }
            catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) { e.message ?: "Could not save the CSV." }
        }
    }
    val canDelete = TokenStore.canManageInvoices()
    val muted = androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant

    val header: @Composable () -> Unit = {
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ServiceTitle("Watch Repairs", Modifier.padding(top = 8.dp))
            androidx.compose.foundation.layout.FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                TextToggle(listOf(ToggleOption("board", "Board", "view-board"), ToggleOption("list", "List", "view-list")),
                    if (state.board) "board" else "list", { viewModel.setBoard(it == "board") })
                if (onOpenQueue != null) IconLabelButton("queue", "Queue", onOpenQueue)
                IconLabelButton("download", "Export CSV", { csvSaver.launch("watch-repairs.csv") }, Modifier.testTag("export-csv"), enabled = state.jobs.isNotEmpty())
            }
            exportInfo?.let { Text(it, style = androidx.compose.material3.MaterialTheme.typography.bodySmall, color = muted) }
            NewTicketButton("New Job Ticket", onNewJob, fullWidth = false)
            Text("Movement services, batteries, pressure testing, and full servicing.", style = androidx.compose.material3.MaterialTheme.typography.bodyLarge, color = muted)
            SandSegmented(listOf(ToggleOption("jobs", "Jobs", "tab-jobs"), ToggleOption("catalogue", "Catalogue", "tab-catalogue")), tab, { tab = it })
            if (tab == "jobs") {
                SandSegmented(listOf(ToggleOption("active", "Active (${state.activeCount})", "segment-active"), ToggleOption("completed", "Completed (${state.completedCount})", "segment-completed")),
                    if (state.showCompleted) "completed" else "active", { viewModel.setShowCompleted(it == "completed") })
                SearchFiltersRow(state.query, viewModel::setQuery, "Search jobs…", { filtersOpen = true }, state.activeFilterCount, onSearch = viewModel::refresh)
                if (state.loading && state.jobs.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = { viewModel.refresh() }) }
                if (!state.loading && state.error == null) Text(
                    if (state.canLoadMore) "Showing the first ${state.jobs.size} jobs for this filter." else "All matching jobs are loaded for this filter (${state.jobs.size} rows).",
                    style = androidx.compose.material3.MaterialTheme.typography.bodySmall, color = muted, modifier = Modifier.testTag("jobs-loaded-note"))
                if (!state.loading && state.error == null && state.visibleJobs.isEmpty()) {
                    au.mainspring.nativeapp.ui.EmptyState("No repairs found", "Try a different search or filter, or start a new repair.")
                }
            }
        }
    }

    Box(Modifier.fillMaxSize()) {
        if (tab == "catalogue") {
            val catalogue: CatalogueViewModel = viewModel()
            val catalogueState by catalogue.state.collectAsStateWithLifecycle()
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                item { header() }
                catalogueBody(catalogueState, catalogue)
            }
        } else if (state.board) {
            au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    header()
                    val order = WATCH_PICKER_STATUSES.filter { isWatchCompleted(it) == state.showCompleted }
                    val cards = state.visibleJobs.map { j -> BoardCard(j.id, j.title, listOfNotNull(j.jobNumber, j.customerName?.takeIf { n -> n.isNotBlank() }).joinToString(" · "), j.status,
                        number = j.jobNumber, brand = listOfNotNull(j.watchBrand, j.watchModel).joinToString(" "), days = "${au.mainspring.nativeapp.daysInShop(j.createdAt)}d",
                        description = j.description, customerLine = listOfNotNull(j.customerName?.takeIf { n -> n.isNotBlank() }, j.customerPhone?.takeIf { n -> n.isNotBlank() }).joinToString(" "),
                        assignee = state.users.firstOrNull { u -> u.id == j.assignedUserId }?.name ?: j.claimedByName, price = j.preQuoteCents.takeIf { c -> c > 0 }?.let { c -> formatCents(c, currency) }) }
                    JobsBoard(buildBoardColumns(cards, order, ::watchStatusLabel), WATCH_PICKER_STATUSES.map { it to watchStatusLabel(it) },
                        canMove = TokenStore.canWorkJobs() && state.movingId == null, onOpen = onOpenJob, onMove = viewModel::moveJob, fillHeight = false, web = true)
                }
            }
        } else {
            au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item { header() }
                    items(state.visibleJobs, key = { it.id }) { job ->
                        ServiceJobCard({ onOpenJob(job.id) }, "#${job.jobNumber}", job.title, job.customerName, au.mainspring.nativeapp.ui.statusLabel(job.status), job.status,
                            shortDaysInShop(au.mainspring.nativeapp.daysInShop(job.createdAt)),
                            job.preQuoteCents.takeIf { it > 0 }?.let { "Quote ${formatCents(it, currency)}" },
                            thumb = { JobThumb("watch", job.id, size = 56.dp) }, urgent = job.status in URGENT_STATUSES,
                            modifier = Modifier.padding(horizontal = 16.dp), onDelete = if (canDelete) ({ deleting = job }) else null)
                    }
                    if (state.canLoadMore) item {
                        SecondaryAction(viewModel::loadMore, Modifier.padding(horizontal = 16.dp).fillMaxWidth(), enabled = !state.loading) { Text("Load more repairs") }
                    }
                }
            }
        }
        NewJobFab(onNewJob, Modifier.align(Alignment.BottomEnd).padding(end = 16.dp, bottom = 16.dp))
    }

    deleting?.let { job ->
        DeleteJobDialog("${job.jobNumber} · ${job.title}", { deleting = null; viewModel.deleteJob(job.id) }, { deleting = null })
    }
    if (filtersOpen) {
        val me = TokenStore.currentUserId()
        FiltersSheet(onDismiss = { filtersOpen = false }, onReset = {
            viewModel.setSort(JobSort.NEWEST); viewModel.filterMinDays(null); viewModel.filterStatus(null); viewModel.filterTechnician(null)
        }) {
            FilterSection("Status") {
                SheetChip("All", state.statusFilter == null, { viewModel.filterStatus(null) })
                WATCH_PICKER_STATUSES.forEach { s -> SheetChip(watchStatusLabel(s), state.statusFilter == s, { viewModel.filterStatus(s) }) }
            }
            FilterSection("Sort by") { JobSort.values().forEach { s -> SheetChip(s.label, state.sort == s, { viewModel.setSort(s) }, "sort-${s.name}") } }
            FilterSection("Days in shop") {
                listOf<Int?>(null, 7, 14, 21).forEach { d -> SheetChip(if (d == null) "Any age" else "$d+ days", state.minDaysInShop == d, { viewModel.filterMinDays(d) }) }
            }
            FilterSection("Technician") {
                SheetChip("All technicians", state.technicianId == null, { viewModel.filterTechnician(null) })
                state.users.forEach { u -> SheetChip(if (u.id == me) "Mine" else u.name, state.technicianId == u.id, { viewModel.filterTechnician(u.id) }) }
            }
            Text("Saved views", style = androidx.compose.material3.MaterialTheme.typography.labelLarge, color = androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant)
            au.mainspring.nativeapp.ui.SavedViewsRow(state.savedViews, viewModel::currentView, viewModel::applyView, viewModel::saveView, viewModel::deleteView, Modifier.padding(horizontal = 0.dp))
        }
    }
}

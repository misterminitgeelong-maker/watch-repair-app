package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.SHOE_ACTIVE_STATUSES
import au.mainspring.nativeapp.SHOE_CLOSED_STATUSES
import au.mainspring.nativeapp.ShoeJobsViewModel
import au.mainspring.nativeapp.ShoeServicesViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.JobThumb
import au.mainspring.nativeapp.ui.SecondaryAction
import au.mainspring.nativeapp.ui.formatCents
import au.mainspring.nativeapp.ui.statusLabel

private val SHOE_URGENT_STATUSES = setOf("no_go", "failed_job", "job_delayed", "declined", "overdue", "urgent")

/** Shoe service screen: same structure as the watch screen (title, Board | List, primary button, Jobs | Catalogue, Active | Completed, search + Filters). */
@Composable
fun ShoeJobsScreen(
    onBack: () -> Unit,
    onOpenJob: (String) -> Unit,
    onNewJob: () -> Unit,
    viewModel: ShoeJobsViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    au.mainspring.nativeapp.ui.RefreshOnResume(viewModel::refresh)
    var tab by rememberSaveable { mutableStateOf("jobs") }
    var filtersOpen by remember { mutableStateOf(false) }
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    val rows = state.visible
    LaunchedEffect(rows) { au.mainspring.nativeapp.JobNavContext.set("shoe", rows.map { it.id }) }

    val header: @Composable () -> Unit = {
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ServiceTitle("Shoe repairs", Modifier.padding(top = 8.dp))
            if (tab == "jobs") Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                TextToggle(listOf(ToggleOption("board", "Board", "view-board"), ToggleOption("list", "List", "view-list")),
                    if (state.board) "board" else "list", { viewModel.setBoard(it == "board") })
            }
            NewTicketButton("New Job Ticket", onNewJob)
            UnderlineTabs(listOf(ToggleOption("jobs", "Jobs", "tab-jobs"), ToggleOption("catalogue", "Catalogue", "tab-catalogue")), tab, { tab = it })
            if (tab == "jobs") {
                TextToggle(listOf(ToggleOption("active", "Active (${state.activeCount})", "segment-active"), ToggleOption("completed", "Completed (${state.completedCount})", "segment-completed")),
                    if (state.showCompleted) "completed" else "active", { viewModel.setShowCompleted(it == "completed") })
                SearchFiltersRow(state.query, viewModel::setQuery, "Search jobs…", { filtersOpen = true }, if (state.statusFilter != "all") 1 else 0)
                if (state.loading && state.jobs.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = { viewModel.refresh() }) }
                if (!state.loading && state.error == null && state.jobs.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No shoe repairs yet", "Tap New Job to book in a pair.")
                if (!state.loading && state.error == null && state.jobs.isNotEmpty() && rows.isEmpty() && !state.board) au.mainspring.nativeapp.ui.EmptyState("No repairs match", "Try a different search or filter.")
            }
        }
    }

    Box(Modifier.fillMaxSize()) {
        if (tab == "catalogue") {
            val services: ShoeServicesViewModel = viewModel()
            val servicesState by services.state.collectAsStateWithLifecycle()
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                item { header() }
                shoeServicesBody(servicesState, services)
            }
        } else if (state.board) {
            au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    header()
                    val order = SHOE_ACTIVE_STATUSES + SHOE_CLOSED_STATUSES
                    val cards = state.boardJobs.map { BoardCard(it.id, it.title, listOfNotNull(it.jobNumber, state.customerName(it)).joinToString(" · "), it.status) }
                    JobsBoard(buildBoardColumns(cards, order, { s -> statusLabel(s) }), au.mainspring.nativeapp.SHOE_JOB_STATUS_OPTIONS.map { it to statusLabel(it) },
                        canMove = TokenStore.canWorkJobs() && state.movingId == null, onOpen = onOpenJob, onMove = viewModel::moveJob, fillHeight = false)
                }
            }
        } else {
            au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item { header() }
                    items(rows, key = { it.id }) { j ->
                        ServiceJobCard({ onOpenJob(j.id) }, j.jobNumber, j.title, state.customerName(j), statusLabel(j.status), j.status,
                            shortDaysInShop(au.mainspring.nativeapp.daysInShop(j.createdAt)),
                            j.costCents.takeIf { it > 0 }?.let { "Quote ${formatCents(it, currency)}" },
                            thumb = { JobThumb("shoe", j.id, size = 56.dp) }, urgent = j.status in SHOE_URGENT_STATUSES,
                            modifier = Modifier.padding(horizontal = 16.dp))
                    }
                    if (state.canLoadMore) item {
                        SecondaryAction(viewModel::loadMore, Modifier.padding(horizontal = 16.dp).fillMaxWidth(), enabled = !state.loading) { Text("Load more repairs") }
                    }
                }
            }
        }
        NewJobFab(onNewJob, Modifier.align(Alignment.BottomEnd).padding(end = 16.dp, bottom = 16.dp))
    }

    if (filtersOpen) {
        FiltersSheet(onDismiss = { filtersOpen = false }, onReset = { viewModel.setStatusFilter("all") }) {
            FilterSection("Status") {
                SheetChip("All", state.statusFilter == "all", { viewModel.setStatusFilter("all") })
                (if (state.showCompleted) SHOE_CLOSED_STATUSES else SHOE_ACTIVE_STATUSES).forEach { s ->
                    SheetChip(statusLabel(s), state.statusFilter == s, { viewModel.setStatusFilter(s) })
                }
            }
            Text("Saved views", style = androidx.compose.material3.MaterialTheme.typography.labelLarge, color = androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant)
            au.mainspring.nativeapp.ui.SavedViewsRow(state.savedViews, viewModel::currentView, viewModel::applyView, viewModel::saveView, viewModel::deleteView)
        }
    }
}

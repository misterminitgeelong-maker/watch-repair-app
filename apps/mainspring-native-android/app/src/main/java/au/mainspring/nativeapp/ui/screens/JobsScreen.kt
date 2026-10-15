package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.OutlinedTextField
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.DisposableEffect
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.JobSort
import au.mainspring.nativeapp.JobsViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.WATCH_PICKER_STATUSES
import au.mainspring.nativeapp.watchStatusLabel

@Composable
fun JobsScreen(
    onOpenJob: (String) -> Unit,
    onNewJob: () -> Unit,
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

    androidx.compose.foundation.layout.Box(Modifier.fillMaxSize()) {
    Column(Modifier.fillMaxSize()) {
        au.mainspring.nativeapp.ui.AtelierTextField(value = state.query, onValueChange = viewModel::setQuery,
            label = { Text("Search jobs or customers") }, singleLine = true,
            keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Search),
            keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSearch = { viewModel.refresh() }),
            modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp))
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            (listOf<String?>(null) + WATCH_PICKER_STATUSES).forEach { status ->
                au.mainspring.nativeapp.ui.TabChip(selected = state.statusFilter == status, onClick = { viewModel.filterStatus(status) },
                    label = { Text(status?.let { watchStatusLabel(it) } ?: "All") })
            }
        }
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            JobSort.values().forEach { sort ->
                au.mainspring.nativeapp.ui.TabChip(selected = state.sort == sort, onClick = { viewModel.setSort(sort) }, label = { Text(sort.label) })
            }
        }
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf<Int?>(null, 7, 14, 21).forEach { days ->
                au.mainspring.nativeapp.ui.TabChip(selected = state.minDaysInShop == days, onClick = { viewModel.filterMinDays(days) },
                    label = { Text(if (days == null) "Any age" else "$days+ days") })
            }
            val me = TokenStore.currentUserId()
            au.mainspring.nativeapp.ui.TabChip(selected = state.technicianId == null, onClick = { viewModel.filterTechnician(null) }, label = { Text("All technicians") })
            state.users.forEach { u ->
                au.mainspring.nativeapp.ui.TabChip(selected = state.technicianId == u.id, onClick = { viewModel.filterTechnician(u.id) },
                    label = { Text(if (u.id == me) "Mine" else u.name) })
            }
        }
        if (state.loading && state.jobs.isEmpty()) {
            androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
        }
        state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp, vertical = 8.dp), onRetry = { viewModel.refresh() }) }
        if (!state.loading && state.error == null && state.visibleJobs.isEmpty()) {
            au.mainspring.nativeapp.ui.EmptyState("No repairs found", "Try a different search or filter, or start a new repair.")
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            au.mainspring.nativeapp.ui.TabChip(selected = !state.board, onClick = { viewModel.setBoard(false) }, label = { Text("List") }, modifier = Modifier.testTag("view-list"))
            au.mainspring.nativeapp.ui.TabChip(selected = state.board, onClick = { viewModel.setBoard(true) }, label = { Text("Board") }, modifier = Modifier.testTag("view-board"))
        }
        if (state.board) {
            val cards = state.visibleJobs.map { BoardCard(it.id, it.title, listOfNotNull(it.jobNumber, it.customerName?.takeIf { n -> n.isNotBlank() }).joinToString(" · "), it.status) }
            JobsBoard(buildBoardColumns(cards, WATCH_PICKER_STATUSES, ::watchStatusLabel), WATCH_PICKER_STATUSES.map { it to watchStatusLabel(it) },
                canMove = TokenStore.canWorkJobs() && state.movingId == null, onOpen = onOpenJob, onMove = viewModel::moveJob,
                modifier = Modifier.fillMaxSize().weight(1f, fill = true))
        } else
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(if(au.mainspring.nativeapp.ui.LocalCalibre.current) 0.dp else 8.dp),
            modifier = Modifier.fillMaxSize().weight(1f, fill = true),
        ) {
            items(state.visibleJobs, key = { it.id }) { job ->
                if(au.mainspring.nativeapp.ui.LocalCalibre.current) {
                    CalibreRow({ onOpenJob(job.id) }, job.title, listOfNotNull(job.jobNumber, job.customerName?.takeIf { it.isNotBlank() }).joinToString(" · "),
                        au.mainspring.nativeapp.ui.statusLabel(job.status), job.status in setOf("no_go", "failed_job", "job_delayed", "declined", "overdue", "urgent"))
                    return@items
                }
                androidx.compose.material3.Surface(Modifier.fillMaxWidth().clickable(role = androidx.compose.ui.semantics.Role.Button) { onOpenJob(job.id) },
                    color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
                    Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(job.jobNumber, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            au.mainspring.nativeapp.ui.StatusPill(job.status)
                        }
                        Text(job.title, style = MaterialTheme.typography.titleMedium)
                        job.customerName?.let { n ->
                            Text(n, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            if(state.canLoadMore) item {
                if(au.mainspring.nativeapp.ui.LocalCalibre.current) LinkAction(onClick = viewModel::loadMore, enabled = !state.loading) { Text("Load more repairs") } else
                androidx.compose.material3.OutlinedButton(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text("Load more repairs") }
            }
        }
    }
    }
}

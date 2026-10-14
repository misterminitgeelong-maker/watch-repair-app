package au.mainspring.nativeapp.ui.screens

import androidx.compose.material3.*
import androidx.compose.foundation.layout.*
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ShoeJobsViewModel
import au.mainspring.nativeapp.SHOE_ACTIVE_STATUSES
import au.mainspring.nativeapp.SHOE_CLOSED_STATUSES
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShoeJobsScreen(
    onBack: () -> Unit,
    onOpenJob: (String) -> Unit,
    onNewJob: () -> Unit,
    viewModel: ShoeJobsViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    au.mainspring.nativeapp.ui.RefreshOnResume(viewModel::refresh)
    Scaffold(
        topBar = {
            au.mainspring.nativeapp.ui.AtelierTopAppBar(
                title = { Text("Shoe repairs") },
                navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
                actions = {
                    TextButton(onClick = { viewModel.refresh() }, enabled = !state.loading, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") }
                    au.mainspring.nativeapp.ui.RoundPlusButton(onNewJob, "New repair", Modifier.padding(end = 12.dp))
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            if (state.loading && state.jobs.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(16.dp), onRetry = { viewModel.refresh() }) }
            if (!state.loading && state.error == null && state.jobs.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No shoe repairs yet", "Tap New repair to book in a pair.")
            val horizontal = if(au.mainspring.nativeapp.ui.LocalCalibre.current) 20.dp else 16.dp
            au.mainspring.nativeapp.ui.AtelierTextField(
                value = state.query, onValueChange = viewModel::setQuery,
                label = { Text("Search job, customer or service") },
                modifier = Modifier.fillMaxWidth().padding(start = horizontal, end = horizontal, top = 8.dp), singleLine = true,
            )
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = horizontal, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                au.mainspring.nativeapp.ui.AtelierChip(!state.showCompleted, { viewModel.setShowCompleted(false) }, label = { Text("Active (${state.activeCount})") })
                au.mainspring.nativeapp.ui.AtelierChip(state.showCompleted, { viewModel.setShowCompleted(true) }, label = { Text("Completed (${state.completedCount})") })
            }
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = horizontal), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                au.mainspring.nativeapp.ui.AtelierChip(state.statusFilter == "all", { viewModel.setStatusFilter("all") }, label = { Text("All") })
                (if(state.showCompleted) SHOE_CLOSED_STATUSES else SHOE_ACTIVE_STATUSES).forEach { s ->
                    au.mainspring.nativeapp.ui.AtelierChip(state.statusFilter == s, { viewModel.setStatusFilter(s) }, label = { Text(au.mainspring.nativeapp.ui.statusLabel(s)) })
                }
            }
            val rows = state.visible
            if(!state.loading && state.error == null && state.jobs.isNotEmpty() && rows.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No repairs match", "Try a different search or filter.")
            LazyColumn(
                contentPadding = PaddingValues(start = if(au.mainspring.nativeapp.ui.LocalCalibre.current) 20.dp else 16.dp, end = if(au.mainspring.nativeapp.ui.LocalCalibre.current) 20.dp else 16.dp, top = 12.dp, bottom = 96.dp),
                verticalArrangement = Arrangement.spacedBy(if(au.mainspring.nativeapp.ui.LocalCalibre.current) 0.dp else 8.dp),
                modifier = Modifier.fillMaxSize().weight(1f, fill = true),
            ) {
                items(rows, key = { it.id }) { j ->
                    if(au.mainspring.nativeapp.ui.LocalCalibre.current) {
                        CalibreRow({ onOpenJob(j.id) }, j.title, listOfNotNull(j.jobNumber, state.customerName(j)).joinToString(" · "), au.mainspring.nativeapp.ui.statusLabel(j.status), j.status in setOf("no_go", "failed_job", "job_delayed", "declined", "overdue", "urgent"))
                        return@items
                    }
                    au.mainspring.nativeapp.ui.ListCard({ onOpenJob(j.id) }) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(j.jobNumber, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            au.mainspring.nativeapp.ui.StatusPill(j.status)
                        }
                        Text(j.title, style = MaterialTheme.typography.titleMedium)
                        state.customerName(j)?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
                if(state.canLoadMore) item {
                    if(au.mainspring.nativeapp.ui.LocalCalibre.current) LinkAction(onClick = viewModel::loadMore, enabled = !state.loading) { Text("Load more repairs") }
                    else OutlinedButton(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text("Load more repairs") }
                }
            }
        }
    }
}

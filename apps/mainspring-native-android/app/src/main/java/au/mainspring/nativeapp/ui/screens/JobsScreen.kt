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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.JobsViewModel

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

    Column(
        Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Button(onClick = onNewJob) { Text("New repair") }
            Button(onClick = { viewModel.refresh() }, enabled = !state.loading) { Text("Refresh") }
        }
        OutlinedTextField(value = state.query, onValueChange = viewModel::setQuery,
            label = { Text("Search jobs or customers") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp))
        Button(onClick = { viewModel.refresh() }, enabled = !state.loading) { Text("Search") }
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(null, "awaiting_quote", "working_on", "awaiting_collection", "collected").forEach { status ->
                FilterChip(selected = state.statusFilter == status, onClick = { viewModel.filterStatus(status) },
                    label = { Text(status?.replace('_', ' ') ?: "All") })
            }
        }
        if (!state.loading && state.error == null && state.jobs.isEmpty()) Text("No matching repairs. Start a new repair or change your search.", Modifier.padding(16.dp))
        if (state.loading && state.jobs.isEmpty()) {
            CircularProgressIndicator(Modifier.padding(24.dp))
        }
        state.error?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(16.dp),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        LazyColumn(
            contentPadding = PaddingValues(bottom = 88.dp),
            modifier = Modifier
                .fillMaxSize()
                .weight(1f, fill = true),
        ) {
            items(state.jobs, key = { it.id }) { job ->
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clickable { onOpenJob(job.id) }
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                ) {
                    Text("${job.jobNumber} · ${job.status}", style = MaterialTheme.typography.titleMedium)
                    Text(job.title, style = MaterialTheme.typography.bodyMedium)
                    job.customerName?.let { n ->
                        Text(n, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                HorizontalDivider()
            }
            if(state.canLoadMore) item {
                Button(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth().padding(16.dp)) { Text("Load more repairs") }
            }
        }
    }
}



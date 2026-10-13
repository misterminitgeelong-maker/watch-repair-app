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
                title = { Text("Shoe repairs", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
                actions = { TextButton(onClick = { viewModel.refresh() }, enabled = !state.loading, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") } },
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(onClick = onNewJob, containerColor = MaterialTheme.colorScheme.primary, contentColor = MaterialTheme.colorScheme.onPrimary) { Text("New repair", style = MaterialTheme.typography.labelLarge) }
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            if (state.loading && state.jobs.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(16.dp), onRetry = { viewModel.refresh() }) }
            if (!state.loading && state.error == null && state.jobs.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No shoe repairs yet", "Tap New repair to book in a pair.")
            LazyColumn(
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 96.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxSize().weight(1f, fill = true),
            ) {
                items(state.jobs, key = { it.id }) { j ->
                    au.mainspring.nativeapp.ui.ListCard({ onOpenJob(j.id) }) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Text(j.jobNumber, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            au.mainspring.nativeapp.ui.StatusPill(j.status)
                        }
                        Text(j.title, style = MaterialTheme.typography.titleMedium)
                    }
                }
                if(state.canLoadMore) item { OutlinedButton(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text("Load more repairs") } }
            }
        }
    }
}

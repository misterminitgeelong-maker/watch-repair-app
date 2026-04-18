package au.mainspring.nativeapp.ui.screens

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
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.JobsViewModel

@Composable
fun JobsScreen(
    onOpenJob: (String) -> Unit,
    viewModel: JobsViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Column(
        Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        RowActions(onRefresh = { viewModel.refresh() }, loading = state.loading)
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
        }
    }
}

@Composable
private fun RowActions(onRefresh: () -> Unit, loading: Boolean) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(12.dp),
        horizontalArrangement = Arrangement.End,
    ) {
        Button(onClick = onRefresh, enabled = !loading) {
            Text("Refresh")
        }
    }
}

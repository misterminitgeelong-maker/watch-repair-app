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
import au.mainspring.nativeapp.AutoKeyJobsViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutoKeyJobsScreen(
    onBack: () -> Unit,
    onOpenJob: (String) -> Unit,
    viewModel: AutoKeyJobsViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Mobile services") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.End) {
                Button(onClick = { viewModel.refresh() }, enabled = !state.loading) { Text("Refresh") }
            }
            if (state.loading && state.jobs.isEmpty()) CircularProgressIndicator(Modifier.padding(24.dp))
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp)) }
            LazyColumn(
                contentPadding = PaddingValues(bottom = 24.dp),
                modifier = Modifier.fillMaxSize().weight(1f, fill = true),
            ) {
                items(state.jobs, key = { it.id }) { j ->
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .clickable { onOpenJob(j.id) }
                            .padding(16.dp),
                    ) {
                        Text("${j.jobNumber} · ${j.status}", style = MaterialTheme.typography.titleMedium)
                        Text(j.title, style = MaterialTheme.typography.bodyMedium)
                        j.customerName?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                        Text("Programming: ${j.programmingStatus}", style = MaterialTheme.typography.labelSmall)
                    }
                    HorizontalDivider()
                }
            }
        }
    }
}

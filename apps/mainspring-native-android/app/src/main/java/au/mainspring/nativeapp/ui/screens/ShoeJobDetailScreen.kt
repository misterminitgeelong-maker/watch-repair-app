package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ShoeJobDetailViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShoeJobDetailScreen(
    jobId: String,
    onBack: () -> Unit,
) {
    val vm: ShoeJobDetailViewModel = viewModel(key = jobId, factory = ShoeJobDetailViewModel.factory(jobId))
    val state by vm.state.collectAsStateWithLifecycle()
    val j = state.job

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(j?.jobNumber ?: "Shoe job") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
            )
        },
    ) { padding ->
        when {
            state.loading && j == null -> CircularProgressIndicator(Modifier.padding(padding).padding(24.dp))
            state.error != null && j == null -> Text(state.error ?: "", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(padding).padding(16.dp))
            j != null -> {
                Column(
                    Modifier
                        .padding(padding)
                        .padding(16.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    Text(j.title, style = MaterialTheme.typography.titleLarge)
                    Text("Status ${j.status}", style = MaterialTheme.typography.bodyLarge)
                    Text("Quote ${j.quoteStatus}", style = MaterialTheme.typography.bodyMedium)
                    j.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                    Text("Created ${j.createdAt}", style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

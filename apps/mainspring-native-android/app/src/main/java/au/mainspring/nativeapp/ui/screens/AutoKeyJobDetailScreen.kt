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
import au.mainspring.nativeapp.AutoKeyJobDetailViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutoKeyJobDetailScreen(
    jobId: String,
    onBack: () -> Unit,
) {
    val vm: AutoKeyJobDetailViewModel = viewModel(key = jobId, factory = AutoKeyJobDetailViewModel.factory(jobId))
    val state by vm.state.collectAsStateWithLifecycle()
    val j = state.job

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(j?.jobNumber ?: "Job") },
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
                    Text("Programming ${j.programmingStatus}", style = MaterialTheme.typography.bodyMedium)
                    j.customerName?.let { Text("Customer $it", style = MaterialTheme.typography.bodyMedium) }
                    listOf(
                        j.vehicleMake to "Make",
                        j.vehicleModel to "Model",
                        j.registrationPlate to "Plate",
                        j.vin to "VIN",
                        j.jobAddress to "Address",
                    ).forEach { (v, label) ->
                        v?.takeIf { it.isNotBlank() }?.let { Text("$label: $it", style = MaterialTheme.typography.bodySmall) }
                    }
                    j.techNotes?.takeIf { it.isNotBlank() }?.let { Text("Tech notes\n$it", style = MaterialTheme.typography.bodySmall) }
                    Text("Created ${j.createdAt}", style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

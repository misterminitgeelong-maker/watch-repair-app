package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.AUTO_KEY_JOB_STATUS_OPTIONS
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
    var statusPicker by remember { mutableStateOf(false) }
    var statusChangeNote by remember { mutableStateOf("") }

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
                    Button(
                        onClick = {
                            statusChangeNote = ""
                            statusPicker = true
                        },
                        enabled = !state.statusBusy,
                        modifier = Modifier.padding(top = 16.dp),
                    ) {
                        Text(if (state.statusBusy) "Updating…" else "Change status")
                    }
                    state.error?.let {
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
                    }
                }
            }
        }
    }

    if (statusPicker) {
        AlertDialog(
            onDismissRequest = { statusPicker = false },
            title = { Text("Choose status") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    OutlinedTextField(
                        value = statusChangeNote,
                        onValueChange = { statusChangeNote = it },
                        label = { Text("Note (optional)") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = false,
                        maxLines = 3,
                    )
                    AUTO_KEY_JOB_STATUS_OPTIONS.forEach { s ->
                        TextButton(onClick = {
                            vm.setStatus(s, statusChangeNote.trim().takeIf { it.isNotEmpty() })
                            statusChangeNote = ""
                            statusPicker = false
                        }) {
                            Text(s)
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { statusPicker = false }) { Text("Close") }
            },
        )
    }
}

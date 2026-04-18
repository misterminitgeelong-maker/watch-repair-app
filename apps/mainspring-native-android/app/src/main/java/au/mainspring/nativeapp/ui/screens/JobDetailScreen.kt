package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
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
import au.mainspring.nativeapp.JobDetailViewModel
import au.mainspring.nativeapp.WATCH_JOB_STATUS_OPTIONS

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobDetailScreen(
    jobId: String,
    onBack: () -> Unit,
) {
    val vm: JobDetailViewModel = viewModel(key = jobId, factory = JobDetailViewModel.factory(jobId))
    val state by vm.state.collectAsStateWithLifecycle()
    var statusPicker by remember { mutableStateOf(false) }
    var addNoteOpen by remember { mutableStateOf(false) }
    var statusChangeNote by remember { mutableStateOf("") }
    var newNoteDraft by remember { mutableStateOf("") }
    val job = state.job

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(job?.jobNumber ?: "Job") },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back") } },
            )
        },
    ) { padding ->
        when {
            state.loading && job == null -> CircularProgressIndicator(Modifier.padding(padding).padding(24.dp))
            state.error != null && job == null -> Text(state.error ?: "", color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(padding).padding(16.dp))
            job != null -> {
                LazyColumn(Modifier.padding(padding).padding(16.dp)) {
                    item {
                        Text(job.title, style = MaterialTheme.typography.titleLarge)
                        Text("Status: ${job.status}", style = MaterialTheme.typography.bodyLarge)
                        job.customerName?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                        Text("Priority ${job.priority}", style = MaterialTheme.typography.bodySmall)
                        job.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                        Button(
                            onClick = {
                                statusChangeNote = ""
                                statusPicker = true
                            },
                            enabled = !state.statusBusy,
                            modifier = Modifier.padding(top = 12.dp),
                        ) {
                            Text(if (state.statusBusy) "Updating…" else "Change status")
                        }
                        Button(
                            onClick = {
                                newNoteDraft = ""
                                addNoteOpen = true
                            },
                            enabled = !state.noteBusy,
                            modifier = Modifier.padding(top = 8.dp),
                        ) {
                            Text(if (state.noteBusy) "Saving…" else "Add shop note")
                        }
                        state.error?.let {
                            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
                        }
                        HorizontalDivider(Modifier.padding(vertical = 16.dp))
                        Text("Status history", style = MaterialTheme.typography.titleSmall)
                    }
                    items(state.history, key = { it.id }) { h ->
                        Column(Modifier.padding(vertical = 6.dp)) {
                            Text("${h.oldStatus ?: "—"} → ${h.newStatus}", style = MaterialTheme.typography.bodyMedium)
                            h.changeNote?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                            Text(h.createdAt, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        HorizontalDivider()
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
                    WATCH_JOB_STATUS_OPTIONS.forEach { s ->
                        TextButton(onClick = {
                            vm.setStatus(s, statusChangeNote.trim().takeIf { t -> t.isNotEmpty() })
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

    if (addNoteOpen) {
        AlertDialog(
            onDismissRequest = { addNoteOpen = false },
            title = { Text("Add shop note") },
            text = {
                OutlinedTextField(
                    value = newNoteDraft,
                    onValueChange = { newNoteDraft = it },
                    label = { Text("Note") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    singleLine = false,
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        vm.addNote(newNoteDraft)
                        addNoteOpen = false
                    },
                    enabled = !state.noteBusy && newNoteDraft.trim().isNotEmpty(),
                ) {
                    Text("Save")
                }
            },
            dismissButton = {
                TextButton(onClick = { addNoteOpen = false }) { Text("Cancel") }
            },
        )
    }
}

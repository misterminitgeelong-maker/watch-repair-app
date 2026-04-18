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
import au.mainspring.nativeapp.SHOE_JOB_STATUS_OPTIONS
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
    var statusPicker by remember { mutableStateOf(false) }
    var addNoteOpen by remember { mutableStateOf(false) }
    var statusChangeNote by remember { mutableStateOf("") }
    var newNoteDraft by remember { mutableStateOf("") }

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
                    Button(
                        onClick = {
                            newNoteDraft = ""
                            addNoteOpen = true
                        },
                        enabled = !state.noteBusy,
                        modifier = Modifier.padding(top = 8.dp),
                    ) {
                        Text(if (state.noteBusy) "Saving…" else "Add note")
                    }
                    state.error?.let {
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
                    }
                    HorizontalDivider(Modifier.padding(vertical = 16.dp))
                    Text("Status history", style = MaterialTheme.typography.titleSmall)
                    if (state.history.isEmpty()) {
                        Text(
                            "No history yet",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    } else {
                        state.history.forEach { h ->
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
    }

    if (statusPicker) {
        AlertDialog(
            onDismissRequest = { statusPicker = false },
            title = { Text("Update status") },
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
                    SHOE_JOB_STATUS_OPTIONS.forEach { s ->
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

    if (addNoteOpen) {
        AlertDialog(
            onDismissRequest = { addNoteOpen = false },
            title = { Text("Add note") },
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

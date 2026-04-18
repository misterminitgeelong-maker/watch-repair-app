package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import au.mainspring.nativeapp.CustomerDetailViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerDetailScreen(
    customerId: String,
    onBack: () -> Unit,
    onOpenWatchJob: (String) -> Unit,
) {
    val vm: CustomerDetailViewModel = viewModel(
        key = customerId,
        factory = CustomerDetailViewModel.factory(customerId),
    )
    val state by vm.state.collectAsStateWithLifecycle()
    var newJobOpen by remember { mutableStateOf(false) }
    var selectedWatchId by remember { mutableStateOf<String?>(null) }
    var newJobTitle by remember { mutableStateOf("") }
    var newJobDescription by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.customer?.fullName ?: "Customer") },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("Back")
                    }
                },
                actions = {
                    if (state.customer != null && state.watches.isNotEmpty()) {
                        TextButton(
                            onClick = {
                                selectedWatchId = state.watches.firstOrNull()?.id
                                newJobTitle = ""
                                newJobDescription = ""
                                newJobOpen = true
                            },
                            enabled = !state.createJobBusy,
                        ) {
                            Text("New job")
                        }
                    }
                },
            )
        },
    ) { padding ->
        when {
            state.loading && state.customer == null -> {
                CircularProgressIndicator(Modifier.padding(padding).padding(24.dp))
            }
            state.error != null && state.customer == null -> {
                Text(
                    state.error ?: "",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(padding).padding(16.dp),
                )
            }
            state.customer != null -> {
                val c = state.customer!!
                LazyColumn(
                    Modifier
                        .padding(padding)
                        .fillMaxSize()
                        .padding(16.dp),
                ) {
                    item {
                        DetailLine("Email", c.email)
                        DetailLine("Phone", c.phone)
                        DetailLine("Address", c.address)
                        DetailLine("Notes", c.notes)
                        Spacer(Modifier.height(8.dp))
                        Text("Created ${c.createdAt}", style = MaterialTheme.typography.bodySmall)
                        state.error?.let { err ->
                            if (state.customer != null) {
                                Text(err, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 8.dp))
                            }
                        }
                        HorizontalDivider(Modifier.padding(vertical = 16.dp))
                        Text("Watches", style = MaterialTheme.typography.titleSmall)
                    }
                    if (state.watches.isEmpty()) {
                        item {
                            Text(
                                "No watches on file — add a watch in the web app before creating a job.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    } else {
                        items(state.watches, key = { it.id }) { w ->
                            Column(Modifier.padding(vertical = 8.dp)) {
                                Text(
                                    listOfNotNull(w.brand, w.model).joinToString(" · ").ifEmpty { "Watch" },
                                    style = MaterialTheme.typography.bodyLarge,
                                )
                                w.serialNumber?.takeIf { it.isNotBlank() }?.let {
                                    Text("Serial $it", style = MaterialTheme.typography.bodySmall)
                                }
                                w.movementType?.takeIf { it.isNotBlank() }?.let {
                                    Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                            HorizontalDivider()
                        }
                    }
                    item {
                        HorizontalDivider(Modifier.padding(vertical = 16.dp))
                        Text("Watch repair jobs", style = MaterialTheme.typography.titleSmall)
                    }
                    if (state.watchJobs.isEmpty()) {
                        item {
                            Text(
                                "No watch jobs for this customer",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    } else {
                        items(state.watchJobs, key = { it.id }) { job ->
                            Column(
                                Modifier
                                    .clickable { onOpenWatchJob(job.id) }
                                    .padding(vertical = 8.dp),
                            ) {
                                Text("${job.jobNumber} · ${job.status}", style = MaterialTheme.typography.bodyLarge)
                                Text(job.title, style = MaterialTheme.typography.bodyMedium)
                            }
                            HorizontalDivider()
                        }
                    }
                }
            }
        }
    }

    if (newJobOpen && state.customer != null) {
        AlertDialog(
            onDismissRequest = { if (!state.createJobBusy) newJobOpen = false },
            title = { Text("New watch repair job") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    Text("Watch", style = MaterialTheme.typography.labelMedium)
                    state.watches.forEach { w ->
                        val label = listOfNotNull(w.brand, w.model).joinToString(" · ").ifEmpty { "Watch" }
                        val sel = w.id == selectedWatchId
                        Column(
                            Modifier
                                .fillMaxWidth()
                                .clickable { selectedWatchId = w.id }
                                .background(
                                    if (sel) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
                                )
                                .padding(12.dp),
                        ) {
                            Text(label, style = MaterialTheme.typography.bodyMedium)
                            w.serialNumber?.takeIf { it.isNotBlank() }?.let { Text("Serial $it", style = MaterialTheme.typography.bodySmall) }
                        }
                        Spacer(Modifier.height(4.dp))
                    }
                    OutlinedTextField(
                        value = newJobTitle,
                        onValueChange = { newJobTitle = it },
                        label = { Text("Title") },
                        singleLine = false,
                        minLines = 2,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 12.dp),
                    )
                    OutlinedTextField(
                        value = newJobDescription,
                        onValueChange = { newJobDescription = it },
                        label = { Text("Description (optional)") },
                        minLines = 2,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 8.dp),
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        selectedWatchId?.let { wid ->
                            vm.createWatchRepairJob(
                                watchId = wid,
                                title = newJobTitle,
                                description = newJobDescription.takeIf { it.isNotBlank() },
                            ) { jobId ->
                                newJobOpen = false
                                onOpenWatchJob(jobId)
                            }
                        }
                    },
                    enabled = !state.createJobBusy && selectedWatchId != null && newJobTitle.trim().isNotEmpty(),
                ) {
                    Text(if (state.createJobBusy) "Creating…" else "Create")
                }
            },
            dismissButton = {
                TextButton(onClick = { newJobOpen = false }, enabled = !state.createJobBusy) {
                    Text("Cancel")
                }
            },
        )
    }
}

@Composable
private fun DetailLine(label: String, value: String?) {
    if (value.isNullOrBlank()) return
    Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
    Text(value, style = MaterialTheme.typography.bodyLarge)
    Spacer(Modifier.height(12.dp))
}

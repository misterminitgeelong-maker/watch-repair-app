package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.DispatchPoolViewModel
import au.mainspring.nativeapp.ui.RefreshOnResume

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DispatchPoolScreen(onBack: () -> Unit, onOpenJob: (String) -> Unit, onOpenBoard: () -> Unit, vm: DispatchPoolViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    var confirmingId by rememberSaveable { mutableStateOf<String?>(null) }
    RefreshOnResume(vm::refresh)
    Scaffold(topBar = { TopAppBar(title = { Text("Dispatch pool", style = MaterialTheme.typography.titleLarge) }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text("Nearby unclaimed work. Ring 1 is closest. Claiming creates a mobile job for your shop.")
                if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                OutlinedButton(onClick = vm::refresh, enabled = !state.busy && !state.loading) { Text("Refresh pool") }
                if(state.unresolvedId.isNotBlank()) {
                    Text("An earlier claim needs review. Refresh, then check the mobile job board before trying again.")
                    TextButton(onClick = onOpenBoard) { Text("Check mobile job board") }
                    if(state.historyChecked) {
                        Text(if(state.jobs.any { it.id == state.unresolvedId }) "This request is still available in the pool." else "This request is no longer available. It may have been claimed; check your board for the resulting job.")
                        OutlinedButton(onClick = vm::reviewedUnresolvedClaim, enabled = !state.busy) { Text("I have reviewed the job board") }
                    }
                }
                state.claimed?.let { result ->
                    Text("Job ${result.jobNumber} claimed.")
                    Button(onClick = { onOpenJob(result.jobId) }) { Text("Open claimed job") }
                }
                if(!state.loading && state.jobs.isEmpty() && state.error == null) Text("No unclaimed jobs in your service area.")
            }
            items(state.jobs, key = { it.id }) { job ->
                Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Ring ${job.ring} · ${job.customerName}", style = MaterialTheme.typography.titleMedium)
                    Text(listOfNotNull(job.make, job.model, job.year, job.plate).filter { it.isNotBlank() }.joinToString(" · "))
                    Text(job.address)
                    job.description?.let { Text(it) }
                    Button(onClick = { confirmingId = job.id }, enabled = !state.busy && !state.loading && state.unresolvedId.isBlank() && state.claimed == null) { Text("Claim job") }
                } }
            }
        }
    }
    confirmingId?.let { id ->
        AlertDialog(onDismissRequest = { confirmingId = null }, title = { Text("Claim this job?", style = MaterialTheme.typography.headlineSmall) },
            text = { Text("The work will be assigned to your shop and added to your mobile job board.") },
            confirmButton = { TextButton(onClick = { confirmingId = null; vm.claim(id) }) { Text("Confirm claim") } },
            dismissButton = { TextButton(onClick = { confirmingId = null }) { Text("Cancel") } })
    }
}

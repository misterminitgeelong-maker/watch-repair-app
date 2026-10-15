package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.screens.LinkAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.DispatchPoolViewModel
import au.mainspring.nativeapp.ui.RefreshOnResume

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DispatchPoolScreen(onBack: () -> Unit, onOpenJob: (String) -> Unit, onOpenBoard: () -> Unit, vm: DispatchPoolViewModel = viewModel(),
    extras: au.mainspring.nativeapp.DispatchExtrasViewModel = viewModel(), pollMs: Long = au.mainspring.nativeapp.POOL_POLL_MS) {
    val state by vm.state.collectAsStateWithLifecycle()
    val extra by extras.state.collectAsStateWithLifecycle()
    var baseOpen by rememberSaveable { mutableStateOf(false) }
    val lifecycleOwner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner, pollMs) {
        lifecycleOwner.lifecycle.repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) {
            while(true) { kotlinx.coroutines.delay(pollMs); vm.poll() }
        }
    }
    var confirmingId by rememberSaveable { mutableStateOf<String?>(null) }
    RefreshOnResume(vm::refresh)
    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Dispatch pool") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
        actions = {
            if(au.mainspring.nativeapp.TokenStore.canManageInvoices()) TextButton(onClick = { baseOpen = true }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Service area") }
            TextButton(onClick = vm::refresh, enabled = !state.busy && !state.loading, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") } }) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text("Nearby unclaimed work, closest first. Claiming one adds it to your mobile job board.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = vm::refresh) }
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
                if(!state.loading && state.jobs.isEmpty() && state.error == null) au.mainspring.nativeapp.ui.EmptyState("Nothing to claim right now", "New unclaimed work in your service area will appear here.")
            }
            itemsIndexed(state.jobs, key = { _, job -> job.id }) { index, job ->
                if(index == 0 || state.jobs[index - 1].ring != job.ring) au.mainspring.nativeapp.ui.SectionLabel("Ring ${job.ring} jobs")
                au.mainspring.nativeapp.ui.FlatPanel {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Text(job.customerName, style = MaterialTheme.typography.titleMedium)
                        Text("Ring ${job.ring}", style = if(au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.Calibre.label else MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                    }
                    listOfNotNull(job.make, job.model, job.year?.toString(), job.plate).filter { it.isNotBlank() }.joinToString(" Â· ").let { vehicle ->
                        if(au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.MonoLabel(vehicle)
                        else Text(vehicle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Text(job.address, style = MaterialTheme.typography.bodyMedium)
                    job.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    Button(onClick = { confirmingId = job.id }, enabled = !state.busy && !state.loading && state.unresolvedId.isBlank() && state.claimed == null, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Claim job") }
                }
            }
        }
    }
    confirmingId?.let { id ->
        AlertDialog(onDismissRequest = { confirmingId = null }, title = { Text("Claim this job?") },
            text = { Text("The work will be assigned to your shop and added to your mobile job board.") },
            confirmButton = { TextButton(onClick = { confirmingId = null; vm.claim(id) }) { Text("Confirm claim") } },
            dismissButton = { TextButton(onClick = { confirmingId = null }) { Text("Cancel") } })
    }
    if(baseOpen) {
        var address by rememberSaveable { mutableStateOf("") }
        var radius by rememberSaveable { mutableStateOf("10") }
        AlertDialog(onDismissRequest = { baseOpen = false; extras.clearMessage() }, title = { Text("Service area") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Pool jobs are ranked by distance from your base address. Operators under an HQ have this set by HQ.", style = MaterialTheme.typography.bodySmall)
                    OutlinedTextField(address, { address = it }, label = { Text("Base address") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(radius, { radius = it.filter(Char::isDigit).take(3) }, label = { Text("Ring radius (km)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    extra.message?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    extra.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
                    if(extra.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                }
            },
            confirmButton = { TextButton(onClick = { extras.saveBaseLocation(address, radius.toIntOrNull() ?: 0, onSaved = vm::refresh) }, enabled = !extra.busy) { Text("Save") } },
            dismissButton = { TextButton(onClick = { baseOpen = false; extras.clearMessage() }) { Text(if(extra.baseSaved != null) "Done" else "Cancel") } })
    }
}

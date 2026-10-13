package au.mainspring.nativeapp.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.JobDetailViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.WATCH_JOB_STATUS_OPTIONS
import au.mainspring.nativeapp.ui.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobDetailScreen(
    jobId: String,
    apiBaseUrl: String,
    onBack: () -> Unit,
    onQuotes: (String) -> Unit,
    onMessages: () -> Unit,
    onWorkLogs: () -> Unit,
    onEdit: () -> Unit,
    onPhotos: () -> Unit = {},
) {
    val vm: JobDetailViewModel = viewModel(
        key = "$jobId|$apiBaseUrl",
        factory = JobDetailViewModel.factory(jobId, apiBaseUrl),
    )
    val state by vm.state.collectAsStateWithLifecycle()
    RefreshOnResume(vm::load)
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var statusPicker by remember { mutableStateOf(false) }
    var addNoteOpen by remember { mutableStateOf(false) }
    var statusChangeNote by remember { mutableStateOf("") }
    var newNoteDraft by remember { mutableStateOf("") }
    var attachmentOpenError by remember { mutableStateOf<String?>(null) }
    var resendPicker by remember { mutableStateOf(false) }
    val job = state.job
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    androidx.activity.compose.BackHandler(state.statusBusy) {}

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(job?.jobNumber ?: "Repair", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = { BackButton(onClick = onBack, enabled = !state.statusBusy) },
                actions = {
                    TextButton(onClick = vm::load, enabled = !state.loading && !state.statusBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") }
                    TextButton(onClick = onEdit, enabled = !state.loading && !state.statusBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text("Edit") }
                },
            )
        },
        bottomBar = {
            if (job != null) Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 2.dp) {
                Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SecondaryAction(onClick = { onQuotes(jobId) }, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Quotes and invoicing") }
                    PrimaryAction(
                        onClick = { statusChangeNote = ""; statusPicker = true },
                        enabled = !state.statusBusy && !state.loading && !state.statusUnknown && TokenStore.canWorkJobs(),
                        modifier = Modifier.weight(1f).heightIn(min = 52.dp),
                    ) { Text(if (state.statusBusy) "Updating…" else "Change status") }
                }
            }
        },
    ) { padding ->
        when {
            state.loading && job == null -> LinearProgressIndicator(Modifier.padding(padding).fillMaxWidth())
            state.error != null && job == null -> ErrorBanner(state.error ?: "", Modifier.padding(padding).padding(16.dp), onRetry = vm::load)
            job != null -> {
                LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item { CounterStatusReview(state.statusUnknown, state.statusRequest, state.statusReviewed, state.loading, vm::load, vm::reviewedStatus) }
                    item {
                        FlatPanel {
                            Text(job.title, style = MaterialTheme.typography.titleLarge)
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                                StatusPill(job.status)
                                if (job.priority != "normal") StatusPill(if (job.priority == "urgent" || job.priority == "high") "urgent" else job.priority)
                            }
                            job.customerName?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
                            job.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                    }
                    item {
                        MetricStrip(buildList {
                            add("Deposit" to formatCents(job.depositCents, currency))
                            if (job.preQuoteCents > 0) add("Pre-quote" to formatCents(job.preQuoteCents, currency))
                            job.collectionDate?.let { add("Collect by" to formatShopDate(it)) }
                        })
                    }
                    if (job.partsEta != null || !job.internalNotes.isNullOrBlank()) item {
                        FlatPanel {
                            job.partsEta?.let { DetailRow("Parts ETA", formatShopDate(it)) }
                            job.internalNotes?.takeIf { it.isNotBlank() }?.let { DetailRow("Internal notes", it) }
                        }
                    }
                    item {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            SecondaryAction(onClick = onMessages, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Messages") }
                            SecondaryAction(onClick = onPhotos, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Photos & files") }
                        }
                        Spacer(Modifier.height(8.dp))
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            SecondaryAction(onClick = onWorkLogs, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Log work") }
                            SecondaryAction(onClick = { resendPicker = true }, enabled = !state.resendBusy, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text(if (state.resendBusy) "Sending…" else "Notify customer") }
                        }
                        Spacer(Modifier.height(8.dp))
                        SecondaryAction(onClick = { newNoteDraft = ""; addNoteOpen = true }, enabled = !state.noteBusy, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text(if (state.noteBusy) "Saving…" else "Add shop note") }
                    }
                    state.resendInfo?.let { item { Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onPrimaryContainer, style = MaterialTheme.typography.bodyMedium) } } }
                    state.error?.let { item { ErrorBanner(it) } }
                    item {
                        FlatPanel {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text("Assigned to", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text(job.claimedByName ?: "Nobody yet", style = MaterialTheme.typography.bodyLarge)
                                }
                                if (job.claimedByName == null) SecondaryAction(onClick = { vm.claimJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "…" else "Claim for me") }
                                else SecondaryAction(onClick = { vm.releaseJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "…" else "Release") }
                            }
                        }
                    }
                    item { SectionLabel("Attachments") }
                    item {
                        attachmentOpenError?.let { ErrorBanner(it) }
                        if (state.attachments.isEmpty()) Text("No files on this job yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    items(state.attachments, key = { it.id }) { att ->
                        FlatPanel {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text(att.fileName ?: att.storageKey, style = MaterialTheme.typography.bodyLarge)
                                    att.contentType?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                                }
                                TextButton(
                                    onClick = {
                                        attachmentOpenError = null
                                        scope.launch {
                                            try {
                                                val url = vm.resolveDownloadUrl(att.storageKey)
                                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                                            } catch (e: Exception) {
                                                attachmentOpenError = e.message ?: "Could not open file"
                                            }
                                        }
                                    },
                                    modifier = Modifier.heightIn(min = 48.dp),
                                ) { Text("Open") }
                            }
                        }
                    }
                    if (state.smsLog.isNotEmpty()) {
                        item { SectionLabel("Customer messages sent") }
                        items(state.smsLog, key = { it.id }) { log ->
                            FlatPanel {
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    Text(statusLabel(log.event), style = MaterialTheme.typography.bodyLarge)
                                    Text(statusLabel(log.status), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                Text(log.body, style = MaterialTheme.typography.bodyMedium)
                                Text("${log.toPhone} · ${formatShopDate(log.createdAt)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    if (state.history.isNotEmpty()) {
                        item { SectionLabel("Status history") }
                        item {
                            FlatPanel {
                                state.history.forEachIndexed { i, h ->
                                    if (i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                                    Column {
                                        Text("${h.oldStatus?.let { statusLabel(it) } ?: "New"} → ${statusLabel(h.newStatus)}", style = MaterialTheme.typography.bodyLarge)
                                        h.changeNote?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                                        Text(formatShopDate(h.createdAt), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (statusPicker) {
        AlertDialog(
            onDismissRequest = { statusPicker = false },
            title = { Text("Change status") },
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
                    Spacer(Modifier.height(8.dp))
                    WATCH_JOB_STATUS_OPTIONS.forEach { s ->
                        val current = s == job?.status
                        TextButton(
                            onClick = {
                                vm.setStatus(s, statusChangeNote.trim().takeIf { t -> t.isNotEmpty() })
                                statusChangeNote = ""
                                statusPicker = false
                            },
                            enabled = !current,
                            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
                        ) { Text(statusLabel(s) + if (current) " (current)" else "", Modifier.fillMaxWidth()) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { statusPicker = false }) { Text("Close") } },
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
                PrimaryAction(
                    onClick = { vm.addNote(newNoteDraft); addNoteOpen = false },
                    enabled = !state.noteBusy && newNoteDraft.trim().isNotEmpty(),
                ) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { addNoteOpen = false }) { Text("Cancel") } },
        )
    }

    if (resendPicker) {
        AlertDialog(
            onDismissRequest = { resendPicker = false },
            title = { Text("Notify customer") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    Text(
                        "The server checks the customer's phone, email and quote state. If nothing is sent, check the messages log on this job.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(bottom = 8.dp),
                    )
                    listOf("job_live" to "Job is live (SMS)", "job_ready" to "Ready for pickup (SMS + email)", "quote_sent" to "Quote sent (SMS + email)").forEach { (event, label) ->
                        TextButton(onClick = { vm.resendNotification(event); resendPicker = false }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text(label, Modifier.fillMaxWidth()) }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { resendPicker = false }) { Text("Close") } },
        )
    }
}

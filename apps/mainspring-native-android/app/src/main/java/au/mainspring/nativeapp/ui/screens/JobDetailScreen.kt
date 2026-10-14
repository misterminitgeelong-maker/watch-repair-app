package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.background
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

    var tab by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf("summary") }
    if (job == null) {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().padding(16.dp)) {
            TextButton(onClick = onBack) { Text("\u2039 Jobs", style = MaterialTheme.typography.titleSmall) }
            if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { ErrorBanner(it, onRetry = vm::load) }
        }
    } else AtelierDetail(
        backLabel = "Jobs", title = job.title,
        reference = listOfNotNull(job.jobNumber, job.customerName?.takeIf { it.isNotBlank() }).joinToString(" \u00b7 "),
        banner = listOfNotNull(statusLabel(job.status), if (job.priority == "urgent" || job.priority == "high") "Urgent" else null,
            if (job.depositCents < job.preQuoteCents) "Balance outstanding" else null).joinToString(" \u00b7 "),
        tabs = listOf("summary" to "Summary", "activity" to "Activity", "messages" to "Messages"), selectedTab = tab, onTab = { tab = it },
        onBack = onBack, backEnabled = !state.statusBusy,
        primaryLabel = if (state.statusBusy) "Updating\u2026" else "Change status",
        primaryEnabled = !state.statusBusy && !state.loading && !state.statusUnknown && TokenStore.canWorkJobs(),
        onPrimary = { statusChangeNote = ""; statusPicker = true },
        footnote = listOfNotNull(job.depositCents.takeIf { it > 0 }?.let { "Deposit ${formatCents(it, currency)}" }, job.preQuoteCents.takeIf { it > 0 }?.let { "Pre-quote ${formatCents(it, currency)}" }).joinToString(" \u00b7 ").ifBlank { null },
        menu = listOf(
            DetailAction("Edit repair details", !state.loading && !state.statusBusy, onEdit),
            DetailAction("Refresh", !state.loading && !state.statusBusy, vm::load),
            DetailAction("Photos & files", true, onPhotos),
            DetailAction("Log work", true, onWorkLogs),
            DetailAction("Notify customer", !state.resendBusy) { resendPicker = true },
            DetailAction("Add shop note", !state.noteBusy) { newNoteDraft = ""; addNoteOpen = true },
        ),
        scrollBody = tab != "messages",
    ) { active ->
        CounterStatusReview(state.statusUnknown, state.statusRequest, state.statusReviewed, state.loading, vm::load, vm::reviewedStatus)
        state.error?.let { ErrorBanner(it) }
        state.resendInfo?.let { Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onPrimaryContainer, style = MaterialTheme.typography.bodyMedium) } }
        when (active) {
            "activity" -> {
                if(LocalCalibre.current) MonoLabel("Repair activity / most recent first")
                if (state.history.isEmpty() && state.smsLog.isEmpty()) Text("No activity recorded yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                state.history.forEach { h ->
                    ActivityCard(statusLabel(h.newStatus), h.changeNote?.takeIf { it.isNotBlank() } ?: h.oldStatus?.let { "From ${statusLabel(it)}" }, formatShopDate(h.createdAt))
                }
                state.smsLog.forEach { log -> ActivityCard(statusLabel(log.event), "${statusLabel(log.status)} \u00b7 ${log.body}", "${log.toPhone} \u00b7 ${formatShopDate(log.createdAt)}") }
                state.attachments.forEach { att ->
                    FlatPanel {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(att.fileName ?: att.storageKey, style = MaterialTheme.typography.titleMedium)
                                att.contentType?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                            }
                            TextButton(onClick = {
                                attachmentOpenError = null
                                scope.launch {
                                    try { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(vm.resolveDownloadUrl(att.storageKey)))) }
                                    catch (e: Exception) { attachmentOpenError = e.message ?: "Could not open file" }
                                }
                            }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Open") }
                        }
                    }
                }
                attachmentOpenError?.let { ErrorBanner(it) }
                Text("Activity includes status changes, approvals, photos and private workshop notes.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            "messages" -> MessageThreadScreen("repair-jobs", jobId, { tab = "summary" }, embedded = true)
            else -> {
                if(LocalCalibre.current) {
                    JobStageStrip(watchStage(job.status))
                    if(state.history.isNotEmpty()) {
                        SectionLabel("Repair history / ${state.history.size} ${if(state.history.size == 1) "event" else "events"}")
                        state.history.take(3).forEach { h ->
                            ActivityCard(statusLabel(h.newStatus), h.changeNote?.takeIf { it.isNotBlank() } ?: h.oldStatus?.let { "From ${statusLabel(it)}" }, formatShopDate(h.createdAt))
                        }
                    }
                }
                FlatPanel {
                    Text(job.title, style = MaterialTheme.typography.titleMedium)
                    job.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    Text(listOfNotNull(job.claimedByName, job.collectionDate?.let { "Due ${formatShopDate(it)}" }, job.partsEta?.let { "Parts ${formatShopDate(it)}" }).joinToString(" \u00b7 ").ifBlank { "Unassigned" },
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                SummaryCard("Customer & contact", job.customerName ?: "No customer recorded", "Contact details and repair history")
                SummaryCard("Quotes & invoicing", listOfNotNull(job.depositCents.takeIf { it > 0 }?.let { "${formatCents(it, currency)} deposit" }, job.preQuoteCents.takeIf { it > 0 }?.let { "${formatCents(it, currency)} pre-quote" }).joinToString(" \u00b7 ").ifBlank { "No charges recorded yet" },
                    "View charges or record payment", { onQuotes(jobId) })
                SummaryCard("Activity & work notes", "Intake and workshop record", "Status changes, approvals and internal notes", { tab = "activity" })
                job.internalNotes?.takeIf { it.isNotBlank() }?.let { SummaryCard("Internal notes", it, null) }
                FlatPanel {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Assigned to", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(job.claimedByName ?: "Nobody yet", style = MaterialTheme.typography.titleMedium)
                        }
                        if (job.claimedByName == null) SecondaryAction(onClick = { vm.claimJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "\u2026" else "Claim for me") }
                        else SecondaryAction(onClick = { vm.releaseJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "\u2026" else "Release") }
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
                    au.mainspring.nativeapp.ui.AtelierTextField(
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
                au.mainspring.nativeapp.ui.AtelierTextField(
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

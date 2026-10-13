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
import au.mainspring.nativeapp.SHOE_JOB_STATUS_OPTIONS
import au.mainspring.nativeapp.ShoeJobDetailViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShoeJobDetailScreen(
    jobId: String,
    apiBaseUrl: String,
    onBack: () -> Unit,
    onMessages: () -> Unit,
    onEdit: () -> Unit,
    onPhotos: () -> Unit = {},
) {
    val vm: ShoeJobDetailViewModel = viewModel(
        key = "$jobId|$apiBaseUrl",
        factory = ShoeJobDetailViewModel.factory(jobId, apiBaseUrl),
    )
    val state by vm.state.collectAsStateWithLifecycle()
    RefreshOnResume(vm::load)
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val j = state.job
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    var statusPicker by remember { mutableStateOf(false) }
    var addNoteOpen by remember { mutableStateOf(false) }
    var statusChangeNote by remember { mutableStateOf("") }
    androidx.activity.compose.BackHandler(state.statusBusy) {}
    var newNoteDraft by remember { mutableStateOf("") }
    var confirmQuote by remember { mutableStateOf(false) }
    var attachmentOpenError by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(j?.jobNumber ?: "Shoe repair", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = { BackButton(onClick = onBack, enabled = !state.statusBusy) },
                actions = {
                    TextButton(onClick = vm::load, enabled = !state.loading && !state.statusBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") }
                    TextButton(onClick = onEdit, enabled = !state.loading && !state.statusBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text("Edit") }
                },
            )
        },
        bottomBar = {
            if (j != null) Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 2.dp) {
                Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (j.quoteStatus != "approved") SecondaryAction(onClick = { confirmQuote = true }, enabled = !state.quoteBusy, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Send quote") }
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
            state.loading && j == null -> LinearProgressIndicator(Modifier.padding(padding).fillMaxWidth())
            state.error != null && j == null -> ErrorBanner(state.error ?: "", Modifier.padding(padding).padding(16.dp), onRetry = vm::load)
            j != null -> {
                LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item { CounterStatusReview(state.statusUnknown, state.statusRequest, state.statusReviewed, state.loading, vm::load, vm::reviewedStatus) }
                    item {
                        FlatPanel {
                            Text(j.title, style = MaterialTheme.typography.titleLarge)
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                                StatusPill(j.status)
                                if (j.quoteStatus != "none") StatusPill(if (j.quoteStatus == "approved") "approved" else "quote_" + j.quoteStatus)
                            }
                            j.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                            Text("Created ${formatShopDate(j.createdAt)}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    item {
                        MetricStrip(buildList {
                            add("Deposit" to formatCents(j.depositCents, currency))
                            j.collectionDate?.let { add("Collect by" to formatShopDate(it)) }
                        })
                    }
                    if (j.items.isNotEmpty()) item {
                        SectionLabel("Work")
                        FlatPanel {
                            j.items.forEachIndexed { i, item ->
                                if (i > 0) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Column(Modifier.weight(1f)) {
                                        Text(item.name, style = MaterialTheme.typography.bodyLarge)
                                        item.notes?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                                    }
                                    Text("${item.quantity} × " + (item.price?.let { formatCents(it, currency) } ?: "Quote"), style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }
                    item {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            SecondaryAction(onClick = onMessages, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Messages") }
                            SecondaryAction(onClick = onPhotos, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Photos & files") }
                        }
                        Spacer(Modifier.height(8.dp))
                        SecondaryAction(onClick = { newNoteDraft = ""; addNoteOpen = true }, enabled = !state.noteBusy, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text(if (state.noteBusy) "Saving…" else "Add note") }
                    }
                    state.error?.let { item { ErrorBanner(it) } }
                    item {
                        FlatPanel {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text("Assigned to", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text(j.claimedByName ?: "Nobody yet", style = MaterialTheme.typography.bodyLarge)
                                }
                                if (j.claimedByName == null) SecondaryAction(onClick = { vm.claimJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "…" else "Claim for me") }
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

    if (confirmQuote) AlertDialog(onDismissRequest = { confirmQuote = false }, title = { Text("Send quote?") },
        text = { Text("Send the saved repair quote to the customer's phone for approval.") },
        confirmButton = { TextButton(onClick = { confirmQuote = false; vm.sendQuote() }) { Text("Send") } },
        dismissButton = { TextButton(onClick = { confirmQuote = false }) { Text("Cancel") } })
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
                    SHOE_JOB_STATUS_OPTIONS.forEach { s ->
                        val current = s == j?.status
                        TextButton(
                            onClick = {
                                vm.setStatus(s, statusChangeNote.trim().takeIf { it.isNotEmpty() })
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
                PrimaryAction(
                    onClick = { vm.addNote(newNoteDraft); addNoteOpen = false },
                    enabled = !state.noteBusy && newNoteDraft.trim().isNotEmpty(),
                ) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { addNoteOpen = false }) { Text("Cancel") } },
        )
    }
}

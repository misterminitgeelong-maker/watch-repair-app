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
    onDeleted: () -> Unit = {},
    onDuplicated: (String) -> Unit = {},
    onEditCustomer: (String) -> Unit = {},
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
    var statusCustomerNote by remember { mutableStateOf("") }
    var pickServices by remember { mutableStateOf(false) }
    var addPair by remember { mutableStateOf(false) }
    var removeItem by remember { mutableStateOf<String?>(null) }
    var removePairId by remember { mutableStateOf<String?>(null) }
    var attachmentOpenError by remember { mutableStateOf<String?>(null) }
    var confirmDelete by remember { mutableStateOf(false) }
    var confirmDuplicate by remember { mutableStateOf(false) }
    var accountPicker by remember { mutableStateOf(false) }
    LaunchedEffect(state.deleted) { if (state.deleted) onDeleted() }
    LaunchedEffect(state.clonedJobId) { state.clonedJobId?.let { vm.consumeClonedJob(); onDuplicated(it) } }
    val adminReady = !state.loading && !state.statusBusy && !state.adminBusy

    var tab by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf("overview") }
    if (j == null) {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().padding(16.dp)) {
            TextButton(onClick = onBack) { Text("\u2039 Jobs", style = MaterialTheme.typography.titleSmall) }
            if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { ErrorBanner(it, onRetry = vm::load) }
        }
    } else AtelierDetail(
        backLabel = "Jobs", title = j.title, reference = j.jobNumber,
        banner = statusLabel(j.status).let { s -> val q = if (j.quoteStatus != "none") "Quote ${j.quoteStatus.replace('_', ' ')}" else null; if (q == null || q.equals(s, true)) s else "$s · $q" },
        tabs = listOf("overview" to "Overview", "history" to "History", "messages" to "Messages"), selectedTab = tab, onTab = { tab = it },
        onBack = onBack, backEnabled = !state.statusBusy,
        primaryLabel = if (state.statusBusy) "Updating\u2026" else "Update repair status",
        primaryEnabled = !state.statusBusy && !state.loading && !state.statusUnknown && TokenStore.canWorkJobs(),
        onPrimary = { statusChangeNote = ""; statusCustomerNote = ""; statusPicker = true },
        footnote = j.depositCents.takeIf { it > 0 }?.let { "Deposit ${formatCents(it, currency)}" },
        menu = listOfNotNull(
            DetailAction("Edit repair details", !state.loading && !state.statusBusy, onEdit),
            DetailAction("Refresh", !state.loading && !state.statusBusy, vm::load),
            DetailAction("Photos & files", true, onPhotos),
            if (j.quoteStatus != "approved") DetailAction("Send quote to customer", !state.quoteBusy) { confirmQuote = true } else null,
            DetailAction("Add note", !state.noteBusy) { newNoteDraft = ""; addNoteOpen = true },
            DetailAction("Print intake ticket", true) {
                try {
                    val pairs = listOfNotNull(j.shoe) + j.extraShoes.orEmpty().mapNotNull { it.shoe }
                    au.mainspring.nativeapp.ui.printIntakeTicket(context, au.mainspring.nativeapp.ui.IntakeTicket(
                        jobNumber = j.jobNumber, customerName = null, customerPhone = null,
                        itemSummary = pairs.joinToString("; ") { listOfNotNull(it.brand, it.shoeType, it.color).joinToString(" ") }.ifBlank { j.title },
                        workSummary = (j.items.map { it.name } + listOfNotNull(j.description?.takeIf { it.isNotBlank() })).joinToString("\n").ifBlank { j.title },
                        dueDate = (j.collectionDate ?: j.estimatedReadyBy)?.takeIf { it.isNotBlank() }?.let { formatShopDate(it) },
                        deposit = j.depositCents.takeIf { it > 0 }?.let { formatCents(it, currency) },
                        statusUrl = au.mainspring.nativeapp.ui.intakeStatusUrl(apiBaseUrl, au.mainspring.nativeapp.ui.IntakeTicketKind.SHOE, j.statusToken),
                        shopName = TokenStore.shopValue("name"), shopPhone = TokenStore.shopValue("phone"),
                        kind = au.mainspring.nativeapp.ui.IntakeTicketKind.SHOE))
                } catch (e: Exception) { android.widget.Toast.makeText(context, e.message ?: "Could not print", android.widget.Toast.LENGTH_LONG).show() }
            },
            DetailAction("Edit customer", adminReady && j.shoe?.customerId != null) { j.shoe?.customerId?.let(onEditCustomer) },
            DetailAction("Business account", adminReady && !state.accountBusy && TokenStore.canWorkJobs()) { vm.loadAccounts(); accountPicker = true },
            DetailAction("Duplicate job", adminReady && TokenStore.canWorkJobs()) { confirmDuplicate = true },
            if (TokenStore.canManageInvoices()) DetailAction("Delete job", adminReady) { confirmDelete = true } else null,
        ),
        scrollBody = tab != "messages",
    ) { active ->
        CounterStatusReview(state.statusUnknown, state.statusRequest, state.statusReviewed, state.loading, vm::load, vm::reviewedStatus)
        state.error?.let { ErrorBanner(it) }
        when (active) {
            "history" -> {
                if (state.history.isEmpty()) Text("No history yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                state.history.forEach { h -> ActivityCard(statusLabel(h.newStatus), h.changeNote?.takeIf { it.isNotBlank() } ?: h.oldStatus?.let { "From ${statusLabel(it)}" }, formatShopDate(h.createdAt)) }
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
            }
            "messages" -> MessageThreadScreen("shoe-repair-jobs", jobId, { tab = "overview" }, embedded = true)
            else -> {
                j.description?.takeIf { it.isNotBlank() }?.let { SummaryCard("Requested work", it, null) }
                j.customerNote?.takeIf { it.isNotBlank() }?.let { SummaryCard("Note shown to customer", it, null) }
                val canEdit = TokenStore.canWorkJobs() && !state.editBusy && !state.loading
                SectionLabel("Shoes")
                ShoePairCard(1, j.shoe, null, canEdit)
                j.extraShoes.orEmpty().forEachIndexed { i, e -> ShoePairCard(i + 2, e.shoe, { removePairId = e.id }, canEdit) }
                if(j.shoe?.customerId != null) SecondaryAction(onClick = { addPair = true }, enabled = canEdit, modifier = Modifier.heightIn(min = 48.dp)) { Text("Add pair") }
                SectionLabel("Services")
                if(j.items.isEmpty()) Text("No services added yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                j.items.forEach { item -> ShoeServiceRow(item, currency, { removeItem = item.id }, canEdit) }
                SecondaryAction(onClick = { vm.loadCatalogue(); pickServices = true }, enabled = canEdit, modifier = Modifier.heightIn(min = 48.dp)) { Text("Add services") }
                j.estimatedReadyBy?.takeIf { it.isNotBlank() }?.let { SummaryCard("Estimated ready", formatShopDate(it), null) }
                if (j.customerAccountId != null) SummaryCard("Business account", "Linked to a customer account", null)
                SummaryCard(statusLabel(j.status), listOfNotNull(j.claimedByName?.let { "Assigned to $it" }, "Created ${formatShopDate(j.createdAt)}").joinToString(" \u00b7 "), null)
                SummaryCard("Quote and invoice", j.items.mapNotNull { it.price?.let { p -> p * it.quantity.toInt() } }.sum().takeIf { it > 0 }?.let { "${formatCents(it, currency)} ${if (j.quoteStatus == "approved") "approved" else "quoted"}" } ?: "Quote ${j.quoteStatus.replace('_', ' ')}",
                    "View services, pricing and payment")
                FlatPanel {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Assigned to", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(j.claimedByName ?: "Nobody yet", style = MaterialTheme.typography.titleMedium)
                        }
                        if (j.claimedByName == null) SecondaryAction(onClick = { vm.claimJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "\u2026" else "Claim for me") }
                        else SecondaryAction(onClick = { vm.releaseJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "\u2026" else "Release") }
                    }
                }
            }
        }
    }

    if (confirmQuote) AlertDialog(onDismissRequest = { confirmQuote = false }, title = { Text("Send quote?") },
        text = { Text("Send the saved repair quote to the customer's phone for approval.") },
        confirmButton = { TextButton(onClick = { confirmQuote = false; vm.sendQuote() }) { Text("Send") } },
        dismissButton = { TextButton(onClick = { confirmQuote = false }) { Text("Cancel") } })
    if (confirmDelete) DeleteJobDialog(j?.let { "${it.jobNumber} · ${it.title}" } ?: "this job", { confirmDelete = false; vm.deleteJob() }, { confirmDelete = false })
    if (confirmDuplicate) DuplicateJobDialog({ confirmDuplicate = false; vm.duplicateJob() }, { confirmDuplicate = false })
    if (accountPicker) AccountPickerDialog(state.accounts, state.accountsLoading, j?.shoe?.customerId, j?.customerAccountId,
        { id -> accountPicker = false; vm.assignAccount(id) }, { accountPicker = false })
    if(pickServices) ShoeServicePickerDialog(state.catalogue, currency, state.editBusy, { pickServices = false }) { vm.addServices(it); pickServices = false }
    if(addPair) AddPairDialog(state.editBusy, { addPair = false }) { type, brand, colour, notes -> vm.addPair(type, brand, colour, notes) }
    removeItem?.let { id -> AlertDialog(onDismissRequest = { removeItem = null }, title = { Text("Remove service?") },
        text = { Text("This removes ${j?.items?.firstOrNull { it.id == id }?.name ?: "the service"} from the job and its quote.") },
        confirmButton = { TextButton(onClick = { removeItem = null; vm.removeService(id) }) { Text("Remove") } },
        dismissButton = { TextButton(onClick = { removeItem = null }) { Text("Cancel") } }) }
    removePairId?.let { id -> AlertDialog(onDismissRequest = { removePairId = null }, title = { Text("Remove pair?") },
        text = { Text("This removes the pair from the job. Services already added stay on the job.") },
        confirmButton = { TextButton(onClick = { removePairId = null; vm.removePair(id) }) { Text("Remove") } },
        dismissButton = { TextButton(onClick = { removePairId = null }) { Text("Cancel") } }) }
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
                    au.mainspring.nativeapp.ui.AtelierTextField(
                        value = statusCustomerNote,
                        onValueChange = { statusCustomerNote = it.take(ShoeJobDetailViewModel.SHOE_CUSTOMER_NOTE_MAX) },
                        label = { Text("Message for customer (optional)") },
                        supportingText = { Text("Shown on their status page \u00b7 ${statusCustomerNote.length}/${ShoeJobDetailViewModel.SHOE_CUSTOMER_NOTE_MAX}") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = false,
                        maxLines = 3,
                    )
                    Spacer(Modifier.height(8.dp))
                    SHOE_JOB_STATUS_OPTIONS.forEach { s ->
                        val current = s == j?.status
                        TextButton(
                            onClick = {
                                vm.setStatus(s, statusChangeNote.trim().takeIf { it.isNotEmpty() }, statusCustomerNote)
                                statusChangeNote = ""; statusCustomerNote = ""
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
}

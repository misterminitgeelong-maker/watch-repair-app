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
import androidx.compose.ui.text.style.TextAlign
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
    initialTab: String = "overview",
) {
    // Prev/next steps through the list the job was opened from without leaving this screen.
    var shownId by androidx.compose.runtime.saveable.rememberSaveable(jobId) { mutableStateOf(jobId) }
    val vm: ShoeJobDetailViewModel = viewModel(
        key = "$shownId|$apiBaseUrl",
        factory = ShoeJobDetailViewModel.factory(shownId, apiBaseUrl),
    )
    val state by vm.state.collectAsStateWithLifecycle()
    RefreshOnResume(vm::load)
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val j = state.job
    val suggested = j?.let { au.mainspring.nativeapp.suggestedShoeStatuses(it.status) } ?: emptyList()
    val quoteFirst = j?.let { it.quoteStatus != "approved" && it.status == "awaiting_quote" } == true
    val (prevJobId, nextJobId) = au.mainspring.nativeapp.JobNavContext.neighbors("shoe", shownId)
    var niimbotLabels by remember { mutableStateOf<List<au.mainspring.nativeapp.niimbot.NiimbotLabelData>?>(null) }
    niimbotLabels?.let { au.mainspring.nativeapp.niimbot.NiimbotPrintDialog(it, { niimbotLabels = null }) }
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
    var resendPicker by remember { mutableStateOf(false) }
    LaunchedEffect(state.deleted) { if (state.deleted) onDeleted() }
    LaunchedEffect(state.clonedJobId) { state.clonedJobId?.let { vm.consumeClonedJob(); onDuplicated(it) } }
    val adminReady = !state.loading && !state.statusBusy && !state.adminBusy

    var tab by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf(initialTab) }
    if (j == null) {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().padding(16.dp)) {
            TextButton(onClick = onBack) { Text("\u2039 Jobs", style = MaterialTheme.typography.titleSmall) }
            if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { ErrorBanner(it, onRetry = vm::load) }
            state.info?.let { Text(it, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodyMedium) }
        }
    } else AtelierDetail(
        backLabel = "Shoe Repairs", title = (if (j.jobNumber.startsWith("#")) j.jobNumber else "#" + j.jobNumber) + " · " + j.title,
        facts = run {
            val days = au.mainspring.nativeapp.daysInShop(j.createdAt)
            val quoteTotal = j.items.mapNotNull { it.price?.let { p -> p * it.quantity.toInt() } }.sum().takeIf { it > 0 }
            listOfNotNull(
                DetailFact("Status", statusLabel(j.status), pillStatus = j.status),
                DetailFact("Priority", j.priority.replace('_', ' ').replaceFirstChar { it.uppercase() }),
                if (quoteTotal != null) DetailFact("Quote", formatCents(quoteTotal, currency) + if (j.quoteStatus == "approved") " approved" else "")
                else if (j.quoteStatus != "none") DetailFact("Quote", j.quoteStatus.replace('_', ' ').replaceFirstChar { it.uppercase() }) else null,
                DetailFact("Created", formatShopDate(j.createdAt)),
                DetailFact("In shop", if (days == 1) "1 day" else "$days days", tag = "days-in-shop",
                    valueColor = when (au.mainspring.nativeapp.daysInShopSeverity(days)) { 2 -> MaterialTheme.colorScheme.error; 1 -> androidx.compose.ui.graphics.Color(0xFF9A5010); else -> null }),
            )
        },
        tabs = detailTabs(state.attachments.size, state.history.size + state.smsLog.size), selectedTab = tab, onTab = { tab = it },
        onBack = onBack, backEnabled = !state.statusBusy,
        primaryLabel = if (state.statusBusy) "Updating…" else if (quoteFirst) "Send Quote" else suggested.firstOrNull()?.let { "→ " + statusLabel(it) } ?: "Change status", primaryFilled = quoteFirst,
        primaryEnabled = !state.statusBusy && !state.loading && !state.statusUnknown && TokenStore.canWorkJobs() && !(quoteFirst && state.quoteBusy),
        primaryTag = if (quoteFirst) "detail-send-quote" else suggested.firstOrNull()?.let { "rail-next-$it" } ?: "detail-primary",
        onPrimary = { val s = suggested.firstOrNull(); if (quoteFirst) confirmQuote = true else if (s != null) vm.setStatus(s) else { statusChangeNote = ""; statusCustomerNote = ""; statusPicker = true } },
        onChangeStatus = { statusChangeNote = ""; statusCustomerNote = ""; statusPicker = true },
        onPrev = prevJobId?.let { id -> { shownId = id; tab = "overview" } },
        onNext = nextJobId?.let { id -> { shownId = id; tab = "overview" } },
        header = {
            ContactQuickActions(state.customer?.phone, state.customer?.email)
            WorkflowRail(au.mainspring.nativeapp.SHOE_WORKFLOW_STEPS, j.status)
        },
        menu = (if (quoteFirst) suggested else suggested.drop(1)).map { s -> DetailAction("Move to " + statusLabel(s).lowercase(), !state.statusBusy && !state.loading && !state.statusUnknown && TokenStore.canWorkJobs()) { vm.setStatus(s) } } + listOfNotNull(
            DetailAction("Edit repair details", !state.loading && !state.statusBusy, onEdit),
            DetailAction("Refresh", !state.loading && !state.statusBusy, vm::load),
            DetailAction("Photos & files", true, onPhotos),
            if (j.quoteStatus != "approved") DetailAction("Send quote to customer", !state.quoteBusy) { confirmQuote = true } else null,
            DetailAction("Add note", !state.noteBusy) { newNoteDraft = ""; addNoteOpen = true },
            DetailAction("Print intake ticket", true) {
                try {
                    val pairs = listOfNotNull(j.shoe) + j.extraShoes.orEmpty().mapNotNull { it.shoe }
                    au.mainspring.nativeapp.ui.printIntakeTicket(context, au.mainspring.nativeapp.ui.IntakeTicket(
                        jobNumber = j.jobNumber, customerName = state.customer?.fullName, customerPhone = state.customer?.phone,
                        itemSummary = pairs.joinToString("; ") { listOfNotNull(it.brand, it.shoeType, it.color).joinToString(" ") }.ifBlank { j.title },
                        workSummary = (j.items.map { it.name } + listOfNotNull(j.description?.takeIf { it.isNotBlank() })).joinToString("\n").ifBlank { j.title },
                        dueDate = (j.collectionDate ?: j.estimatedReadyBy)?.takeIf { it.isNotBlank() }?.let { formatShopDate(it) },
                        deposit = j.depositCents.takeIf { it > 0 }?.let { formatCents(it, currency) },
                        statusUrl = au.mainspring.nativeapp.ui.intakeStatusUrl(apiBaseUrl, au.mainspring.nativeapp.ui.IntakeTicketKind.SHOE, j.statusToken),
                        shopName = TokenStore.shopValue("name"), shopPhone = TokenStore.shopValue("phone"),
                        kind = au.mainspring.nativeapp.ui.IntakeTicketKind.SHOE))
                } catch (e: Exception) { android.widget.Toast.makeText(context, e.message ?: "Could not print", android.widget.Toast.LENGTH_LONG).show() }
            },
            DetailAction("Print label (Niimbot)", true) {
                niimbotLabels = au.mainspring.nativeapp.ui.shoeJobBundle(j, state.customer?.fullName, state.customer?.phone, au.mainspring.nativeapp.ui.JobPrintContext(
                    apiBaseUrl, TokenStore.shopValue("name"), TokenStore.shopValue("phone"), { formatCents(it, currency) }, { formatShopDate(it) })).labels
            },
            DetailAction("Edit customer", adminReady && j.shoe?.customerId != null) { j.shoe?.customerId?.let(onEditCustomer) },
            DetailAction("Business account", adminReady && !state.accountBusy && TokenStore.canWorkJobs()) { vm.loadAccounts(); accountPicker = true },
            DetailAction("Notify customer", !state.resendBusy && TokenStore.canWorkJobs()) { resendPicker = true },
            DetailAction("Duplicate job", adminReady && TokenStore.canWorkJobs()) { confirmDuplicate = true },
            if (TokenStore.canManageInvoices()) DetailAction("Delete job", adminReady) { confirmDelete = true } else null,
        ),
        scrollBody = tab != "messages",
    ) { active ->
        CounterStatusReview(state.statusUnknown, state.statusRequest, state.statusReviewed, state.loading, vm::load, vm::reviewedStatus)
        state.error?.let { ErrorBanner(it) }
        PendingStatusBanner(shownId)
        SyncedRefreshEffect(shownId) { vm.load() }
        state.resendInfo?.let { Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onPrimaryContainer, style = MaterialTheme.typography.bodyMedium) } }
        when (active) {
            "messages" -> MessageThreadScreen("shoe-repair-jobs", shownId, { tab = "overview" }, embedded = true)
            "work" -> {
                val canEdit = TokenStore.canWorkJobs() && !state.editBusy && !state.loading
                FlatPanel {
                    CardHeading("Services")
                    if(j.items.isEmpty()) Text("No services added yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    j.items.forEach { item -> ShoeServiceRow(item, currency, { removeItem = item.id }, canEdit) }
                    SecondaryAction(onClick = { vm.loadCatalogue(); pickServices = true }, enabled = canEdit, modifier = Modifier.heightIn(min = 48.dp)) { Text("Add services") }
                }
                FlatPanel {
                    CardHeading("Shop notes")
                    SecondaryAction(onClick = { newNoteDraft = ""; addNoteOpen = true }, enabled = !state.noteBusy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Add note") }
                }
            }
            "attachments" -> {
                if(LocalCalibre.current) JobHeroPhoto("shoe", shownId, known = state.attachments.takeIf { !state.loading }, onClick = onPhotos)
                FlatPanel {
                    CardHeading("Photos & files / ${state.attachments.size}")
                    if (state.attachments.isEmpty()) Text(if (state.loading) "Loading…" else "No photos or files yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    state.attachments.forEach { att ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(att.fileName ?: att.storageKey, style = MaterialTheme.typography.titleSmall)
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
                    attachmentOpenError?.let { ErrorBanner(it) }
                    SecondaryAction(onClick = onPhotos, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Photos & files") }
                }
            }
            "money" -> {
                SummaryCard("Quote and invoice", j.items.mapNotNull { it.price?.let { p -> p * it.quantity.toInt() } }.sum().takeIf { it > 0 }?.let { "${formatCents(it, currency)} ${if (j.quoteStatus == "approved") "approved" else "quoted"}" } ?: "Quote ${j.quoteStatus.replace('_', ' ')}",
                    "View services, pricing and payment")
                if (j.quoteStatus != "approved") SecondaryAction(onClick = { confirmQuote = true }, enabled = !state.quoteBusy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Send quote to customer") }
                if (j.depositCents > 0) SummaryCard("Deposit", formatCents(j.depositCents, currency), null)
            }
            else -> {
                val canEdit = TokenStore.canWorkJobs() && !state.editBusy && !state.loading
                WebCard {
                    WebCardTitle("Photos", icon = "camera")
                    if (state.attachments.isNotEmpty()) JobHeroPhoto("shoe", shownId, known = state.attachments.takeIf { !state.loading }, onClick = onPhotos)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        WebButton("Take photo", onPhotos, primary = true, icon = "camera", tag = "take-photo")
                        DashedButton("Gallery upload", onPhotos, "upload")
                    }
                    if (state.attachments.isEmpty()) Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        GlyphIcon("camera", size = 28.dp, color = MaterialTheme.colorScheme.outline)
                        Text(if (state.loading) "Loading…" else "No photos yet. Tap to add intake or gallery photos.", style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                    }
                }
                WebCard(padding = 0.dp) {
                    val pairs = 1 + j.extraShoes.orEmpty().size
                    WebCardTitle("Shoes", icon = "shoe", count = if (pairs == 1) "1 pair" else "$pairs pairs", modifier = Modifier.padding(start = 16.dp, end = 4.dp, top = 8.dp)) {
                        if (j.shoe?.customerId != null) TextButton(onClick = { addPair = true }, enabled = canEdit, modifier = Modifier.heightIn(min = 48.dp)) {
                            GlyphIcon("plus", size = 14.dp, color = LocalContentColor.current); Spacer(Modifier.width(4.dp)); Text("Add pair")
                        }
                    }
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                        ShoePairCard(1, j.shoe, null, canEdit)
                        j.extraShoes.orEmpty().forEachIndexed { i, e -> ShoePairCard(i + 2, e.shoe, { removePairId = e.id }, canEdit) }
                    }
                }
                FlatPanel {
                    CardHeading("Job ticket")
                    Text(j.title, style = MaterialTheme.typography.titleMedium)
                    j.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    DetailRow("Job #", j.jobNumber)
                    DetailRow("Status", statusLabel(j.status))
                    j.estimatedReadyBy?.takeIf { it.isNotBlank() }?.let { DetailRow("Estimated ready", formatShopDate(it)) }
                    DetailRow("Created", formatShopDate(j.createdAt))
                    if (j.customerAccountId != null) DetailRow("Business account", "Linked")
                    j.customerNote?.takeIf { it.isNotBlank() }?.let { DetailRow("Customer note", it) }
                }
                state.customer?.let { c ->
                    var contactError by remember { mutableStateOf<String?>(null) }
                    val phone = c.phone?.takeIf { it.isNotBlank() }
                    val email = c.email?.takeIf { it.isNotBlank() }
                    FlatPanel {
                        CardHeading("Customer & contact")
                        Text(c.fullName, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (phone == null && email == null) Text("No phone or email on file", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        phone?.let { p -> TextButton(onClick = { contactError = launchContact(context, Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + p.filter { ch -> ch.isDigit() || ch == '+' }))) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Call $p") } }
                        email?.let { e -> TextButton(onClick = { contactError = launchContact(context, Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:" + Uri.encode(e)))) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Email $e") } }
                        contactError?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
                    }
                }
                FlatPanel {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Assigned to", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(j.claimedByName ?: "Nobody yet", style = MaterialTheme.typography.titleMedium)
                        }
                        if (j.claimedByName == null) SecondaryAction(onClick = { vm.claimJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "…" else "Claim for me") }
                        else SecondaryAction(onClick = { vm.releaseJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "…" else "Release") }
                    }
                }
                au.mainspring.nativeapp.ui.CustomFieldsCard(au.mainspring.nativeapp.CustomFieldJobKind.Shoe, j.id, canEdit = TokenStore.canWorkJobs())
                FlatPanel {
                    CardHeading("History")
                    if (state.history.isEmpty() && state.smsLog.isEmpty()) Text("No history yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    state.history.forEach { h -> ActivityCard(statusLabel(h.newStatus), h.changeNote?.takeIf { it.isNotBlank() } ?: h.oldStatus?.let { "From ${statusLabel(it)}" }, formatShopDate(h.createdAt)) }
                    state.smsLog.forEach { log -> ActivityCard(statusLabel(log.event), "${statusLabel(log.status)} · ${log.body}", "${log.toPhone} · ${formatShopDate(log.createdAt)}") }
                }
            }
        }
    }

    if (resendPicker) AlertDialog(onDismissRequest = { resendPicker = false }, title = { Text("Notify customer") },
        text = { Column {
            Text("Sends a text to the customer's phone. The result appears in History.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            TextButton(onClick = { vm.resendNotification("job_live"); resendPicker = false }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Job is live", Modifier.fillMaxWidth()) }
            j?.let { TextButton(onClick = { vm.resendNotification("status_" + it.status); resendPicker = false }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Current status: " + statusLabel(it.status), Modifier.fillMaxWidth()) } }
        } },
        confirmButton = { TextButton(onClick = { resendPicker = false }) { Text("Close") } })
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

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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.JobDetailViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.watchPickerOptions
import au.mainspring.nativeapp.watchStatusLabel
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
    onDeleted: () -> Unit = {},
    onDuplicated: (String) -> Unit = {},
    onEditCustomer: (String) -> Unit = {},
    onEditWatch: (String, String) -> Unit = { _, _ -> },
) {
    // Prev/next steps through the list the job was opened from without leaving this screen.
    var shownId by androidx.compose.runtime.saveable.rememberSaveable(jobId) { mutableStateOf(jobId) }
    val vm: JobDetailViewModel = viewModel(
        key = "$shownId|$apiBaseUrl",
        factory = JobDetailViewModel.factory(shownId, apiBaseUrl),
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
    var statusCustomerNote by remember { mutableStateOf("") }
    var assignPicker by remember { mutableStateOf(false) }
    var contactError by remember { mutableStateOf<String?>(null) }
    var confirmDelete by remember { mutableStateOf(false) }
    var confirmDuplicate by remember { mutableStateOf(false) }
    var accountPicker by remember { mutableStateOf(false) }
    LaunchedEffect(state.deleted) { if (state.deleted) onDeleted() }
    LaunchedEffect(state.clonedJobId) { state.clonedJobId?.let { vm.consumeClonedJob(); onDuplicated(it) } }
    val job = state.job
    val suggested = job?.let { au.mainspring.nativeapp.suggestedWatchStatuses(it.status) } ?: emptyList()
    val (prevJobId, nextJobId) = au.mainspring.nativeapp.JobNavContext.neighbors("watch", shownId)
    var niimbotLabel by remember { mutableStateOf<au.mainspring.nativeapp.niimbot.NiimbotLabelData?>(null) }
    niimbotLabel?.let { au.mainspring.nativeapp.niimbot.NiimbotPrintDialog(it) { niimbotLabel = null } }
    val adminReady = !state.loading && !state.statusBusy && !state.adminBusy
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    androidx.activity.compose.BackHandler(state.statusBusy) {}

    var tab by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf("overview") }
    if (job == null) {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().padding(16.dp)) {
            TextButton(onClick = onBack, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.onSurfaceVariant)) {
                LineIcon("chevL", androidx.compose.material3.LocalContentColor.current, 18.dp); Spacer(Modifier.width(6.dp))
                Text("Back to Jobs", style = MaterialTheme.typography.bodyLarge)
            }
            if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { ErrorBanner(it, onRetry = vm::load) }
        }
    } else AtelierDetail(
        backLabel = "Jobs", title = (if (job.jobNumber.startsWith("#")) job.jobNumber else "#" + job.jobNumber) + " \u00b7 " + job.title,
        facts = run {
            val days = au.mainspring.nativeapp.daysInShop(job.createdAt)
            val quote = (if (state.invoiceTotalCents > 0) state.invoiceTotalCents else job.preQuoteCents).takeIf { it > 0 }
            listOfNotNull(
                DetailFact("Status", watchStatusLabel(job.status), pillStatus = job.status),
                DetailFact("Priority", job.priority.replace('_', ' ').replaceFirstChar { it.uppercase() }),
                quote?.let { DetailFact("Quote", webMoney(it, currency)) },
                DetailFact("Created", shopDateOnly(job.createdAt)),
                DetailFact("In shop", if (days == 1) "1 day" else "$days days", tag = "days-in-shop",
                    valueColor = when (au.mainspring.nativeapp.daysInShopSeverity(days)) { 2 -> MaterialTheme.colorScheme.error; 1 -> androidx.compose.ui.graphics.Color(0xFF9A5010); else -> null }),
            )
        },
        tabs = detailTabs(state.attachments.size, state.history.size + state.smsLog.size), selectedTab = tab, onTab = { tab = it },
        onBack = onBack, backEnabled = !state.statusBusy,
        primaryLabel = if (state.statusBusy) "Updating\u2026" else suggested.firstOrNull()?.let { "\u2192 " + watchStatusLabel(it) } ?: "Change status",
        primaryEnabled = !state.statusBusy && !state.loading && !state.statusUnknown && TokenStore.canWorkJobs(),
        primaryTag = suggested.firstOrNull()?.let { "rail-next-$it" } ?: "detail-primary",
        onPrimary = { val s = suggested.firstOrNull(); if (s != null) vm.setStatus(s) else { statusChangeNote = ""; statusCustomerNote = ""; statusPicker = true } },
        onChangeStatus = { statusChangeNote = ""; statusCustomerNote = ""; statusPicker = true },
        onPrev = prevJobId?.let { id -> { shownId = id; tab = "overview" } },
        onNext = nextJobId?.let { id -> { shownId = id; tab = "overview" } },
        header = {
            ContactQuickActions(job.customerPhone, job.customerEmail)
            WorkflowRail(au.mainspring.nativeapp.WATCH_WORKFLOW_STEPS, job.status)
        },
        menu = suggested.drop(1).map { s -> DetailAction("Move to " + watchStatusLabel(s).lowercase(), !state.statusBusy && !state.loading && !state.statusUnknown && TokenStore.canWorkJobs()) { vm.setStatus(s) } } + listOfNotNull(
            DetailAction("Edit repair details", !state.loading && !state.statusBusy, onEdit),
            DetailAction("Refresh", !state.loading && !state.statusBusy, vm::load),
            DetailAction("Photos & files", true, onPhotos),
            DetailAction("Log work", true, onWorkLogs),
            DetailAction("Notify customer", !state.resendBusy) { resendPicker = true },
            DetailAction("Assign technician", !state.assignBusy && !state.loading && !state.statusBusy && TokenStore.canWorkJobs()) { vm.loadUsers(); assignPicker = true },
            DetailAction("Add shop note", !state.noteBusy) { newNoteDraft = ""; addNoteOpen = true },
            DetailAction("Print intake ticket", job.statusToken != null) {
                try {
                    au.mainspring.nativeapp.ui.printIntakeTicket(context, au.mainspring.nativeapp.ui.IntakeTicket(
                        jobNumber = job.jobNumber, customerName = job.customerName, customerPhone = job.customerPhone,
                        itemSummary = listOfNotNull(job.watchBrand, job.watchModel).joinToString(" ").ifBlank { "Watch" },
                        workSummary = listOfNotNull(job.title.takeIf { it.isNotBlank() }, job.description?.takeIf { it.isNotBlank() }).joinToString("\n").ifBlank { null },
                        dueDate = job.collectionDate?.takeIf { it.isNotBlank() }?.let { formatShopDate(it) },
                        deposit = job.depositCents.takeIf { it > 0 }?.let { formatCents(it, currency) },
                        statusUrl = au.mainspring.nativeapp.ui.intakeStatusUrl(apiBaseUrl, au.mainspring.nativeapp.ui.IntakeTicketKind.WATCH, job.statusToken.orEmpty()),
                        shopName = TokenStore.shopValue("name"), shopPhone = TokenStore.shopValue("phone"),
                        kind = au.mainspring.nativeapp.ui.IntakeTicketKind.WATCH))
                } catch (e: Exception) { android.widget.Toast.makeText(context, e.message ?: "Could not print", android.widget.Toast.LENGTH_LONG).show() }
            },
            DetailAction("Print label (Niimbot)", job.statusToken != null) {
                niimbotLabel = au.mainspring.nativeapp.niimbot.NiimbotLabelData(
                    jobNumber = job.jobNumber, customerName = job.customerName, customerPhone = job.customerPhone,
                    itemTitle = listOfNotNull(job.watchBrand, job.watchModel).joinToString(" ").ifBlank { "Watch" },
                    services = job.title.takeIf { it.isNotBlank() },
                    dateIn = null,
                    qrText = au.mainspring.nativeapp.ui.intakeStatusUrl(apiBaseUrl, au.mainspring.nativeapp.ui.IntakeTicketKind.WATCH, job.statusToken.orEmpty()),
                )
            },
            DetailAction("Edit customer", adminReady && state.watch != null) { state.watch?.customerId?.let(onEditCustomer) },
            DetailAction("Edit watch details", adminReady && state.watch != null) { state.watch?.let { onEditWatch(it.customerId, it.id) } },
            DetailAction("Business account", adminReady && !state.accountBusy && TokenStore.canWorkJobs()) { vm.loadAccounts(); accountPicker = true },
            DetailAction("Duplicate job", adminReady && TokenStore.canWorkJobs()) { confirmDuplicate = true },
            if (TokenStore.canManageInvoices()) DetailAction("Delete job", adminReady) { confirmDelete = true } else null,
        ),
        scrollBody = tab != "messages",
    ) { active ->
        CounterStatusReview(state.statusUnknown, state.statusRequest, state.statusReviewed, state.loading, vm::load, vm::reviewedStatus)
        PendingStatusBanner(shownId)
        SyncedRefreshEffect(shownId) { vm.load() }
        state.error?.let { ErrorBanner(it) }
        state.resendInfo?.let { Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) { Text(it, Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onPrimaryContainer, style = MaterialTheme.typography.bodyMedium) } }
        when (active) {
            "messages" -> MessageThreadScreen("repair-jobs", shownId, { tab = "overview" }, embedded = true)
            "work" -> {
                val workLogs: au.mainspring.nativeapp.WorkLogsViewModel = viewModel(key = shownId, factory = au.mainspring.nativeapp.WorkLogsViewModel.factory(shownId))
                val workLogState by workLogs.state.collectAsStateWithLifecycle()
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text(if (workLogState.rows.size == 1) "1 log" else "${workLogState.rows.size} logs", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    AccentAction(onClick = onWorkLogs, modifier = Modifier.heightIn(min = 48.dp).testTag("log-work")) { Text("Log Work", style = MaterialTheme.typography.bodyLarge, fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold) }
                }
                workLogState.rows.forEach { row ->
                    FlatPanel {
                        Text("${row.minutes} min", style = MaterialTheme.typography.titleSmall)
                        row.note?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                        Text(shopDateOnly(row.createdAt), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                job.description?.takeIf { it.isNotBlank() }?.let { note ->
                    FlatPanel {
                        CardHeading("Initial notes")
                        Text(note, style = MaterialTheme.typography.bodyLarge)
                        Text(shopDateOnly(job.createdAt), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                au.mainspring.nativeapp.ui.CustomFieldsCard(au.mainspring.nativeapp.CustomFieldJobKind.Watch, job.id, alwaysOpen = true)
                FlatPanel {
                    CardHeading("Shop notes")
                    val notes = job.internalNotes?.takeIf { it.isNotBlank() }
                    if (notes != null) Text(notes, style = MaterialTheme.typography.bodyMedium)
                    else Text("No internal notes yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    SecondaryAction(onClick = { newNoteDraft = ""; addNoteOpen = true }, enabled = !state.noteBusy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Add shop note") }
                }
            }
            "attachments" -> {
                if(LocalCalibre.current) JobHeroPhoto("watch", shownId, known = state.attachments.takeIf { !state.loading }, onClick = onPhotos)
                var sortByName by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf(false) }
                var sortReversed by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf(false) }
                var sortMenu by remember { mutableStateOf(false) }
                var orderMenu by remember { mutableStateOf(false) }
                val files = state.attachments.let { list ->
                    val sorted = if (sortByName) list.sortedBy { (it.fileName ?: it.storageKey).lowercase() } else list.sortedBy { it.createdAt }
                    // Newest / Z-A is the default (descending); the other option flips it.
                    if (sortReversed) sorted else sorted.reversed()
                }
                Text(if (state.attachments.size == 1) "1 file loaded" else "${state.attachments.size} files loaded", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box {
                        SecondaryAction(onClick = { sortMenu = true }, modifier = Modifier.heightIn(min = 44.dp).testTag("attachments-sort"), contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)) {
                            Text("Sort: " + if (sortByName) "Name" else "Date"); Spacer(Modifier.width(6.dp)); Text("▾")
                        }
                        DropdownMenu(sortMenu, { sortMenu = false }) {
                            DropdownMenuItem(text = { Text("Sort: Date") }, onClick = { sortByName = false; sortMenu = false })
                            DropdownMenuItem(text = { Text("Sort: Name") }, onClick = { sortByName = true; sortMenu = false })
                        }
                    }
                    Box {
                        SecondaryAction(onClick = { orderMenu = true }, modifier = Modifier.heightIn(min = 44.dp).testTag("attachments-order"), contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)) {
                            Text(if (sortReversed) "Oldest / A-Z" else "Newest / Z-A"); Spacer(Modifier.width(6.dp)); Text("▾")
                        }
                        DropdownMenu(orderMenu, { orderMenu = false }) {
                            DropdownMenuItem(text = { Text("Newest / Z-A") }, onClick = { sortReversed = false; orderMenu = false })
                            DropdownMenuItem(text = { Text("Oldest / A-Z") }, onClick = { sortReversed = true; orderMenu = false })
                        }
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SecondaryAction(onClick = onPhotos, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("take-extra-photo"), contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp)) {
                        LineIcon("camera", androidx.compose.material3.LocalContentColor.current, 18.dp); Spacer(Modifier.width(8.dp)); Text("Take Extra Photo", maxLines = 1)
                    }
                    AccentAction(onClick = onPhotos, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("upload-file")) {
                        LineIcon("upload", androidx.compose.material3.LocalContentColor.current, 18.dp); Spacer(Modifier.width(8.dp)); Text("Upload File", maxLines = 1, fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold)
                    }
                }
                if (state.attachments.isEmpty() && !state.loading) Column(Modifier.fillMaxWidth().padding(vertical = 32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    LineIcon("upload", MaterialTheme.colorScheme.error, 32.dp)
                    Text("No attachments yet. Upload photos or documents.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                }
                if (state.loading && state.attachments.isEmpty()) Text("Loading…", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (state.attachments.isNotEmpty()) FlatPanel {
                    CardHeading("Photos & files / ${state.attachments.size}")
                    files.forEach { att ->
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
                }
            }
            "money" -> {
                SummaryCard("Quotes & invoicing", listOfNotNull(job.depositCents.takeIf { it > 0 }?.let { "${formatCents(it, currency)} deposit" }, job.preQuoteCents.takeIf { it > 0 }?.let { "${formatCents(it, currency)} pre-quote" }).joinToString(" · ").ifBlank { "No charges recorded yet" },
                    "View charges or record payment", { onQuotes(shownId) })
                FlatPanel {
                    Text("Balance", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(formatCents(state.outstandingCents(job), currency) + " outstanding", style = MaterialTheme.typography.titleMedium)
                    if (state.invoiceTotalCents > 0) Text("Invoiced ${formatCents(state.invoiceTotalCents, currency)} · paid ${formatCents(state.invoicePaidCents, currency)}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    else Text("No invoice raised yet", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if(TokenStore.canManageInvoices()) SecondaryAction(onClick = { onQuotes(shownId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("job-quote-payment")) {
                    Text(if(state.outstandingCents(job) > 0 && state.invoiceTotalCents > 0) "Take payment" else "Quote & payment")
                }
                if(LocalCalibre.current && job.status == "awaiting_collection") {
                    val outstandingCents = state.outstandingCents(job)
                    val paid = outstandingCents == 0
                    FlatPanel {
                        CardHeading(if(paid) "Payment recorded" else "Check before handing over")
                        CalibreCheckRow(true, "Service complete", "Repair has reached ${statusLabel(job.status).lowercase()}")
                        CalibreCheckRow(state.smsLog.isNotEmpty(), if(state.smsLog.isNotEmpty()) "Customer notified" else "Customer not yet notified",
                            if(state.smsLog.isNotEmpty()) "${state.smsLog.size} ${if(state.smsLog.size == 1) "message" else "messages"} sent" else "No message logged for this job")
                        CalibreCheckRow(paid, if(paid) "Payment verified" else "Payment not yet verified", if(paid) null else "Balance outstanding")
                        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                        Column(Modifier.padding(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            MonoLabel(if(paid) "Payment recorded" else "Outstanding")
                            Text((if(currency == "AUD") String.format(java.util.Locale.US, "A$%.2f", outstandingCents / 100.0) else formatCents(outstandingCents, currency)) + if(paid) " outstanding" else "", style = MaterialTheme.typography.headlineMedium, color = MaterialTheme.colorScheme.onSurface)
                            if(paid) Text("Payment does not close the job. Confirm collection only when the customer receives the watch.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        AccentAction(onClick = { onQuotes(shownId) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Open invoice & payment") }
                    }
                }
            }
            else -> {
                FlatPanel {
                    CardHeading("Job ticket")
                    Text(shopDateOnly(job.createdAt), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(job.title, style = MaterialTheme.typography.titleMedium)
                    job.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    DashedDivider(Modifier.padding(vertical = 4.dp))
                    TicketRow("Job #", job.jobNumber.removePrefix("#").let { "#$it" }, mono = true)
                    TicketRow("Status", watchStatusLabel(job.status), pillStatus = job.status)
                    job.collectionDate?.takeIf { it.isNotBlank() }?.let { TicketRow("Due", formatShopDate(it)) }
                    job.partsEta?.takeIf { it.isNotBlank() }?.let { TicketRow("Parts", formatShopDate(it)) }
                    TicketRow("Created", shopDateOnly(job.createdAt))
                }
                FlatPanel {
                    CardHeading("Customer & contact")
                    Text(job.customerName ?: "No customer recorded", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    val phone = job.customerPhone?.takeIf { it.isNotBlank() }
                    val email = job.customerEmail?.takeIf { it.isNotBlank() }
                    if (job.customerAccountId != null) Text("Business account linked", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (phone == null && email == null) Text("No phone or email on file", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    phone?.let { p -> TextButton(onClick = { contactError = launchContact(context, Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + p.filter { c -> c.isDigit() || c == '+' }))) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Call $p") } }
                    email?.let { e -> TextButton(onClick = { contactError = launchContact(context, Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:" + Uri.encode(e)))) }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Email $e") } }
                    contactError?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
                }
                state.watch?.let { w ->
                    val details = listOf("Brand" to w.brand, "Model" to w.model, "Serial" to w.serialNumber, "Movement" to w.movementType, "Condition" to w.conditionNotes)
                        .filter { !it.second.isNullOrBlank() }
                    if (details.isNotEmpty()) FlatPanel {
                        CardHeading("Watch details")
                        details.forEach { (label, value) -> DetailRow(label, value.orEmpty()) }
                    }
                }
                FlatPanel {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Assigned to", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            val assignedName = job.assignedUserId?.let { id -> state.users.firstOrNull { it.id == id }?.name ?: job.claimedByName ?: if (id == TokenStore.currentUserId()) "You" else "Assigned" }
                            Text(assignedName ?: job.claimedByName ?: "Nobody yet", style = MaterialTheme.typography.titleMedium)
                        }
                        if (job.claimedByName == null) SecondaryAction(onClick = { vm.claimJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "…" else "Claim for me") }
                        else SecondaryAction(onClick = { vm.releaseJob() }, enabled = !state.claimBusy, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (state.claimBusy) "…" else "Release") }
                    }
                }
                FlatPanel {
                    CardHeading("Repair activity")
                    if (state.history.isEmpty() && state.smsLog.isEmpty()) Text("No activity recorded yet.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    state.history.forEach { h ->
                        ActivityCard(statusLabel(h.newStatus), h.changeNote?.takeIf { it.isNotBlank() } ?: h.oldStatus?.let { "From ${statusLabel(it)}" }, formatShopDate(h.createdAt))
                    }
                    state.smsLog.forEach { log -> ActivityCard(statusLabel(log.event), "${statusLabel(log.status)} · ${log.body}", "${log.toPhone} · ${formatShopDate(log.createdAt)}") }
                    Text("Activity includes status changes, approvals, photos and private workshop notes. Customer-visible conversations are in Messages.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }

    if (confirmDelete) DeleteJobDialog(job?.let { "${it.jobNumber} · ${it.title}" } ?: "this job", { confirmDelete = false; vm.deleteJob() }, { confirmDelete = false })
    if (confirmDuplicate) DuplicateJobDialog({ confirmDuplicate = false; vm.duplicateJob() }, { confirmDuplicate = false })
    if (accountPicker) AccountPickerDialog(state.accounts, state.accountsLoading, state.watch?.customerId, job?.customerAccountId,
        { id -> accountPicker = false; vm.assignAccount(id) }, { accountPicker = false })

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
                        onValueChange = { statusCustomerNote = it.take(JobDetailViewModel.CUSTOMER_NOTE_MAX) },
                        label = { Text("Note for customer (optional)") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = false,
                        maxLines = 3,
                    )
                    Text("Shown on their status page \u00b7 ${statusCustomerNote.length}/${JobDetailViewModel.CUSTOMER_NOTE_MAX}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(8.dp))
                    watchPickerOptions(job?.status).forEach { s ->
                        val current = s == job?.status
                        TextButton(
                            onClick = {
                                vm.setStatus(s, statusChangeNote.trim().takeIf { t -> t.isNotEmpty() }, statusCustomerNote.trim().takeIf { t -> t.isNotEmpty() })
                                statusChangeNote = ""; statusCustomerNote = ""
                                statusPicker = false
                            },
                            enabled = !current,
                            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
                        ) { Text(watchStatusLabel(s) + if (current) " (current)" else "", Modifier.fillMaxWidth()) }
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

    if (assignPicker) {
        AlertDialog(
            onDismissRequest = { assignPicker = false },
            title = { Text("Assign technician") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    if (state.usersLoading) LinearProgressIndicator(Modifier.fillMaxWidth())
                    if (!state.usersLoading && state.users.isEmpty()) Text("No team members loaded.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    state.users.forEach { u ->
                        val current = u.id == job?.assignedUserId
                        TextButton(onClick = { vm.assignTechnician(u.id); assignPicker = false }, enabled = !current, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                            Text(u.name + if (current) " (assigned)" else "", Modifier.fillMaxWidth())
                        }
                    }
                    if (job?.assignedUserId != null) TextButton(onClick = { vm.assignTechnician(null); assignPicker = false }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Unassign", Modifier.fillMaxWidth()) }
                }
            },
            confirmButton = { TextButton(onClick = { assignPicker = false }) { Text("Close") } },
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

/** Starts an external call/email intent; returns an error message when no app can handle it. */
internal fun launchContact(context: android.content.Context, intent: Intent): String? =
    try { context.startActivity(intent); null } catch (e: android.content.ActivityNotFoundException) { "No app available to handle this." }

/** The web shows the quote as "$95.00" (no currency suffix) for AUD shops; other currencies keep the suffix. */
internal fun webMoney(cents: Int, currency: String): String =
    if (currency == "AUD") String.format(java.util.Locale.US, "$%.2f", cents / 100.0) else formatCents(cents, currency)

/** Shop-timezone date without the time of day, as the web's job header and ticket show it. */
internal fun shopDateOnly(value: String): String = formatShopDate(value).substringBefore(' ')

/** Phone-first tab set shared by the watch and shoe job details: counts are shown only when non-zero. */
internal fun detailTabs(photos: Int, events: Int): List<Pair<String, String>> = listOf(
    "overview" to "Details",
    "work" to "Work Logs",
    "attachments" to if (photos > 0) "Attachments $photos" else "Attachments",
    "money" to "Money",
    "messages" to "Messages",
)

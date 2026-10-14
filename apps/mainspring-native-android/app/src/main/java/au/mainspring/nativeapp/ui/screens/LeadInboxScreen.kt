package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.InboundLead
import au.mainspring.nativeapp.ui.*
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.temporal.ChronoUnit

private fun leadAge(createdAt: String?): String {
    val days = try {
        val created = runCatching { OffsetDateTime.parse(createdAt!!).toLocalDate() }.getOrElse { LocalDate.parse(createdAt!!.take(10)) }
        ChronoUnit.DAYS.between(created, LocalDate.now()).coerceAtLeast(0)
    } catch(_: Exception) { return "" }
    return if(days == 0L) "Today" else "${days}d old"
}

private fun leadMeta(lead: InboundLead): String = listOfNotNull(
    lead.suburbName?.takeIf { it.isNotBlank() } ?: lead.address?.takeIf { it.isNotBlank() },
    lead.category?.takeIf { it.isNotBlank() },
    if(lead.source == "website_lead") "Website" else null,
    leadAge(lead.createdAt).takeIf { it.isNotBlank() },
).joinToString(" · ")

@Composable fun LeadInboxScreen(onOpenAccount: (String) -> Unit = {}, embedded: Boolean = true, viewModel: LeadsViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var adding by rememberSaveable { mutableStateOf(false) }
    var expanded by rememberSaveable { mutableStateOf<String?>(null) }
    var confirmConvert by remember { mutableStateOf<InboundLead?>(null) }
    LaunchedEffect(state.convertedAccountId) { state.convertedAccountId?.let { onOpenAccount(it); viewModel.consumeConverted() } }
    val stageTabs = listOf<Pair<String?, String>>(null to "Active") + LEAD_PIPELINE
    Column(Modifier.fillMaxSize().then(if(embedded) Modifier else Modifier.statusBarsPadding())) {
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(22.dp)) {
            stageTabs.forEach { (key, label) ->
                val count = if(key == null) state.all.count { it.status != "won" && it.status != "lost" } else state.counts[key] ?: 0
                TabChip(state.stage == key, { viewModel.selectStage(key) }, label = { Text("$label $count") })
            }
        }
        HorizontalDivider(Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.outlineVariant)
        if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        state.error?.let { ErrorBanner(it, Modifier.padding(horizontal = 20.dp, vertical = 8.dp), onRetry = viewModel::refresh) }
        LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp)) {
            item {
                Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    if(state.overdue > 0) StatusPill("overdue") else Spacer(Modifier.width(1.dp))
                    if(state.overdue > 0) Text(" ${state.overdue} follow-up${if(state.overdue != 1) "s" else ""} overdue", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.weight(1f))
                    PrimaryAction({ adding = true }, Modifier.heightIn(min = 44.dp)) { Text("+ New lead") }
                }
            }
            if(state.shown.isEmpty() && !state.loading && state.error == null) item {
                EmptyState("No leads here", "Add inbound calls and enquiries so they don't slip through.")
            }
            items(state.shown, key = { it.id }) { lead ->
                LeadRow(lead, expanded == lead.id, state.busyId == lead.id, { expanded = if(expanded == lead.id) null else lead.id },
                    onStatus = { viewModel.setStatus(lead, it) }, onFollowUp = { viewModel.followUpIn(lead, it) },
                    onSaveNotes = { viewModel.saveNotes(lead, it) }, onConvert = { confirmConvert = lead }, onOpenAccount = onOpenAccount)
            }
        }
    }
    confirmConvert?.let { lead ->
        AlertDialog(onDismissRequest = { confirmConvert = null }, title = { Text("Convert to account?") },
            text = { Text("Create a business account named \"${lead.name}\" from this lead.") },
            confirmButton = { PrimaryAction({ viewModel.convert(lead); confirmConvert = null }) { Text("Convert") } },
            dismissButton = { TextButton({ confirmConvert = null }) { Text("Cancel") } })
    }
    if(adding) AddLeadDialog(state.adding, { adding = false }) { name, phone, suburb, notes, status -> viewModel.add(name, phone, suburb, notes, status) { adding = false } }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable private fun LeadRow(
    lead: InboundLead, expanded: Boolean, busy: Boolean, onToggle: () -> Unit, onStatus: (String) -> Unit, onFollowUp: (Long) -> Unit,
    onSaveNotes: (String) -> Unit, onConvert: () -> Unit, onOpenAccount: (String) -> Unit,
) {
    val overdue = lead.isOverdueFollowUp()
    val uri = LocalUriHandler.current
    Column(Modifier.fillMaxWidth()) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Column(Modifier.fillMaxWidth().clickable(onClick = onToggle).padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text(lead.name, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                StatusPill(if(overdue) "overdue" else lead.status)
            }
            leadMeta(lead).takeIf { it.isNotBlank() }?.let { MonoLabel(it) }
            listOfNotNull(lead.phone?.takeIf { it.isNotBlank() }, lead.contactName?.takeIf { it.isNotBlank() }).joinToString(" · ").takeIf { it.isNotBlank() }
                ?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            lead.nextFollowUpOn?.takeIf { it.isNotBlank() }?.let {
                MonoLabel((if(overdue) "Due " else "Follow-up ") + formatShopDate(it), color = if(overdue) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        if(expanded) Column(Modifier.fillMaxWidth().padding(bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            lead.phone?.takeIf { it.isNotBlank() }?.let { phone -> LinkAction({ uri.openUri("tel:" + phone.filter { c -> !c.isWhitespace() }) }) { Text("Call $phone") } }
            lead.contactEmail?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            MonoLabel("Stage")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                LEAD_STATUS_OPTIONS.forEach { (key, label) -> TabChip(lead.status == key, { if(lead.status != key) onStatus(key) }, label = { Text(label) }, enabled = !busy) }
            }
            MonoLabel("Follow-up")
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                listOf(1L to "Tomorrow", 3L to "In 3 days", 7L to "In a week").forEach { (days, label) -> LinkAction({ onFollowUp(days) }, enabled = !busy) { Text(label) } }
            }
            var notes by rememberSaveable(lead.id, lead.notes) { mutableStateOf(lead.notes.orEmpty()) }
            AtelierTextField(notes, { notes = it }, Modifier.fillMaxWidth(), label = { Text("Notes") }, minLines = 2, maxLines = 5, enabled = !busy)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                if(notes.trim() != lead.notes.orEmpty().trim()) SecondaryAction({ onSaveNotes(notes) }, enabled = !busy) { Text("Save notes") }
                if(lead.customerAccountId == null) PrimaryAction(onConvert, enabled = !busy) { Text(if(busy) "Working…" else "Convert to account") }
                else PrimaryAction({ onOpenAccount(lead.customerAccountId) }) { Text("View account") }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable private fun AddLeadDialog(busy: Boolean, onDismiss: () -> Unit, onSave: (String, String, String, String, String) -> Unit) {
    var name by rememberSaveable { mutableStateOf("") }; var phone by rememberSaveable { mutableStateOf("") }
    var suburb by rememberSaveable { mutableStateOf("") }; var notes by rememberSaveable { mutableStateOf("") }
    var status by rememberSaveable { mutableStateOf("new") }
    AlertDialog(onDismissRequest = { if(!busy) onDismiss() }, title = { Text("New inbound lead") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                AtelierTextField(name, { name = it }, Modifier.fillMaxWidth(), label = { Text("Name / business") }, singleLine = true, enabled = !busy)
                AtelierTextField(phone, { phone = it }, Modifier.fillMaxWidth(), label = { Text("Phone") }, singleLine = true, enabled = !busy,
                    keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Phone))
                AtelierTextField(suburb, { suburb = it }, Modifier.fillMaxWidth(), label = { Text("Suburb") }, singleLine = true, enabled = !busy)
                AtelierTextField(notes, { notes = it }, Modifier.fillMaxWidth(), label = { Text("Notes") }, minLines = 2, maxLines = 4, enabled = !busy)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    LEAD_PIPELINE.forEach { (key, label) -> TabChip(status == key, { status = key }, label = { Text(label) }, enabled = !busy) }
                }
            }
        },
        confirmButton = { PrimaryAction({ onSave(name, phone, suburb, notes, status) }, enabled = !busy && name.isNotBlank()) { Text(if(busy) "Saving…" else "Add lead") } },
        dismissButton = { TextButton(onDismiss, enabled = !busy) { Text("Cancel") } })
}


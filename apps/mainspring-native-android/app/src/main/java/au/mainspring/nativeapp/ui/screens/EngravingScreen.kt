package au.mainspring.nativeapp.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.*
import com.google.gson.JsonObject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun EngravingScreen(onBack: () -> Unit, vm: EngravingViewModel = viewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    val event = s.queue?.event
    val orders = s.queue?.orders.orEmpty()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val owner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    var eventForm by remember { mutableStateOf(false) }
    var walkUp by remember { mutableStateOf(false) }
    var qr by remember { mutableStateOf(false) }
    var filter by rememberSaveable { mutableStateOf("active") }
    var query by rememberSaveable { mutableStateOf("") }
    var software by rememberSaveable { mutableStateOf("xtool") }
    var exportLimit by rememberSaveable { mutableStateOf("") }
    var pending by remember { mutableStateOf<Pair<String, () -> Unit>?>(null) }
    var editing by remember { mutableStateOf<EngravingOrder?>(null) }
    val enabled = !s.loading && !s.busy && !s.unknown && TokenStore.canWorkJobs()
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        if(uri != null) scope.launch { try {
            val limit = exportLimit.toIntOrNull(); require(exportLimit.isBlank() || limit != null && limit in 1..500) { "Export between 1 and 500 medals, or leave the limit blank." }
            val data = vm.export(software, limit)
            withContext(Dispatchers.IO) { context.contentResolver.openOutputStream(uri)?.use { it.write(data) } ?: error("Could not save export.") }
        } catch(e: Exception) { vm.error(e.userMessage()) } }
    }
    LaunchedEffect(owner) { owner.lifecycle.repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) { while(true) { kotlinx.coroutines.delay(8_000); vm.refresh() } } }
    fun printSign(e: EngravingEvent) { try { printCommunityPages(context, "${e.name} engraving", listOf(IntakeTicketCopy("Medal engraving", e.name, listOf("Price per medal" to formatCents(e.price, (TokenStore.shopValue("currency") ?: "AUD")), "Ordering" to "Scan to order. We will tell you when it is ready.", "Location" to e.location.orEmpty()), "Scan to order engraving") to e.publicUrl)) } catch(ex: Exception) { vm.error(ex.userMessage()) } }
    fun printTicket(o: EngravingOrder) {
        val e = event ?: return
        val members = orders.filter { it.id == o.id || o.group != null && it.group == o.group }
        val origin = au.mainspring.nativeapp.api.ApiClient.getEffectiveBaseUrl().trimEnd('/')
        try { printCommunityPages(context, "Tub ticket ${o.number}", listOf(IntakeTicketCopy("Engraving ${o.ticket ?: o.number}", e.name,
            members.map { it.number to "${it.athlete} · ${it.line2.orEmpty()} · ${it.place} ×${it.qty}" } + listOf("Payment" to if(members.all { it.paid }) "Paid" else "Payment outstanding"), "Scan for order status") to "$origin/engrave/o/${o.token}")) }
        catch(ex: Exception) { vm.error(ex.userMessage()) }
    }
    Scaffold(topBar = { AtelierTopAppBar(title = { Text(event?.name ?: "Medal engraving") }, navigationIcon = { BackButton(onClick = { if(event == null) onBack() else vm.open(null) }) }, actions = { TextButton(vm::refresh, enabled = !s.loading && !s.busy) { Text("Refresh") } }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("engraving-content"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                if(s.loading || s.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                s.error?.let { ErrorBanner(it) }
                if(s.unknown) {
                    Text("An earlier action needs review. Refresh and check the orders before repeating it.")
                    TextButton(vm::reviewedUnknown, enabled = s.reviewed && !s.busy) { Text("I have reviewed the current records") }
                }
            }
            if(event == null) {
                item { Button({ eventForm = true }, enabled = enabled) { Text("New engraving event") } }
                if(s.events.isEmpty() && !s.loading) item { EmptyState("No events yet", "Create an event to take medal orders and run the engraving queue.") }
                items(s.events, key = { it.id }) { e -> FlatPanel {
                    Text(e.name, style = MaterialTheme.typography.titleLarge)
                    Text(listOfNotNull(e.date?.let { formatShopDate(it) }, e.location).joinToString(" · "))
                    Text("${e.status} · ${formatCents(e.price, (TokenStore.shopValue("currency") ?: "AUD"))} per medal")
                    Text("${e.stats["medals_remaining"] ?: 0} medals remaining · ${e.stats["waiting"] ?: 0} waiting")
                    Row { TextButton({ vm.open(e.id) }) { Text("Open queue") }; TextButton({ printSign(e) }) { Text("Print QR sign") } }
                } }
            } else {
                item {
                    Text("${event.status} · ${event.minutes} minutes per medal · ${formatCents(event.price, (TokenStore.shopValue("currency") ?: "AUD"))}", style = MaterialTheme.typography.bodyMedium)
                    Text("Waiting ${event.stats["waiting"] ?: 0} · Engraving ${event.stats["engraving"] ?: 0} · Ready ${event.stats["ready"] ?: 0} · Collected ${event.stats["collected"] ?: 0}")
                    Text("Paid ${formatCents(event.stats["paid_cents"] ?: 0, (TokenStore.shopValue("currency") ?: "AUD"))} · Unpaid ${formatCents(event.stats["unpaid_cents"] ?: 0, (TokenStore.shopValue("currency") ?: "AUD"))}")
                    if(event.online && !event.onlineReady) Text("Online card payments are not ready. Customers can pay at the stall.")
                    Row(Modifier.horizontalScroll(rememberScrollState())) {
                        Button({ walkUp = true }, enabled = enabled && event.status != "closed") { Text("Walk-up order") }
                        TextButton({ qr = true }) { Text("QR sign") }; TextButton({ eventForm = true }, enabled = enabled) { Text("Event settings") }
                        TextButton({ pending = (if(event.status == "open") "Pause orders?" else "Open orders?") to { vm.status(if(event.status == "open") "paused" else "open") } }, enabled = enabled) { Text(if(event.status == "open") "Pause" else "Open") }
                        if(event.status != "closed") TextButton({ pending = "Close this event to new orders?" to { vm.status("closed") } }, enabled = enabled) { Text("Close event") }
                    }
                }
                val current = orders.firstOrNull { it.status == "engraving" }
                val next = orders.firstOrNull { it.status == "waiting" }
                if(current != null) item { FlatPanel {
                    SectionLabel("NOW ENGRAVING · ${current.number}")
                    MedalPreview(current.athlete, current.line2.orEmpty(), current.place)
                    Text("Medal ${minOf(current.done + 1, current.qty)} of ${current.qty}")
                    Button({ vm.action(current, "medal-done") }, enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("engraving-medal-done")) { Text(if(current.done + 1 >= current.qty) "Done — order ready" else "Done — next medal") }
                    TextButton({ vm.update(current, JsonObject().apply { addProperty("status", "waiting") }) }, enabled = enabled) { Text("Skip for now") }
                } } else if(next != null) item { Button({ vm.action(next, "start") }, enabled = enabled) { Text("Start ${next.number} · ${next.athlete}") } }
                item {
                    OutlinedTextField(query, { query = it }, label = { Text("Order, ticket, name or last four of phone") }, modifier = Modifier.fillMaxWidth())
                    Row { listOf("active", "ready", "all").forEach { key -> FilterChip(filter == key, { filter = key }, label = { Text(key.replaceFirstChar { it.uppercase() }) }) } }
                }
                items(orders.filter { o -> (filter == "all" || filter == "active" && o.status in listOf("waiting", "engraving") || filter == "ready" && o.status == "ready") && (query.isBlank() || "${o.number} ${o.ticket.orEmpty()} ${o.athlete} ${o.phone?.takeLast(4).orEmpty()}".contains(query, true)) }, key = { it.id }) { o ->
                    FlatPanel {
                        Text("${o.ticket?.let { "Ticket $it · " }.orEmpty()}${o.number} · ${o.athlete}", style = MaterialTheme.typography.titleMedium)
                        Text(listOfNotNull(o.line2, o.place.takeIf { it != "None" }, "${o.done}/${o.qty} medals").joinToString(" · "))
                        Text("${o.status} · ${if(o.paid) "Paid" else "Unpaid"} ${formatCents(o.amount, (TokenStore.shopValue("currency") ?: "AUD"))}")
                        o.smsStatus?.let { Text(when(it) { "sent" -> "Ready text sent"; "failed" -> "Ready text failed"; "dry_run" -> "Ready text simulated"; else -> "Ready text skipped" }) }
                        o.notes?.let { Text(it) }
                        Row(Modifier.horizontalScroll(rememberScrollState())) {
                            if(o.status == "waiting") TextButton({ vm.action(o, "start") }, enabled = enabled) { Text("Start") }
                            if(o.status != "cancelled") TextButton({ pending = "${if(o.paid) "Mark unpaid" else "Record stall payment"} for ${o.number}?" to { vm.update(o, JsonObject().apply { addProperty("paid", !o.paid) }) } }, enabled = enabled) { Text(if(o.paid) "Mark unpaid" else "Mark paid") }
                            if(o.status == "ready") {
                                TextButton({ pending = "Collect ${o.number} and confirm payment?" to { vm.update(o, JsonObject().apply { addProperty("status", "collected"); addProperty("paid", true) }) } }, enabled = enabled) { Text("Collected") }
                                if(o.group != null && orders.count { it.group == o.group && it.status == "ready" } > 1) TextButton({ pending = "Collect all ready medals in this group and confirm payment?" to { vm.collectGroup(o) } }, enabled = enabled) { Text("Collect group") }
                                if(!o.phone.isNullOrBlank()) TextButton({ pending = "Resend ready text for ${o.number}?" to { vm.action(o, "resend-ready") } }, enabled = enabled) { Text("Resend text") }
                            }
                            if(o.status in listOf("waiting", "engraving")) TextButton({ pending = "Cancel ${o.number}?" to { vm.update(o, JsonObject().apply { addProperty("status", "cancelled") }) } }, enabled = enabled) { Text("Cancel") }
                            if(o.status in listOf("ready", "collected", "cancelled")) TextButton({ pending = "Put ${o.number} back in the queue?" to { vm.update(o, JsonObject().apply { addProperty("status", "waiting") }) } }, enabled = enabled) { Text("Re-engrave") }
                            TextButton({ editing = o }, enabled = enabled) { Text("Edit") }
                            TextButton({ printTicket(o) }) { Text("Print tub ticket") }
                        }
                    }
                }
                item { FlatPanel {
                    SectionLabel("EXPORT FOR LASER")
                    Row(Modifier.horizontalScroll(rememberScrollState())) { listOf("xtool", "lightburn", "ezcad2", "csv").forEach { key -> FilterChip(software == key, { software = key }, label = { Text(key) }) } }
                    OutlinedTextField(exportLimit, { exportLimit = it.filter(Char::isDigit) }, label = { Text("Medal limit (optional)") }, modifier = Modifier.fillMaxWidth())
                    TextButton({ export.launch("engraving-$software.${if(software == "ezcad2") "zip" else "csv"}") }, enabled = !s.busy) { Text("Save laser file") }
                } }
            }
        }
    }
    pending?.let { (title, action) -> AlertDialog(onDismissRequest = { pending = null }, title = { Text(title) }, confirmButton = { TextButton({ pending = null; action() }) { Text("Confirm") } }, dismissButton = { TextButton({ pending = null }) { Text("Cancel") } }) }
    if(eventForm) EngravingForm(event, null, s.busy, { eventForm = false }, { fields -> vm.saveEvent(event?.id, fields) { eventForm = false } }, serverError = s.error, blocked = s.unknown)
    if(walkUp) EngravingForm(null, null, s.busy, { walkUp = false }, { fields -> vm.order(fields) { walkUp = false } }, orderMode = true, serverError = s.error, blocked = s.unknown)
    editing?.let { o -> EngravingForm(null, o, s.busy, { editing = null }, { fields -> vm.update(o, fields) { editing = null } }, orderMode = true, serverError = s.error, blocked = s.unknown) }
    if(qr && event != null) AlertDialog(onDismissRequest = { qr = false }, title = { Text("${event.name} · Scan to order") }, text = { Column { QrPreview(event.publicUrl); Text(event.publicUrl) } }, confirmButton = { TextButton({ printSign(event) }) { Text("Print sign") } }, dismissButton = { TextButton({ qr = false }) { Text("Close") } })
}

@Composable private fun MedalPreview(name: String, line2: String, place: String) {
    Surface(Modifier.fillMaxWidth().padding(8.dp), shape = androidx.compose.foundation.shape.CircleShape, color = Color(0xFFF3D791)) {
        Column(Modifier.padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally) { Text(name.ifBlank { "Athlete name" }, style = MaterialTheme.typography.titleLarge); Text(line2); if(place != "None") Text(if(place == "Participant") place else "$place Place") }
    }
}
@Composable private fun QrPreview(url: String) {
    val matrix = remember(url) { QrCode.encode(url) }
    Canvas(Modifier.size(240.dp)) { val cell = size.width / (matrix.size + 8); drawRect(Color.White); for(r in matrix.indices) for(c in matrix.indices) if(matrix[r][c]) drawRect(Color.Black, Offset((c + 4) * cell, (r + 4) * cell), Size(cell, cell)) }
}

@Composable private fun EngravingForm(event: EngravingEvent?, order: EngravingOrder?, busy: Boolean, close: () -> Unit,
    save: (JsonObject) -> Unit, orderMode: Boolean = false, serverError: String? = null, blocked: Boolean = false) {
    var name by rememberSaveable { mutableStateOf(if(orderMode) order?.athlete.orEmpty() else event?.name.orEmpty()) }
    var second by rememberSaveable { mutableStateOf(if(orderMode) order?.line2.orEmpty() else event?.location.orEmpty()) }
    var date by rememberSaveable { mutableStateOf(event?.date?.let { formatShopDate(it) }.orEmpty()) }
    var price by rememberSaveable { mutableStateOf(event?.price?.let { "%.2f".format(java.util.Locale.US, it / 100.0) } ?: "15.00") }
    var minutes by rememberSaveable { mutableStateOf(event?.minutes?.toString() ?: "3") }
    var qty by rememberSaveable { mutableStateOf(order?.qty?.toString() ?: "1") }
    var place by rememberSaveable { mutableStateOf(order?.place ?: "1st") }
    var phone by rememberSaveable { mutableStateOf(order?.phone.orEmpty()) }
    var notes by rememberSaveable { mutableStateOf(order?.notes.orEmpty()) }
    var paid by rememberSaveable { mutableStateOf(order?.paid ?: true) }
    var sms by rememberSaveable { mutableStateOf(event?.sms ?: true) }
    var online by rememberSaveable { mutableStateOf(event?.online ?: true) }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(onDismissRequest = { if(!busy) close() }, title = { Text(if(orderMode) if(order == null) "Walk-up order" else "Edit order" else if(event == null) "New engraving event" else "Event settings") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if(orderMode) MedalPreview(name, second, place)
            OutlinedTextField(name, { if(!orderMode || it.length <= 24) name = it }, label = { Text(if(orderMode) "Athlete’s name" else "Event name") }, enabled = !busy)
            OutlinedTextField(second, { if(!orderMode || it.length <= 28) second = it }, label = { Text(if(orderMode) "Second line" else "Location") }, enabled = !busy)
            if(orderMode) {
                Row(Modifier.horizontalScroll(rememberScrollState())) { listOf("1st", "2nd", "3rd", "Participant", "None").forEach { p -> FilterChip(place == p, { place = p }, label = { Text(p) }) } }
                OutlinedTextField(qty, { qty = it }, label = { Text("Medals (1–20)") }, enabled = !busy)
                OutlinedTextField(phone, { phone = it }, label = { Text("Mobile for ready text") }, enabled = !busy)
                OutlinedTextField(notes, { notes = it }, label = { Text("Notes") }, enabled = !busy)
                Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(paid, { paid = it }, enabled = !busy); Text("Paid at stall") }
            } else {
                OutlinedTextField(date, { date = it }, label = { Text("Date (DD/MM/YYYY)") }, enabled = !busy)
                OutlinedTextField(price, { price = it }, label = { Text("Price per medal ($)") }, enabled = !busy)
                OutlinedTextField(minutes, { minutes = it }, label = { Text("Minutes per medal") }, enabled = !busy)
                Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(sms, { sms = it }, enabled = !busy); Text("Text when ready") }
                Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(online, { online = it }, enabled = !busy); Text("Allow online card payments") }
            }
            error?.let { ErrorBanner(it) }
            serverError?.let { ErrorBanner(it) }
            if(blocked) Text("Close this form, refresh and review the current records before repeating the action.")
        }
    }, confirmButton = { TextButton({ try {
        require(name.isNotBlank()) { "Enter a name." }
        val body = JsonObject()
        if(orderMode) {
            val count = qty.toIntOrNull(); require(count != null && count in 1..20) { "Medals must be between 1 and 20." }
            body.addProperty("athlete_name", name.trim()); body.addProperty("line2", second.trim().ifBlank { null }); body.addProperty("place", place); body.addProperty("qty", count); body.addProperty("phone", phone.trim().ifBlank { null }); body.addProperty("paid", paid); body.addProperty("notes", notes.trim().ifBlank { null })
        } else {
            val time = minutes.toIntOrNull(); require(time != null && time > 0) { "Enter positive minutes per medal." }
            body.addProperty("name", name.trim()); body.addProperty("location", second.trim().ifBlank { null }); body.addProperty("event_date", collectionDateIso(date)); body.addProperty("price_cents", dollarsToCentsChecked(price)); body.addProperty("minutes_per_medal", time); body.addProperty("sms_enabled", sms); body.addProperty("online_payments", online)
        }
        save(body)
    } catch(e: Exception) { error = e.userMessage() } }, enabled = !busy && !blocked && name.isNotBlank()) { Text(if(busy) "Saving…" else "Save") } }, dismissButton = { TextButton(close, enabled = !busy) { Text("Cancel") } })
}

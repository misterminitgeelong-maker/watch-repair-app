package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.*
import com.google.gson.Gson

@Composable private fun LocationChoices(label: String, locations: List<PartLocation>, selected: String, enabled: Boolean, onSelect: (String) -> Unit) {
    Text(label, style = MaterialTheme.typography.labelLarge)
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        locations.forEach { location -> FilterChip(selected == location.id, { onSelect(location.id) }, label = { Text(location.name) }, enabled = enabled) }
    }
}

@Composable private fun StockWriteReview(s: PartsState, vm: PartsViewModel) {
    if(s.unknown) {
        Text("An earlier stock action needs review. Refresh and check stock quantities, used parts and transfers before repeating it.")
        TextButton(vm::refresh, enabled = !s.loading && !s.busy) { Text("Refresh records") }
        TextButton(vm::reviewed, enabled = s.reviewed && !s.loading && !s.busy, modifier = Modifier.testTag("stock-reviewed")) { Text("I have reviewed the current records") }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun PartsStockScreen(onBack: () -> Unit, vm: PartsViewModel = viewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    var query by rememberSaveable { mutableStateOf("") }
    var lowOnly by rememberSaveable { mutableStateOf(false) }
    var location by rememberSaveable { mutableStateOf("") }
    var sku by rememberSaveable { mutableStateOf("") }
    var quantity by rememberSaveable { mutableStateOf("1") }
    var kind by rememberSaveable { mutableStateOf("receive") }
    var note by rememberSaveable { mutableStateOf("") }
    var from by rememberSaveable { mutableStateOf("") }
    var to by rememberSaveable { mutableStateOf("") }
    var sendSku by rememberSaveable { mutableStateOf("") }
    var sendQuantity by rememberSaveable { mutableStateOf("1") }
    var sendNote by rememberSaveable { mutableStateOf("") }
    var linesJson by rememberSaveable { mutableStateOf("[]") }
    val lines = remember(linesJson) { runCatching { Gson().fromJson(linesJson, Array<PartLineInput>::class.java).toList() }.getOrDefault(emptyList()) }
    var pending by remember { mutableStateOf<Pair<String, () -> Unit>?>(null) }
    val enabled = s.available && !s.busy && !s.loading && !s.unknown
    val myLocation = s.mine.firstOrNull { it.id == location }?.id ?: s.mine.firstOrNull()?.id.orEmpty()
    val fromLocation = s.mine.firstOrNull { it.id == from }?.id ?: s.mine.firstOrNull()?.id.orEmpty()
    RefreshOnResume(vm::refresh)
    Scaffold(topBar = { AtelierTopAppBar(title = { Text("Parts stock") }, navigationIcon = { BackButton(onClick = onBack) }, actions = { TextButton(vm::refresh, enabled = !s.loading && !s.busy) { Text("Refresh") } }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("parts-stock"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                if(s.loading || s.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                s.error?.let { ErrorBanner(it, onRetry = vm::refresh) }; s.info?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
                StockWriteReview(s, vm)
                if(!s.loading && !s.available && s.error == null) EmptyState("Parts stock is not enabled for this shop", "Your network must grant stock access and link a stock location.")
                else if(s.available && s.mine.isEmpty()) EmptyState("No stock location is linked", "Ask support to link this shop to a stock location.")
            }
            if(s.available) {
                if(s.incoming.isNotEmpty()) item { SectionLabel("ARRIVING") }
                items(s.incoming, key = { "incoming-${it.id}" }) { transfer ->
                    FlatPanel {
                        Text(transfer.lines.joinToString(", ") { "${it.quantity - it.receivedQuantity} × ${it.name.ifBlank { it.sku }}" })
                        Text("From ${s.locations.firstOrNull { it.id == transfer.from }?.name ?: "another location"}")
                        Button({ pending = "Receive all remaining parts in this transfer?" to { vm.receive(transfer) } }, enabled = enabled, modifier = Modifier.testTag("receive-transfer-${transfer.id}")) { Text("Receive all") }
                    }
                }
                item {
                    SectionLabel("MY STOCK")
                    OutlinedTextField(query, { query = it }, label = { Text("Search part or SKU") }, modifier = Modifier.fillMaxWidth())
                    FilterChip(lowOnly, { lowOnly = !lowOnly }, label = { Text("Low stock only") })
                }
                val rows = s.myLevels.filter { (!lowOnly || it.low) && "${it.name} ${it.sku} ${it.locationName}".contains(query, true) }
                if(rows.isEmpty()) item { Text(if(s.loading) "Loading stock…" else "No stock matches.") }
                items(rows, key = { "level-${it.locationId}-${it.partId}" }) { row ->
                    FlatPanel { Text(row.name, style = MaterialTheme.typography.titleMedium); Text("${row.sku} · ${row.locationName}"); Text("${row.quantity} in stock${if(row.low) " · Low (reorder ${row.reorderLevel})" else ""}", color = if(row.low) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface) }
                }
                if(s.mine.isNotEmpty()) {
                    item { FlatPanel {
                        CardHeading("Scan stock in or correct a count")
                        LocationChoices("Location", s.mine, myLocation, enabled) { location = it }
                        Row { listOf("receive" to "Add to stock", "set_count" to "Set count to").forEach { (key, label) -> FilterChip(kind == key, { kind = key }, label = { Text(label) }, enabled = enabled) } }
                        OutlinedTextField(sku, { sku = it }, label = { Text("Scan or type SKU") }, enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("stock-sku"))
                        OutlinedTextField(quantity, { quantity = it }, label = { Text("Quantity") }, enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("stock-quantity"))
                        OutlinedTextField(note, { note = it }, label = { Text("Note (optional)") }, enabled = enabled, modifier = Modifier.fillMaxWidth())
                        Button({
                            try { val body = partAdjustment(myLocation, sku, quantity, kind, note); pending = "${if(body.kind == "receive") "Add" else "Set count to"} ${body.quantity} for ${body.sku}?" to { vm.adjust(myLocation, sku, quantity, kind, note) { sku = ""; quantity = "1"; note = "" } } }
                            catch(e: Exception) { vm.error(e.userMessage()) }
                        }, enabled = enabled && sku.isNotBlank(), modifier = Modifier.testTag("stock-save")) { Text("Save stock") }
                    } }
                    item { FlatPanel {
                        CardHeading("Send stock to another location")
                        LocationChoices("From", s.mine, fromLocation, enabled) { from = it }
                        LocationChoices("To", s.locations.filter { !it.mine && it.active }, to, enabled) { to = it }
                        OutlinedTextField(sendSku, { sendSku = it }, label = { Text("Scan or type SKU") }, enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("transfer-sku"))
                        OutlinedTextField(sendQuantity, { sendQuantity = it }, label = { Text("Quantity") }, enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("transfer-quantity"))
                        TextButton({ try { require(sendSku.isNotBlank()) { "Enter a SKU." }; linesJson = Gson().toJson(lines + PartLineInput(sendSku.trim(), partQuantity(sendQuantity))); sendSku = ""; sendQuantity = "1" } catch(e: Exception) { vm.error(e.userMessage()) } }, enabled = enabled && sendSku.isNotBlank()) { Text("Add line") }
                        lines.forEachIndexed { index, line -> Row { Text("${line.quantity} × ${line.sku}", Modifier.weight(1f)); TextButton({ linesJson = Gson().toJson(lines.filterIndexed { i, _ -> i != index }) }, enabled = enabled) { Text("Remove") } } }
                        OutlinedTextField(sendNote, { sendNote = it }, label = { Text("Transfer note (optional)") }, enabled = enabled, modifier = Modifier.fillMaxWidth())
                        Button({ try { val body = partTransfer(fromLocation, to, lines, sendNote); pending = "Send ${body.lines.joinToString { "${it.quantity} × ${it.sku}" }} to ${s.locations.firstOrNull { it.id == to }?.name}?" to { vm.transfer(fromLocation, to, lines, sendNote) { linesJson = "[]"; sendNote = "" } } } catch(e: Exception) { vm.error(e.userMessage()) } }, enabled = enabled && to.isNotBlank() && lines.isNotEmpty(), modifier = Modifier.testTag("transfer-send")) { Text("Send transfer") }
                    } }
                }
                if(s.transfers.isNotEmpty()) item { SectionLabel("TRANSFER HISTORY") }
                items(s.transfers, key = { "transfer-${it.id}" }) { transfer -> FlatPanel {
                    Text("${s.locations.firstOrNull { it.id == transfer.from }?.name ?: "Source"} → ${s.locations.firstOrNull { it.id == transfer.to }?.name ?: "Destination"}", style = MaterialTheme.typography.titleSmall)
                    Text("${transfer.status.replace('_', ' ')} · ${transfer.lines.joinToString { "${it.quantity} × ${it.name.ifBlank { it.sku }}" }}")
                    transfer.note?.let { Text(it) }; transfer.createdAt?.let { Text(formatShopDate(it), style = MaterialTheme.typography.bodySmall) }
                } }
            }
        }
    }
    pending?.let { (title, action) -> AlertDialog(onDismissRequest = { pending = null }, title = { Text(title) }, confirmButton = { TextButton({ pending = null; action() }) { Text("Confirm") } }, dismissButton = { TextButton({ pending = null }) { Text("Cancel") } }) }
}

/** A job's model-and-size bill of materials, plus the parts actually consumed. */
@Composable fun ShoeJobPartsCard(jobId: String, refreshKey: String, vm: PartsViewModel = viewModel(key = "shoe-parts/$jobId", factory = PartsViewModel.factory(jobId))) {
    val s by vm.state.collectAsStateWithLifecycle()
    var location by rememberSaveable(jobId) { mutableStateOf("") }
    var pending by remember { mutableStateOf<SuggestedPart?>(null) }
    LaunchedEffect(refreshKey) { vm.refresh() }
    if(!s.available) return
    val remaining = s.suggested.filter { p -> s.used.none { it.partId == p.id } }
    if(remaining.isEmpty() && s.used.isEmpty() && !s.unknown) return
    val enabled = !s.busy && !s.loading && !s.unknown
    val picked = s.mine.firstOrNull { it.id == location }?.id ?: s.mine.singleOrNull()?.id.orEmpty()
    WebCard {
        WebCardTitle("Parts", icon = "stock")
        if(s.busy || s.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        s.error?.let { ErrorBanner(it) }; s.info?.let { Text(it) }; StockWriteReview(s, vm)
        if(s.mine.size > 1) LocationChoices("Use parts from", s.mine, picked, enabled) { location = it }
        remaining.forEach { part -> Row(Modifier.fillMaxWidth(), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Text("${part.quantity} × ${part.name} (${part.inStock} in stock)", Modifier.weight(1f))
            TextButton({ if(picked.isBlank()) vm.error("Choose the stock location for this part.") else pending = part }, enabled = enabled, modifier = Modifier.testTag("use-part-${part.id}")) { Text("Use") }
        } }
        if(s.used.isNotEmpty()) Text("Used: ${s.used.joinToString { "${it.quantity} × ${it.name}" }}", style = MaterialTheme.typography.bodyMedium)
    }
    pending?.let { part -> AlertDialog(onDismissRequest = { pending = null }, title = { Text("Use ${part.quantity} × ${part.name}?") }, text = { Text("The part will be recorded on this repair and removed from the selected stock location.") }, confirmButton = { TextButton({ pending = null; vm.use(part, picked) }) { Text("Use part") } }, dismissButton = { TextButton({ pending = null }) { Text("Cancel") } }) }
}

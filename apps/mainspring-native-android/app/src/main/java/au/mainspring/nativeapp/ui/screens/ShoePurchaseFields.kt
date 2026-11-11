package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.formatShopDate
import au.mainspring.nativeapp.userMessage
import kotlinx.coroutines.*

/** A purchase lookup only appears when the shop's network grants parts-stock access. */
@Composable fun ShoePurchaseLookup(enabled: Boolean, onPick: (PurchaseRecord) -> Unit, model: String = "", onModel: (String) -> Unit = {}) {
    val api = remember { ApiClient.service(PartsApi::class.java) }
    val scope = rememberCoroutineScope()
    var available by remember { mutableStateOf(false) }
    var models by remember { mutableStateOf<List<PartModel>>(emptyList()) }
    var query by rememberSaveable { mutableStateOf("") }
    var hits by remember { mutableStateOf<List<PurchaseRecord>?>(null) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var request by remember { mutableStateOf<Job?>(null) }
    LaunchedEffect(api) { try { api.locations(); available = true; models = api.models().filter { it.active } } catch(e: CancellationException) { throw e } catch(_: Exception) {} }
    DisposableEffect(Unit) { onDispose { request?.cancel() } }
    if(available) Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        OutlinedTextField(query, { query = it.take(100); request?.cancel(); hits = null; loading = false }, label = { Text("Find original purchase") }, supportingText = { Text("Name, phone, email or receipt") }, enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("shoe-purchase-search"))
        TextButton({
            request?.cancel()
            request = scope.launch { loading = true; error = null; try { hits = api.purchases(query.trim()) } catch(e: CancellationException) { throw e } catch(e: Exception) { error = e.userMessage() } finally { loading = false } }
        }, enabled = enabled && !loading && query.trim().length >= 2) { Text(if(loading) "Searching…" else "Search purchases") }
        if(hits?.isEmpty() == true) Text("No matching purchases.", style = MaterialTheme.typography.bodySmall)
        hits?.forEach { h -> TextButton({ onPick(h); hits = null }, enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("shoe-purchase-${h.id}")) {
            Text(listOfNotNull(h.customer, h.model, h.size?.let { "Size $it" }, h.date?.let { formatShopDate(it) }, h.store, h.reference).joinToString(" · "))
        } }
        error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
        if(model.isNotBlank()) models.filter { it.name.contains(model, true) && it.name != model }.take(8).forEach { m -> TextButton({ onModel(m.name) }, enabled = enabled) { Text(m.name) } }
    }
}

/** Extended editor keeps all shoe and purchase fields together and validates dates before saving. */
@Composable fun EditShoeDetailsDialog(shoe: ShoeRead, busy: Boolean, onClose: () -> Unit,
    onSave: (String, String, String, String, au.mainspring.nativeapp.ShoePurchaseDetails) -> Unit) {
    var type by rememberSaveable(shoe.id) { mutableStateOf(shoe.shoeType.orEmpty()) }
    var brand by rememberSaveable(shoe.id) { mutableStateOf(shoe.brand.orEmpty()) }
    var colour by rememberSaveable(shoe.id) { mutableStateOf(shoe.color.orEmpty()) }
    var notes by rememberSaveable(shoe.id) { mutableStateOf(shoe.notes.orEmpty()) }
    var model by rememberSaveable(shoe.id) { mutableStateOf(shoe.modelName.orEmpty()) }
    var size by rememberSaveable(shoe.id) { mutableStateOf(shoe.size.orEmpty()) }
    var date by rememberSaveable(shoe.id) { mutableStateOf(shoe.purchaseDate?.let { formatShopDate(it) }.orEmpty()) }
    var store by rememberSaveable(shoe.id) { mutableStateOf(shoe.purchaseStore.orEmpty()) }
    var reference by rememberSaveable(shoe.id) { mutableStateOf(shoe.purchaseRef.orEmpty()) }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(onDismissRequest = { if(!busy) onClose() }, title = { Text("Edit pair") }, text = {
        Column(Modifier.heightIn(max = 560.dp).verticalScroll(androidx.compose.foundation.rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(type, { type = it }, label = { Text("Shoe type") }, enabled = !busy, modifier = Modifier.fillMaxWidth().testTag("edit-shoe-type"))
            OutlinedTextField(brand, { brand = it }, label = { Text("Brand") }, enabled = !busy, modifier = Modifier.fillMaxWidth().testTag("edit-shoe-brand"))
            OutlinedTextField(colour, { colour = it }, label = { Text("Colour") }, enabled = !busy, modifier = Modifier.fillMaxWidth().testTag("edit-shoe-colour"))
            OutlinedTextField(model, { model = it }, label = { Text("Model") }, enabled = !busy, modifier = Modifier.fillMaxWidth().testTag("edit-shoe-model"))
            ShoePurchaseLookup(!busy, { h -> model = h.model.orEmpty(); size = h.size.orEmpty(); date = h.date?.let { formatShopDate(it) }.orEmpty(); store = h.store.orEmpty(); reference = h.reference }, model, { model = it })
            OutlinedTextField(size, { size = it }, label = { Text("Size") }, enabled = !busy, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(date, { date = it }, label = { Text("Purchase date (DD/MM/YYYY)") }, enabled = !busy, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(store, { store = it }, label = { Text("Bought at") }, enabled = !busy, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(reference, { reference = it }, label = { Text("Receipt / order reference") }, enabled = !busy, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(notes, { notes = it }, label = { Text("Condition notes") }, enabled = !busy, modifier = Modifier.fillMaxWidth().testTag("edit-shoe-notes"))
            error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
        }
    }, confirmButton = { TextButton({ try { au.mainspring.nativeapp.collectionDateIso(date); onSave(type, brand, colour, notes, au.mainspring.nativeapp.ShoePurchaseDetails(model, size, date, store, reference)); onClose() } catch(e: Exception) { error = e.userMessage() } }, enabled = !busy) { Text("Save") } }, dismissButton = { TextButton(onClose, enabled = !busy) { Text("Cancel") } })
}

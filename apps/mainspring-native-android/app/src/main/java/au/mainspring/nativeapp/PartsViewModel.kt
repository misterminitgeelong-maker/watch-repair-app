package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class PartsState(val loading: Boolean = false, val busy: Boolean = false, val available: Boolean = false,
    val error: String? = null, val info: String? = null, val unknown: Boolean = false, val reviewed: Boolean = false,
    val locations: List<PartLocation> = emptyList(), val levels: List<PartLevel> = emptyList(),
    val transfers: List<PartTransfer> = emptyList(), val suggested: List<SuggestedPart> = emptyList(), val used: List<UsedShoePart> = emptyList()) {
    val mine get() = locations.filter { it.mine && it.active }
    val myLevels get() = levels.filter { row -> mine.any { it.id == row.locationId } }
    val incoming get() = transfers.filter { t -> t.status == "in_transit" && mine.any { it.id == t.to } }
}

fun partQuantity(text: String, allowZero: Boolean = false): Int {
    val quantity = text.trim().toIntOrNull()
    require(quantity != null && quantity in (if(allowZero) 0 else 1)..1_000_000) { "Enter a whole quantity between ${if(allowZero) 0 else 1} and 1,000,000." }
    return quantity
}
fun partAdjustment(location: String, sku: String, quantity: String, kind: String, note: String): PartAdjustment {
    require(location.isNotBlank()) { "Choose your stock location." }
    require(sku.isNotBlank()) { "Scan or enter a SKU." }
    require(kind in listOf("receive", "set_count")) { "Choose Add to stock or Set count." }
    require(note.trim().length <= 300) { "Notes can be up to 300 characters." }
    return PartAdjustment(location, sku.trim(), partQuantity(quantity, true), kind, note.trim().ifBlank { null })
}
fun partTransfer(from: String, to: String, lines: List<PartLineInput>, note: String): PartTransferCreate {
    require(from.isNotBlank() && to.isNotBlank() && from != to) { "Choose different source and destination locations." }
    require(lines.isNotEmpty() && lines.size <= 200) { "Add between 1 and 200 parts to the transfer." }
    require(note.trim().length <= 300) { "Notes can be up to 300 characters." }
    require(lines.all { it.sku.isNotBlank() && it.quantity in 1..1_000_000 }) { "Check each SKU and quantity." }
    return PartTransferCreate(from, to, lines.map { it.copy(sku = it.sku.trim()) }, note.trim().ifBlank { null })
}

/** Parts stock writes use a durable checkpoint so an uncertain network result cannot silently duplicate a movement. */
class PartsViewModel(private val jobId: String? = null, private val api: PartsApi = ApiClient.service(PartsApi::class.java)) : ViewModel() {
    private val drafts = TokenStore.bindDrafts()
    private val checkpoint = "parts-stock/${jobId ?: "shop"}"
    private val mutable = MutableStateFlow(PartsState(unknown = drafts.pendingOperation(checkpoint)))
    val state = mutable.asStateFlow()
    init { refresh() }
    fun refresh() {
        if(mutable.value.loading || mutable.value.busy) return
        viewModelScope.launch { reload() }
    }
    private suspend fun reload() {
        mutable.update { it.copy(loading = true, error = null) }
        try {
            val locations = api.locations()
            if(jobId == null) {
                val levels = api.levels(); val transfers = api.transfers()
                mutable.update { it.copy(loading = false, available = true, locations = locations, levels = levels, transfers = transfers, reviewed = true) }
            } else {
                val suggested = api.suggested(jobId); val used = api.used(jobId)
                mutable.update { it.copy(loading = false, available = true, locations = locations, suggested = suggested, used = used, reviewed = true) }
            }
        } catch(e: CancellationException) { throw e }
        catch(e: Exception) {
            val denied = e is retrofit2.HttpException && e.code() == 403
            mutable.update { it.copy(loading = false, available = if(denied) false else it.available, error = if(denied) null else e.userMessage()) }
        }
    }
    fun error(message: String) { mutable.update { it.copy(error = message) } }
    fun reviewed() { if(mutable.value.reviewed && !mutable.value.busy) { drafts.setPendingOperation(checkpoint, false); mutable.update { it.copy(unknown = false) } } }
    private fun write(info: String, success: () -> Unit = {}, operation: suspend () -> Unit) {
        val s = mutable.value
        if(s.busy || s.loading || s.unknown || !s.available) return
        if(!drafts.setPendingOperation(checkpoint, true)) { error("Could not save the stock checkpoint. Check device storage before trying again."); return }
        mutable.update { it.copy(busy = true, error = null, info = null, reviewed = false) }
        viewModelScope.launch {
            var acknowledged = false
            try {
                operation(); acknowledged = true; drafts.setPendingOperation(checkpoint, false)
                mutable.update { it.copy(info = info) }; success(); reload()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val definite = acknowledged || e is retrofit2.HttpException && e.code() in 400..499
                if(definite) drafts.setPendingOperation(checkpoint, false)
                mutable.update { it.copy(unknown = !definite, error = if(definite) e.userMessage() else "The stock update result is unknown. Refresh and review current stock and transfers before repeating it. ${e.userMessage()}") }
            } finally { mutable.update { it.copy(busy = false) } }
        }
    }
    fun adjust(location: String, sku: String, quantity: String, kind: String, note: String, success: () -> Unit) {
        val body = try { partAdjustment(location, sku, quantity, kind, note) } catch(e: Exception) { error(e.userMessage()); return }
        if(mutable.value.mine.none { it.id == body.location }) { error("Choose a location assigned to this shop."); return }
        write("Stock updated.", success) { api.adjust(body) }
    }
    fun transfer(from: String, to: String, lines: List<PartLineInput>, note: String, success: () -> Unit) {
        val body = try { partTransfer(from, to, lines, note) } catch(e: Exception) { error(e.userMessage()); return }
        val s = mutable.value
        if(s.mine.none { it.id == from } || s.locations.none { it.id == to && it.active && !it.mine }) { error("Choose your source location and an active destination outside this shop."); return }
        write("Transfer sent.", success) { api.transfer(body) }
    }
    fun receive(transfer: PartTransfer) {
        if(mutable.value.incoming.none { it.id == transfer.id }) return
        write("Transfer received.") { api.receive(transfer.id, JsonObject()) }
    }
    fun use(part: SuggestedPart, location: String) {
        val job = jobId ?: return
        if(part.quantity !in 1..1000 || mutable.value.suggested.none { it.id == part.id } || mutable.value.mine.none { it.id == location }) { error("Choose the shop location used for this part."); return }
        write("Part recorded and removed from stock.") { api.use(job, ShoePartUse(part.id, part.quantity, location)) }
    }
    companion object {
        fun factory(job: String): ViewModelProvider.Factory = object: ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = PartsViewModel(job) as T
        }
    }
}

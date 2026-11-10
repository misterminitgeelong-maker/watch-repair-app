package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class EngravingState(val loading: Boolean = false, val busy: Boolean = false, val error: String? = null,
    val events: List<EngravingEvent> = emptyList(), val queue: EngravingQueue? = null, val unknown: Boolean = false, val reviewed: Boolean = false)
class EngravingViewModel(private val api: EngravingApi = ApiClient.service(EngravingApi::class.java)) : ViewModel() {
    private val drafts = TokenStore.bindDrafts()
    private val pendingKey = "engraving-write"
    private val mutable = MutableStateFlow(EngravingState(unknown = drafts.pendingOperation(pendingKey)))
    val state = mutable.asStateFlow()
    private var request: Job? = null
    private var eventId: String? = null
    init { refresh() }
    fun open(id: String?) { if(mutable.value.busy) return; request?.cancel(); eventId = id; mutable.update { it.copy(queue = null, loading = false) }; refresh() }
    fun refresh() {
        if(mutable.value.loading || mutable.value.busy) return
        request = viewModelScope.launch { reload() }
    }
    private suspend fun reload() {
        mutable.update { it.copy(loading = true, error = null) }
        try { val events = api.events(); val queue = eventId?.let { api.queue(it) }; mutable.update { it.copy(loading = false, events = events, queue = queue, reviewed = true) } }
        catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
    }
    fun reviewedUnknown() { if(mutable.value.reviewed && !mutable.value.busy) { drafts.setPendingOperation(pendingKey, false); mutable.update { it.copy(unknown = false) } } }
    fun error(message: String) { mutable.update { it.copy(error = message) } }
    private fun write(done: () -> Unit = {}, block: suspend () -> Unit) {
        if(mutable.value.busy || mutable.value.loading || mutable.value.unknown || !TokenStore.canWorkJobs()) return
        if(!drafts.setPendingOperation(pendingKey, true)) { error("Could not save the write checkpoint."); return }
        mutable.update { it.copy(busy = true, error = null, reviewed = false) }
        viewModelScope.launch {
            try { block(); drafts.setPendingOperation(pendingKey, false); done(); reload() }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { val definite = e is retrofit2.HttpException && e.code() in 400..499; if(definite) drafts.setPendingOperation(pendingKey, false); mutable.update { it.copy(unknown = !definite, error = if(definite) e.userMessage() else "The result is uncertain. Refresh and review the event and orders before repeating this action. ${e.userMessage()}") } }
            finally { mutable.update { it.copy(busy = false) } }
        }
    }
    fun saveEvent(id: String?, fields: JsonObject, done: () -> Unit) = write(done) { if(id == null) { val event = api.createEvent(fields); eventId = event.id } else api.updateEvent(id, fields) }
    fun status(status: String) { val id = eventId ?: return; write { api.updateEvent(id, JsonObject().apply { addProperty("status", status) }) } }
    fun order(fields: JsonObject, done: () -> Unit) { val id = eventId ?: return; write(done) { api.walkUp(id, fields) } }
    fun update(order: EngravingOrder, fields: JsonObject, done: () -> Unit = {}) = write(done) { api.updateOrder(order.id, fields) }
    fun action(order: EngravingOrder, action: String) { if(action !in listOf("start", "medal-done", "resend-ready")) return; write { api.action(order.id, action) } }
    fun collectGroup(order: EngravingOrder) = write {
        val group = mutable.value.queue?.orders.orEmpty().filter { it.status == "ready" && (it.id == order.id || order.group != null && it.group == order.group) }
        for(member in group) api.updateOrder(member.id, JsonObject().apply { addProperty("status", "collected"); addProperty("paid", true) })
    }
    suspend fun export(software: String, limit: Int?): ByteArray = withContext(Dispatchers.IO) {
        require(software in listOf("xtool", "lightburn", "ezcad2", "csv")) { "Choose a supported laser format." }
        require(limit == null || limit in 1..500) { "Export between 1 and 500 medals, or leave the limit blank." }
        api.export(requireNotNull(eventId), software, limit).use { it.bytes() }
    }
}

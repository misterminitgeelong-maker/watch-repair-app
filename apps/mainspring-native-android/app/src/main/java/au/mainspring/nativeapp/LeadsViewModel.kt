package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.time.LocalDate

/** Active pipeline stages, in the order the web Lead inbox shows them. */
val LEAD_PIPELINE = listOf("new" to "New", "quote_needed" to "Quote needed", "contacted" to "Contacted", "follow_up_due" to "Follow-up due")
val LEAD_STATUS_OPTIONS = LEAD_PIPELINE + listOf("won" to "Won", "lost" to "Lost")

data class LeadsState(
    /** null = all active leads; otherwise a pipeline status requested from the server. */
    val stage: String? = null,
    val all: List<InboundLead> = emptyList(),
    val shown: List<InboundLead> = emptyList(),
    val loading: Boolean = false, val busyId: String? = null, val adding: Boolean = false,
    val error: String? = null, val convertedAccountId: String? = null,
) {
    val counts: Map<String, Int> get() = all.groupingBy { it.status }.eachCount()
    val overdue: Int get() = all.count { it.isOverdueFollowUp() }
}

fun InboundLead.isOverdueFollowUp(today: LocalDate = LocalDate.now()): Boolean =
    status == "follow_up_due" && nextFollowUpOn?.let { runCatching { LocalDate.parse(it.take(10)).isBefore(today) }.getOrDefault(false) } == true

class LeadsViewModel : ViewModel() {
    private val api = ApiClient.service(LeadsApi::class.java)
    private val mutable = MutableStateFlow(LeadsState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }

    fun selectStage(stage: String?) { mutable.update { it.copy(stage = stage) }; refresh() }
    fun consumeConverted() { mutable.update { it.copy(convertedAccountId = null) } }

    fun refresh() {
        request?.cancel()
        val stage = state.value.stage
        mutable.update { it.copy(loading = true, error = null) }
        request = viewModelScope.launch {
            try {
                val all = api.leads(null)
                val shown = if(stage == null) all.filter { it.status != "won" && it.status != "lost" } else api.leads(stage)
                mutable.update { it.copy(loading = false, all = all, shown = shown) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }

    fun setStatus(lead: InboundLead, status: String) = update(lead) { addProperty("status", status) }
    fun followUpIn(lead: InboundLead, days: Long) = update(lead) { addProperty("status", "follow_up_due"); addProperty("next_follow_up_on", LocalDate.now().plusDays(days).toString()) }
    fun saveNotes(lead: InboundLead, notes: String) = update(lead) { addProperty("notes", notes.trim()) }

    private fun update(lead: InboundLead, build: JsonObject.() -> Unit) {
        if(state.value.busyId != null) return
        mutable.update { it.copy(busyId = lead.id, error = null) }
        viewModelScope.launch {
            try { api.updateLead(lead.id, JsonObject().apply(build)); mutable.update { it.copy(busyId = null) }; refresh() }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(busyId = null, error = e.userMessage()) } }
        }
    }

    fun convert(lead: InboundLead) {
        if(state.value.busyId != null) return
        mutable.update { it.copy(busyId = lead.id, error = null) }
        viewModelScope.launch {
            try {
                val body = JsonObject().apply { addProperty("account_name", lead.name) }
                val result = api.convertLead(lead.id, body)
                mutable.update { it.copy(busyId = null, convertedAccountId = result.customerAccountId) }; refresh()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(busyId = null, error = e.userMessage()) } }
        }
    }

    fun add(name: String, phone: String, suburb: String, notes: String, status: String, onDone: () -> Unit) {
        if(state.value.adding || name.isBlank()) return
        mutable.update { it.copy(adding = true, error = null) }
        viewModelScope.launch {
            try {
                val body = JsonObject().apply {
                    addProperty("name", name.trim()); addProperty("status", status)
                    phone.trim().takeIf { it.isNotEmpty() }?.let { addProperty("phone", it) }
                    suburb.trim().takeIf { it.isNotEmpty() }?.let { addProperty("suburb_name", it) }
                    notes.trim().takeIf { it.isNotEmpty() }?.let { addProperty("notes", it) }
                }
                api.createLead(body); mutable.update { it.copy(adding = false) }; onDone(); refresh()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(adding = false, error = e.userMessage()) } }
        }
    }
}

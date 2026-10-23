package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.time.Instant
import java.time.temporal.ChronoUnit

data class RevenueControlState(
    val queue: String = "due", val kind: String? = null,
    /** null = everyone, otherwise "me", "unassigned" or a user id (as accepted by the API). */
    val owner: String? = null, val search: String = "",
    val owners: List<RevenueOwner> = emptyList(),
    val items: List<RevenueItem> = emptyList(), val buckets: List<RevenueBucket> = emptyList(),
    val total: Int = 0, val warnings: List<String> = emptyList(),
    val loading: Boolean = false, val error: String? = null,
    val editing: RevenueItem? = null, val saving: Boolean = false, val saveError: String? = null,
)

class RevenueControlViewModel : ViewModel() {
    private val api = ApiClient.service(RevenueApi::class.java)
    private val mutable = MutableStateFlow(RevenueControlState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    private var nextOffset = 0
    init { refresh() }
    fun queue(value: String) { mutable.update { it.copy(queue = value) }; load(false) }
    fun kind(value: String?) { mutable.update { it.copy(kind = if(it.kind == value) null else value) }; load(false) }
    fun owner(value: String?) { mutable.update { it.copy(owner = value) }; load(false) }
    /** Search is debounced so typing does not fire a request per keystroke. */
    fun search(value: String) { mutable.update { it.copy(search = value) }; load(false, debounce = true) }
    fun refresh() { load(false) }
    fun more() { if(!state.value.loading && nextOffset < state.value.total) load(true) }

    fun edit(item: RevenueItem?) { mutable.update { it.copy(editing = item, saveError = null) } }

    /**
     * Mirrors the web FollowUpModal. [schedule] is "keep", "now" or a number of days.
     * Sends the item's version as expected_version (optimistic lock); a stale version surfaces the server message.
     */
    fun saveFollowUp(ownerUserId: String?, schedule: String, note: String, contacted: Boolean) {
        val item = state.value.editing ?: return
        if(state.value.saving) return
        val next: String? = when(schedule) {
            "keep" -> if(item.due) null else item.dueAt
            "now" -> null
            else -> Instant.now().plus(schedule.toLong(), ChronoUnit.DAYS).toString()
        }
        val body = JsonObject().apply {
            addProperty("expected_version", item.version)
            if(ownerUserId.isNullOrBlank()) add("owner_user_id", JsonNull.INSTANCE) else addProperty("owner_user_id", ownerUserId)
            if(next == null) add("next_follow_up_at", JsonNull.INSTANCE) else addProperty("next_follow_up_at", next)
            addProperty("note", note.take(2000))
            addProperty("contacted", contacted)
        }
        mutable.update { it.copy(saving = true, saveError = null) }
        viewModelScope.launch {
            try {
                api.saveFollowUp(item.key, body)
                mutable.update { it.copy(saving = false, editing = null) }
                load(false)
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(saving = false, saveError = "Could not save follow-up. ${e.userMessage()}") } }
        }
    }

    private fun load(append: Boolean, debounce: Boolean = false) {
        request?.cancel()
        val offset = if(append) nextOffset else 0
        mutable.update { it.copy(loading = true, error = null, items = if(append) it.items else emptyList()) }
        request = viewModelScope.launch {
            try {
                if(debounce) delay(350)
                val selection = state.value
                val page = api.revenueControl(state = selection.queue, kind = selection.kind, owner = selection.owner,
                    search = selection.search.trim().ifBlank { null }, offset = offset)
                nextOffset = page.offset + page.items.size
                mutable.update { it.copy(loading = false, total = page.total, buckets = page.buckets, warnings = page.warnings,
                    owners = page.owners.ifEmpty { it.owners },
                    items = (if(append) it.items + page.items else page.items).distinctBy { item -> item.key }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}

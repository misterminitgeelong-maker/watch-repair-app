package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.CardPaymentIssueRead
import au.mainspring.nativeapp.api.InboxExtrasApi
import au.mainspring.nativeapp.api.TenantEventLogRead
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class InboxUiState(
    val loading: Boolean = false,
    val loadingMore: Boolean = false,
    val canLoadMore: Boolean = false,
    val error: String? = null,
    val events: List<TenantEventLogRead> = emptyList(),
    val deletingId: String? = null,
    /** Open card-payment issues keyed by issue (event entity) id. */
    val issues: Map<String, CardPaymentIssueRead> = emptyMap(),
    val busyIssueId: String? = null,
    val actionError: String? = null,
)

/** Where a tapped inbox row goes; mirrors InboxPage.tsx. Returns null when the row has no destination. */
fun inboxRoute(ev: TenantEventLogRead): String? {
    val id = ev.entityId?.takeIf { it.isNotBlank() } ?: return null
    val reply = ev.eventType == "customer_sms_reply" || ev.eventType == "portal_customer_message"
    return when (ev.entityType) {
        "repair_job" -> if (reply) "messages/repair-jobs/$id" else "watchJob/$id"
        "shoe_repair_job" -> if (reply) "messages/shoe-repair-jobs/$id" else "shoeJob/$id"
        "auto_key_job" -> if (reply) "messages/auto-key-jobs/$id" else "autoKeyJob/$id"
        "invoice" -> "invoice/$id"
        else -> null
    }
}

class InboxViewModel : ViewModel() {
    companion object { const val PAGE_SIZE = 50 }
    private val api = ApiClient.api
    private val extras get() = ApiClient.service(InboxExtrasApi::class.java)
    private val _state = MutableStateFlow(InboxUiState())
    val state: StateFlow<InboxUiState> = _state.asStateFlow()

    enum class CardAction { Refund, Apply, Dismiss }

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = api.listInbox(PAGE_SIZE, 0)
                _state.update { it.copy(loading = false, events = list, canLoadMore = list.size >= PAGE_SIZE) }
                loadIssues(list)
                InboxCountStore.refreshNow()
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }

    fun loadMore() {
        val s = _state.value
        if (s.loading || s.loadingMore || !s.canLoadMore) return
        viewModelScope.launch {
            _state.update { it.copy(loadingMore = true, actionError = null) }
            try {
                val list = api.listInbox(PAGE_SIZE, _state.value.events.size)
                _state.update { cur ->
                    val known = cur.events.map { it.id }.toSet()
                    cur.copy(loadingMore = false, events = cur.events + list.filter { it.id !in known }, canLoadMore = list.size >= PAGE_SIZE)
                }
                loadIssues(list)
            } catch (e: Exception) {
                _state.update { it.copy(loadingMore = false, actionError = e.userMessage()) }
            }
        }
    }

    private suspend fun loadIssues(list: List<TenantEventLogRead>) {
        for (ev in list) {
            if (ev.eventType != "card_payment_needs_attention" || ev.entityType != "card_payment_issue") continue
            val id = ev.entityId ?: continue
            try {
                val issue = extras.cardPaymentIssue(id)
                if (issue.status == "open") _state.update { it.copy(issues = it.issues + (id to issue)) }
            } catch (_: Exception) {}
        }
    }

    fun delete(eventId: String) {
        val ev = _state.value.events.firstOrNull { it.id == eventId } ?: return
        if (ev.eventType == "card_payment_needs_attention" || _state.value.deletingId != null) return
        viewModelScope.launch {
            _state.update { it.copy(deletingId = eventId, actionError = null) }
            try {
                val r = extras.deleteInboxEvent(eventId)
                if (!r.isSuccessful && r.code() != 404) throw retrofit2.HttpException(r)
                _state.update { it.copy(deletingId = null, events = it.events.filter { e -> e.id != eventId }) }
                InboxCountStore.refreshNow()
            } catch (e: Exception) {
                _state.update { it.copy(deletingId = null, actionError = e.userMessage()) }
            }
        }
    }

    /** Moves money for Refund/Apply: the UI must confirm before calling. */
    fun resolveIssue(issueId: String, action: CardAction) {
        if (_state.value.busyIssueId != null) return
        viewModelScope.launch {
            _state.update { it.copy(busyIssueId = issueId, actionError = null) }
            try {
                when (action) {
                    CardAction.Refund -> extras.refundCardPaymentIssue(issueId)
                    CardAction.Apply -> extras.applyCardPaymentIssue(issueId)
                    CardAction.Dismiss -> extras.dismissCardPaymentIssue(issueId)
                }
                _state.update { it.copy(busyIssueId = null, issues = it.issues - issueId) }
                // Backend removes the alert on resolution; reload to reflect it.
                val list = api.listInbox(maxOf(PAGE_SIZE, _state.value.events.size).coerceAtMost(500), 0)
                _state.update { it.copy(events = list, canLoadMore = list.size >= PAGE_SIZE) }
                InboxCountStore.refreshNow()
            } catch (e: Exception) {
                _state.update { it.copy(busyIssueId = null, actionError = e.userMessage()) }
            }
        }
    }
}

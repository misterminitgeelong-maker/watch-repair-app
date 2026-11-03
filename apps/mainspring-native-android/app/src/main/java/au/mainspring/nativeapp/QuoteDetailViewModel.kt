package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.QuoteLineItemRead
import au.mainspring.nativeapp.api.QuoteRead
import au.mainspring.nativeapp.data.QuoteNavCache
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class QuoteDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val quote: QuoteRead? = null,
    val lines: List<QuoteLineItemRead> = emptyList(),
    val sendBusy: Boolean = false,
    val invoiceBusy: Boolean = false,
    val invoiceId: String? = null,
    val resendBusy: Boolean = false,
    val info: String? = null,
)

class QuoteDetailViewModel(
    private val quoteId: String,
) : ViewModel() {
    private val generation = au.mainspring.nativeapp.TokenStore.sessionGeneration()
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val _state = MutableStateFlow(QuoteDetailUiState())
    val state: StateFlow<QuoteDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        if (_state.value.loading || _state.value.sendBusy || _state.value.invoiceBusy) return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val cached = QuoteNavCache[quoteId]
                var meta: QuoteRead? = null
                var offset = 0
                while (meta == null) {
                    val page = api.listQuotes(limit = 500, offset = offset, repairJobId = cached?.repairJobId)
                    QuoteNavCache.putAll(page,generation)
                    meta = page.firstOrNull { it.id == quoteId }
                    if (page.size < 500) break
                    offset += page.size
                }
                val lines = api.getQuoteLineItems(quoteId)
                _state.update {
                    it.copy(loading = false, quote = meta, lines = lines, error = if (meta == null) "Quote not found in recent list." else null)
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }

    fun sendQuote() {
        if (_state.value.sendBusy || _state.value.quote?.status != "draft") return
        viewModelScope.launch {
            _state.update { it.copy(sendBusy = true, error = null) }
            try {
                val resp = api.postQuoteSend(quoteId)
                val cur = _state.value.quote
                if (cur != null) {
                    val updated = cur.copy(
                        status = resp.status,
                        sentAt = resp.sentAt,
                        approvalToken = resp.approvalToken,
                    )
                    QuoteNavCache.put(updated,generation)
                    _state.update { it.copy(sendBusy = false, quote = updated) }
                } else {
                    _state.update { it.copy(sendBusy = false, error = "Quote metadata missing; pull to refresh from list.") }
                }
            } catch (e: Exception) {
                _state.update { it.copy(sendBusy = false, error = e.userMessage()) }
            }
        }
    }

    /** Resend a sent or expired quote (web `POST /quotes/{id}/resend`): refreshes the approval window and re-notifies the customer. */
    fun resendQuote() {
        val cur = _state.value.quote ?: return
        if (_state.value.resendBusy || _state.value.sendBusy || cur.status !in listOf("sent", "expired")) return
        viewModelScope.launch {
            _state.update { it.copy(resendBusy = true, error = null, info = null) }
            try {
                val resp = api.postQuoteResend(quoteId)
                val updated = cur.copy(status = resp.status, sentAt = resp.sentAt, approvalToken = resp.approvalToken)
                QuoteNavCache.put(updated, generation)
                _state.update { it.copy(resendBusy = false, quote = updated, info = "Quote resent to the customer.") }
            } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (e: Exception) {
                _state.update { it.copy(resendBusy = false, error = e.userMessage()) }
            }
        }
    }

    fun createInvoice() {
        if (_state.value.invoiceBusy || _state.value.quote?.status != "approved") return
        _state.update { it.copy(invoiceBusy = true, error = null) }
        viewModelScope.launch {
            try {
                val response = api.invoiceFromQuote(quoteId)
                _state.update { it.copy(invoiceBusy = false, invoiceId = response.invoice.id) }
            } catch(e: Exception) {
                // Server enforces one invoice per quote. Resolve a previous/unknown success by reading.
                try {
                    var offset = 0
                    var existing: au.mainspring.nativeapp.api.InvoiceRead? = null
                    do {
                        val page = api.listInvoices(limit = 500, offset = offset)
                        existing = page.items.firstOrNull { it.quoteId == quoteId }
                        offset += page.items.size
                        if(existing != null || page.items.isEmpty() || offset >= page.total) break
                    } while(true)
                    _state.update { it.copy(invoiceBusy = false, invoiceId = existing?.id,
                        error = if(existing == null) e.userMessage() else null) }
                } catch (_: Exception) { _state.update { it.copy(invoiceBusy = false, error = "Could not confirm invoice creation. Check invoices before retrying.") } }
            }
        }
    }

    companion object {
        fun factory(quoteId: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return QuoteDetailViewModel(quoteId) as T
            }
        }
    }
}

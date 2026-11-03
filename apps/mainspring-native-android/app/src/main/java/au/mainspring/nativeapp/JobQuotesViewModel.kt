package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.data.QuoteNavCache
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class JobQuotesState(val loading: Boolean = false, val busy: Boolean = false,
    val error: String? = null, val job: RepairJobRead? = null, val quotes: List<QuoteRead> = emptyList(),
    val created: QuoteRead? = null, val unknownSave: Boolean = false, val historyChecked: Boolean = false,
    val sentToCustomer: Boolean = false)
class JobQuotesViewModel(private val jobId: String) : ViewModel() {
    private val generation = au.mainspring.nativeapp.TokenStore.sessionGeneration()
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
    private val operationKey = "quote:$jobId"
    private val mutable = MutableStateFlow(JobQuotesState(unknownSave = drafts.pendingOperation(operationKey)))
    val state = mutable.asStateFlow()
    init { load() }
    fun load() {
        if (mutable.value.loading || mutable.value.busy) return
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val job = api.getRepairJob(jobId)
                val quotes = api.listQuotes(repairJobId = jobId, limit = 500)
                QuoteNavCache.putAll(quotes,generation)
                mutable.update { it.copy(loading = false, job = job, quotes = quotes, historyChecked = true) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun createLines(lines: List<MobileQuoteLine>, gst: Boolean, inclusive: Boolean) = create(lines, gst, inclusive, send = false)
    /** Web "Create and send": creates the quote then sends it to the customer in one action. */
    fun createAndSendLines(lines: List<MobileQuoteLine>, gst: Boolean, inclusive: Boolean) = create(lines, gst, inclusive, send = true)
    private fun create(lines: List<MobileQuoteLine>, gst: Boolean, inclusive: Boolean, send: Boolean) {
        if (mutable.value.loading || mutable.value.busy || mutable.value.created != null || mutable.value.unknownSave) return
        if(lines.isEmpty() || lines.any { it.description.isBlank() || !it.quantity.isFinite() || it.quantity <= 0 || it.quantity > 10000 || it.unitCents !in 0..100_000_000 }) {
            mutable.update { it.copy(error = "Enter a description, valid quantity and unit price for every line.") }; return
        }
        try { validateQuoteAmountRange(lines) } catch(e: IllegalArgumentException) { mutable.update { it.copy(error = e.userMessage()) }; return }
        if(!drafts.setPendingOperation(operationKey, true)) { mutable.update { it.copy(error = "Could not save the quote checkpoint. Check device storage and sign in before continuing.") }; return }
        mutable.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            try {
                val quote = api.createQuote(QuoteCreate(jobId, gst, inclusive,
                    lines.map { QuoteLineItemRead(description = it.description, quantity = it.quantity, unitPriceCents = it.unitCents, itemType = "labor") }))
                QuoteNavCache.put(quote,generation)
                drafts.saveMessageDraft("quote-composer/watch/$jobId", "")
                drafts.setPendingOperation(operationKey, false)
                mutable.update { it.copy(busy = send, created = quote, quotes = listOf(quote) + it.quotes, sentToCustomer = false) }
                if(send) {
                    // The draft is already saved; a failed send leaves it as a draft the user can open and send.
                    try {
                        val sent = api.postQuoteSend(quote.id)
                        mutable.update { s -> s.copy(sentToCustomer = true, quotes = s.quotes.map { q -> if(q.id == quote.id) q.copy(status = sent.status, approvalToken = sent.approvalToken, sentAt = sent.sentAt) else q }) }
                    } catch(e: CancellationException) { throw e }
                    catch(e: Exception) { mutable.update { it.copy(error = "Quote saved as a draft but could not be sent. Open it to send. ${e.userMessage()}") } }
                    mutable.update { it.copy(busy = false) }
                }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { val unknown = e !is retrofit2.HttpException || e.code() >= 500
                drafts.setPendingOperation(operationKey, unknown)
                mutable.update { it.copy(busy = false, unknownSave = unknown, historyChecked = false,
                error = "Could not confirm the quote save. Refresh the quote list before trying again. ${e.userMessage()}") } }
        }
    }
    fun startAnotherQuote() { if(!mutable.value.busy && !mutable.value.unknownSave) mutable.update { it.copy(created = null, sentToCustomer = false) } }
    fun acknowledgeHistory() { if(!mutable.value.historyChecked) return; drafts.setPendingOperation(operationKey, false); mutable.update { it.copy(unknownSave = false) } }
    companion object {
        fun factory(jobId: String) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = JobQuotesViewModel(jobId) as T
        }
    }
}


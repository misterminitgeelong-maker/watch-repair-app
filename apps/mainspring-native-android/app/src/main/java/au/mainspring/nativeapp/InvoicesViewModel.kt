package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.InvoiceExtrasApi
import au.mainspring.nativeapp.api.InvoiceRead
import au.mainspring.nativeapp.api.MobileListedInvoice
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class InvoicesUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val invoices: List<InvoiceRead> = emptyList(),
    val total: Int = 0,
    val jobs: Map<String, au.mainspring.nativeapp.api.RepairJobRead> = emptyMap(),
    val mobile: List<MobileListedInvoice> = emptyList(),
    /** Watch invoice loaded for the inline "Record payment" dialog (list row pay). */
    val payTarget: au.mainspring.nativeapp.api.InvoiceWithPayments? = null,
    val payBusy: Boolean = false,
    val notice: String? = null,
)

/** One row of the merged invoice list (watch or mobile). */
data class ListedInvoice(
    val id: String, val number: String, val status: String, val totalCents: Int, val currency: String,
    val createdAt: String, val customerName: String?, val title: String, val mobile: Boolean, val jobId: String,
    val subtotalCents: Int? = null, val taxCents: Int? = null,
)

/** Merge, filter and search like the web InvoicesPage. `type` is null (all), "watch" or "mobile". */
fun mergedInvoices(state: InvoicesUiState, type: String?, status: String?, query: String): List<ListedInvoice> {
    val watch = state.invoices.map { inv ->
        val job = state.jobs[inv.repairJobId]
        ListedInvoice(inv.id, inv.invoiceNumber, inv.status, inv.totalCents, inv.currency, inv.createdAt, job?.customerName, job?.title ?: "Repair invoice", false, inv.repairJobId, inv.subtotalCents, inv.taxCents)
    }
    val mobile = state.mobile.map {
        ListedInvoice(it.id, it.number, it.status, it.totalCents, it.currency, it.createdAt, it.customerName, it.jobNumber?.let { n -> "Mobile job $n" } ?: "Mobile invoice", true, it.jobId, it.subtotal, it.tax)
    }
    val term = query.trim().lowercase()
    return (watch + mobile).filter { row ->
        (status == null || row.status == status) &&
            (type == null || (type == "mobile") == row.mobile) &&
            (term.isEmpty() || row.number.lowercase().contains(term) || (row.customerName ?: "").lowercase().contains(term))
    }.sortedByDescending { it.createdAt }
}

class InvoicesViewModel : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val extras get() = ApiClient.service(InvoiceExtrasApi::class.java)
    private val _state = MutableStateFlow(InvoicesUiState())
    val state: StateFlow<InvoicesUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.loading) return
        fetch(false)
    }

    fun loadMore() {
        if (_state.value.loading || _state.value.invoices.size >= _state.value.total) return
        fetch(true)
    }

    /** Remaining balance for an invoice: total minus payments, never negative. */
    fun remainingCents(data: au.mainspring.nativeapp.api.InvoiceWithPayments) = (data.invoice.totalCents - data.payments.sumOf { it.amountCents }).coerceAtLeast(0)

    fun beginPay(invoiceId: String) {
        if(!TokenStore.canManageInvoices() || _state.value.payBusy) return
        val drafts = TokenStore.bindDrafts()
        if(drafts.pendingOperation("payment:$invoiceId")) { _state.update { it.copy(notice = "A previous payment on this invoice could not be confirmed. Open the invoice and check its payment history first.") }; return }
        _state.update { it.copy(payBusy = true, notice = null) }
        viewModelScope.launch {
            try { val data = api.getInvoice(invoiceId); _state.update { it.copy(payBusy = false, payTarget = data) } }
            catch(e: Exception) { _state.update { it.copy(payBusy = false, notice = "Could not load invoice. ${e.userMessage()}") } }
        }
    }

    fun dismissPay() { if(!_state.value.payBusy) _state.update { it.copy(payTarget = null) } }
    fun clearNotice() { _state.update { it.copy(notice = null) } }

    fun submitPay(amountCents: Int, reference: String?) {
        val data = _state.value.payTarget ?: return
        if(_state.value.payBusy || !TokenStore.canManageInvoices() || data.invoice.status != "unpaid") return
        if(amountCents <= 0 || amountCents > remainingCents(data)) { _state.update { it.copy(notice = "Enter an amount within the remaining balance.") }; return }
        val key = "payment:${data.invoice.id}"
        val drafts = TokenStore.bindDrafts()
        if(!drafts.setPendingOperation(key, true)) { _state.update { it.copy(notice = "Could not save the payment checkpoint. Check device storage before continuing.") }; return }
        _state.update { it.copy(payBusy = true, notice = null) }
        viewModelScope.launch {
            try {
                api.postInvoicePayment(data.invoice.id, au.mainspring.nativeapp.api.PaymentCreate(amountCents = amountCents, providerReference = reference?.trim()?.takeIf { it.isNotEmpty() }))
                drafts.setPendingOperation(key, false)
                _state.update { it.copy(payBusy = false, payTarget = null, notice = "Payment recorded.") }
                refresh()
            } catch(e: Exception) {
                val unknown = e !is retrofit2.HttpException || e.code() >= 500
                drafts.setPendingOperation(key, unknown)
                _state.update { it.copy(payBusy = false, payTarget = null, notice = "Could not confirm this payment. Open the invoice and check payment history before recording another. ${e.userMessage()}") }
            }
        }
    }

    /** Builds the printable summary for a list row; watch invoices load line items and payments first. */
    suspend fun summaryFor(row: ListedInvoice): InvoiceSummary {
        if(row.mobile) return InvoiceSummary(row.number, row.status,
            details = listOfNotNull(row.customerName?.let { "Customer: $it" }, "Created ${au.mainspring.nativeapp.ui.formatShopDate(row.createdAt)}"),
            totals = listOfNotNull(row.subtotalCents?.let { "Subtotal" to au.mainspring.nativeapp.ui.formatCents(it, row.currency) }, row.taxCents?.let { "Tax / GST" to au.mainspring.nativeapp.ui.formatCents(it, row.currency) }, "Total" to au.mainspring.nativeapp.ui.formatCents(row.totalCents, row.currency)))
        val data = api.getInvoice(row.id)
        val lines = runCatching { api.getInvoiceLineItems(row.id) }.getOrDefault(emptyList())
        return watchInvoiceSummary(data, lines)
    }

    private fun fetch(append: Boolean) {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val page = api.listInvoices(offset = if(append) _state.value.invoices.size else 0)
                _state.update { it.copy(loading = false, invoices = if(append) (it.invoices + page.items).distinctBy { row -> row.id } else page.items, total = page.total) }
                runCatching { api.listRepairJobs(limit = 200) }.getOrNull()?.let { jobs -> _state.update { it.copy(jobs = jobs.associateBy { job -> job.id }) } }
                // Mobile invoices are feature-gated; a tenant without the feature simply has none.
                if (!append) { val mobile = runCatching { extras.listAllMobileInvoices() }.getOrNull(); if (mobile != null) _state.update { it.copy(mobile = mobile) } }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }
}

/** Printable summary of a watch invoice (shared by the list and the detail screen). */
fun watchInvoiceSummary(data: au.mainspring.nativeapp.api.InvoiceWithPayments, lines: List<au.mainspring.nativeapp.api.QuoteLineItemRead>): InvoiceSummary {
    val inv = data.invoice
    val paid = data.payments.sumOf { it.amountCents }
    val remaining = (inv.totalCents - paid).coerceAtLeast(0)
    fun money(c: Int) = au.mainspring.nativeapp.ui.formatCents(c, inv.currency)
    return InvoiceSummary(inv.invoiceNumber, inv.status,
        details = listOf("Created ${au.mainspring.nativeapp.ui.formatShopDate(inv.createdAt)}"),
        items = lines.map { "${it.description.orEmpty()}\n${java.math.BigDecimal.valueOf(it.quantity).stripTrailingZeros().toPlainString()} \u00d7 ${money(it.unitPriceCents)}" },
        totals = listOf("Subtotal" to money(inv.subtotalCents), "Tax / GST" to money(inv.taxCents), "Total" to money(inv.totalCents), "Paid" to money(paid), "Remaining" to money(remaining)))
}

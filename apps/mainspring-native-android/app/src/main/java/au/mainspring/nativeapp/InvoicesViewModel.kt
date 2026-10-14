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
)

/** One row of the merged invoice list (watch or mobile). */
data class ListedInvoice(
    val id: String, val number: String, val status: String, val totalCents: Int, val currency: String,
    val createdAt: String, val customerName: String?, val title: String, val mobile: Boolean, val jobId: String,
)

/** Merge, filter and search like the web InvoicesPage. `type` is null (all), "watch" or "mobile". */
fun mergedInvoices(state: InvoicesUiState, type: String?, status: String?, query: String): List<ListedInvoice> {
    val watch = state.invoices.map { inv ->
        val job = state.jobs[inv.repairJobId]
        ListedInvoice(inv.id, inv.invoiceNumber, inv.status, inv.totalCents, inv.currency, inv.createdAt, job?.customerName, job?.title ?: "Repair invoice", false, inv.repairJobId)
    }
    val mobile = state.mobile.map {
        ListedInvoice(it.id, it.number, it.status, it.totalCents, it.currency, it.createdAt, it.customerName, it.jobNumber?.let { n -> "Mobile job $n" } ?: "Mobile invoice", true, it.jobId)
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

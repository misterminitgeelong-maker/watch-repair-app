package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.InvoiceRead
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
)

class InvoicesViewModel : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
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
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }
}

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
)

class InvoicesViewModel : ViewModel() {
    private val _state = MutableStateFlow(InvoicesUiState())
    val state: StateFlow<InvoicesUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = ApiClient.api.listInvoices()
                _state.update { it.copy(loading = false, invoices = list) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load invoices") }
            }
        }
    }
}

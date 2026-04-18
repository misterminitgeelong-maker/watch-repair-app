package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.InvoiceWithPayments
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class InvoiceDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val data: InvoiceWithPayments? = null,
)

class InvoiceDetailViewModel(
    private val invoiceId: String,
) : ViewModel() {
    private val _state = MutableStateFlow(InvoiceDetailUiState())
    val state: StateFlow<InvoiceDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val d = ApiClient.api.getInvoice(invoiceId)
                _state.update { it.copy(loading = false, data = d) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load invoice") }
            }
        }
    }

    companion object {
        fun factory(invoiceId: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return InvoiceDetailViewModel(invoiceId) as T
            }
        }
    }
}

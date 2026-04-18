package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.InvoiceWithPayments
import au.mainspring.nativeapp.api.PaymentCreate
import au.mainspring.nativeapp.api.QuoteLineItemRead
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class InvoiceDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val data: InvoiceWithPayments? = null,
    val lineItems: List<QuoteLineItemRead> = emptyList(),
    val paymentBusy: Boolean = false,
    val paymentInfo: String? = null,
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
            _state.update { it.copy(loading = true, error = null, paymentInfo = null) }
            try {
                val data: InvoiceWithPayments
                val lines: List<QuoteLineItemRead>
                coroutineScope {
                    val inv = async { ApiClient.api.getInvoice(invoiceId) }
                    val li = async {
                        try {
                            ApiClient.api.getInvoiceLineItems(invoiceId)
                        } catch (_: Exception) {
                            emptyList()
                        }
                    }
                    data = inv.await()
                    lines = li.await()
                }
                _state.update { it.copy(loading = false, data = data, lineItems = lines) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load invoice") }
            }
        }
    }

    fun recordPayment(amountCents: Int, providerReference: String?) {
        viewModelScope.launch {
            _state.update { it.copy(paymentBusy = true, error = null, paymentInfo = null) }
            try {
                ApiClient.api.postInvoicePayment(
                    invoiceId,
                    PaymentCreate(
                        amountCents = amountCents,
                        providerReference = providerReference?.trim()?.takeIf { it.isNotEmpty() },
                    ),
                )
                val data = ApiClient.api.getInvoice(invoiceId)
                val lines = try {
                    ApiClient.api.getInvoiceLineItems(invoiceId)
                } catch (_: Exception) {
                    _state.value.lineItems
                }
                _state.update {
                    it.copy(paymentBusy = false, data = data, lineItems = lines, paymentInfo = "Payment recorded.")
                }
            } catch (e: Exception) {
                _state.update { it.copy(paymentBusy = false, error = e.message ?: "Payment failed") }
            }
        }
    }

    companion object {
        /** Parses amounts like "12", "12.50", "$12.50" into cents, or null if invalid. */
        fun parseDollarsToCents(input: String): Int? {
            val t = input.trim().removePrefix("$").replace(",", "").trim()
            if (t.isEmpty()) return null
            val d = t.toDoubleOrNull() ?: return null
            if (d <= 0) return null
            return (d * 100.0 + 0.5).toInt()
        }

        fun factory(invoiceId: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return InvoiceDetailViewModel(invoiceId) as T
            }
        }
    }
}

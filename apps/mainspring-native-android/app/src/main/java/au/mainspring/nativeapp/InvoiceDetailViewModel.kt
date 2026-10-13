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
    val paymentUnknown: Boolean = false,
    val historyChecked: Boolean = false,
    val sendBusy: Boolean = false,
    val sendInfo: String? = null,
)

class InvoiceDetailViewModel(
    private val invoiceId: String,
) : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
    private val operationKey = "payment:$invoiceId"
    private val _state = MutableStateFlow(InvoiceDetailUiState(paymentUnknown = drafts.pendingOperation(operationKey)))
    val state: StateFlow<InvoiceDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        if (_state.value.loading || _state.value.paymentBusy) return
        _state.update { it.copy(loading = true, error = null, paymentInfo = null) }
        viewModelScope.launch {
            try {
                val data: InvoiceWithPayments
                val lines: List<QuoteLineItemRead>
                coroutineScope {
                    val inv = async { api.getInvoice(invoiceId) }
                    val li = async {
                        try {
                            api.getInvoiceLineItems(invoiceId)
                        } catch (_: Exception) {
                            emptyList()
                        }
                    }
                    data = inv.await()
                    lines = li.await()
                }
                _state.update { it.copy(loading = false, data = data, lineItems = lines, historyChecked = true) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = "Could not load invoice. ${e.userMessage()}") }
            }
        }
    }

    fun recordPayment(amountCents: Int, providerReference: String?) {
        if (_state.value.loading || _state.value.paymentBusy || _state.value.paymentUnknown || !TokenStore.canManageInvoices()) return
        val snapshot = _state.value.data ?: return
        if(snapshot.invoice.status != "unpaid") { _state.update { it.copy(error = "Payments can only be recorded for an unpaid invoice.") }; return }
        val remaining = snapshot.invoice.totalCents - snapshot.payments.sumOf { it.amountCents }
        if(amountCents <= 0 || amountCents > remaining) { _state.update { it.copy(error = "Enter an amount within the remaining balance.") }; return }
        if(!drafts.setPendingOperation(operationKey, true)) { _state.update { it.copy(error = "Could not save the payment checkpoint. Check device storage and sign in before continuing.") }; return }
        _state.update { it.copy(paymentBusy = true, error = null, paymentInfo = null) }
        viewModelScope.launch {
            try {
                val payment = api.postInvoicePayment(
                    invoiceId,
                    PaymentCreate(
                        amountCents = amountCents,
                        providerReference = providerReference?.trim()?.takeIf { it.isNotEmpty() },
                    ),
                )
                drafts.setPendingOperation(operationKey, false)
                _state.update { it.copy(data = snapshot.copy(payments = snapshot.payments + payment), paymentInfo = "Payment recorded.") }
                val data = try { api.getInvoice(invoiceId) } catch (_: Exception) { _state.value.data!! }
                val lines = try {
                    api.getInvoiceLineItems(invoiceId)
                } catch (_: Exception) {
                    _state.value.lineItems
                }
                _state.update {
                    it.copy(paymentBusy = false, data = data, lineItems = lines, paymentInfo = "Payment recorded.")
                }
            } catch (e: Exception) {
                val unknown = e !is retrofit2.HttpException || e.code() >= 500
                drafts.setPendingOperation(operationKey, unknown)
                _state.update { it.copy(paymentBusy = false, paymentUnknown = unknown, historyChecked = false,
                    error = "Could not confirm this payment. Refresh and check payment history before recording another payment. ${e.userMessage()}") }
            }
        }
    }
    fun acknowledgePaymentHistory() { if(!_state.value.historyChecked) return; drafts.setPendingOperation(operationKey, false); _state.update { it.copy(paymentUnknown = false) } }

    fun sendInvoice() {
        if(_state.value.sendBusy || !TokenStore.canManageInvoices()) return
        _state.update { it.copy(sendBusy = true, sendInfo = null) }
        viewModelScope.launch {
            try {
                val result = api.sendInvoice(invoiceId)
                val info = if(result.emailSent) "Invoice emailed to customer." else when(result.skippedReason) {
                    "email_disabled" -> "Email notifications are disabled for this shop."
                    "sendgrid_not_configured" -> "Email delivery is not configured for this shop."
                    else -> "Invoice email was not sent. ${result.errorDetail.orEmpty()}"
                }
                _state.update { it.copy(sendBusy = false, sendInfo = info) }
            } catch(e: Exception) { _state.update { it.copy(sendBusy = false, sendInfo = "Could not confirm the invoice email. Check delivery before resending. ${e.userMessage()}") } }
        }
    }

    companion object {
        /** Parses amounts like "12", "12.50", "$12.50" into cents, or null if invalid. */
        fun parseDollarsToCents(input: String): Int? {
            val t = input.trim().removePrefix("$").replace(",", "").trim()
            if (t.isEmpty()) return null
            return try { dollarsToCentsChecked(t).takeIf { it > 0 } } catch (_: Exception) { null }
        }

        fun factory(invoiceId: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return InvoiceDetailViewModel(invoiceId) as T
            }
        }
    }
}


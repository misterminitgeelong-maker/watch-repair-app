package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class AccountsState(
    val loading: Boolean = false, val error: String? = null,
    val session: SessionResponse? = null, val billing: BillingLimits? = null, val billingError: String? = null,
    val busy: Boolean = false, val info: String? = null, val actionError: String? = null,
)
class AccountsViewModel : ViewModel() {
    private val mutable = MutableStateFlow(AccountsState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    private val billingApi get() = ApiClient.service(AccountsApi::class.java)
    init { refresh() }
    private fun isOwner() = mutable.value.session?.user?.role == "owner"

    /** Re-checks the shop's Stripe card payments and payouts with Stripe (web "Refresh status"). Owner only. */
    fun refreshPayouts() {
        if(mutable.value.busy || !isOwner()) return
        mutable.update { it.copy(busy = true, info = null, actionError = null) }
        viewModelScope.launch {
            try {
                val status = billingApi.refreshStripeConnect()
                mutable.update { s -> s.copy(busy = false, info = payoutSummary(status),
                    billing = s.billing?.copy(stripeConnectCharges = status.charges, stripeConnectPayouts = status.payouts, stripeConnectDetails = status.details)) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(busy = false, actionError = "Could not refresh payout status. ${e.userMessage()}") } }
        }
    }

    /** Disconnects Xero for the whole shop (web "Disconnect"). Owner only; invoices stop syncing until it is reconnected on the web. */
    fun disconnectXero() {
        if(mutable.value.busy || !isOwner()) return
        mutable.update { it.copy(busy = true, info = null, actionError = null) }
        viewModelScope.launch {
            try {
                val status = billingApi.disconnectXero()
                mutable.update { s -> s.copy(busy = false, info = "Xero disconnected.",
                    billing = s.billing?.copy(xeroConnected = status.connected, xeroConnectionStatus = status.connectionStatus)) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(busy = false, actionError = "Could not disconnect Xero. ${e.userMessage()}") } }
        }
    }
    fun refresh() {
        request?.cancel()
        mutable.update { it.copy(loading = true, error = null, billingError = null) }
        request = viewModelScope.launch {
            try {
                val session = ApiClient.api.session()
                mutable.update { it.copy(session = session) }
                // Billing is manager-only context; a failure there must not hide the account itself.
                var billing: BillingLimits? = null; var billingError: String? = null
                if(TokenStore.canManageInvoices()) {
                    try { billing = ApiClient.service(AccountsApi::class.java).billingLimits() }
                    catch(e: CancellationException) { throw e }
                    catch(e: Exception) { billingError = e.userMessage() }
                }
                mutable.update { it.copy(loading = false, billing = billing, billingError = billingError) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}

/** Plain-language result of a payout status refresh. */
fun payoutSummary(status: StripeConnectStatus): String = when {
    status.charges && status.payouts -> "Card payments and payouts are enabled."
    status.charges -> "Card payments are enabled. Payouts are not enabled yet; Stripe may still be verifying your details."
    status.details -> "Stripe has your details and is still verifying them. Card payments are not enabled yet."
    else -> "Stripe onboarding is not finished. Finish it on the web to accept card payments."
}

package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class AccountsState(
    val loading: Boolean = false, val error: String? = null,
    val session: SessionResponse? = null, val billing: BillingLimits? = null, val billingError: String? = null,
)
class AccountsViewModel : ViewModel() {
    private val mutable = MutableStateFlow(AccountsState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }
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

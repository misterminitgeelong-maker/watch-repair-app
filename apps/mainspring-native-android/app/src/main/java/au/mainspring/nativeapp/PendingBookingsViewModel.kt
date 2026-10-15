package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

/** Count of shop booking requests waiting on this operator, for the badge on the job board (web: ShopBookingInbox). */
class PendingBookingsViewModel : ViewModel() {
    private val api = ApiClient.api
    private val mutable = MutableStateFlow(0)
    val pending = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }

    fun refresh() {
        request?.cancel()
        request = viewModelScope.launch {
            try {
                val tenant = TokenStore.currentTenantId()
                mutable.value = api.bookingRequests(limit = 100).items.count { it.status == "pending" && it.targetTenant == tenant }
            } catch(e: CancellationException) { throw e }
            catch(_: Exception) { /* the badge is a hint: an unavailable feature or a flaky network just hides it */ }
        }
    }
}

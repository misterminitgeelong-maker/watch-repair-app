package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.AcceptBookingApi
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.BookingRequest
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AcceptBookingState(
    val loading: Boolean = true, val accepting: Boolean = false,
    /** The booking as listed, when it could be found (best effort: accepting does not require it). */
    val booking: BookingRequest? = null, val result: BookingRequest? = null, val error: String? = null,
)

/**
 * Accept flow for a booking opened from a deep link. The web accepts immediately on landing; the app shows the request
 * first and accepts only on an explicit tap, so a link preview or accidental open never changes data.
 */
class AcceptBookingViewModel(private val bookingId: String) : ViewModel() {
    private val mutable = MutableStateFlow(AcceptBookingState())
    val state = mutable.asStateFlow()
    init { load() }

    fun load() {
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val found = ApiClient.api.bookingRequests(limit = 100).items.firstOrNull { it.id == bookingId }
                mutable.update { it.copy(loading = false, booking = found) }
            } catch(e: CancellationException) { throw e }
            catch(_: Exception) { mutable.update { it.copy(loading = false) } } // the summary is optional; the accept call is authoritative
        }
    }

    fun accept() {
        val s = mutable.value
        if(s.accepting || s.loading || s.result != null) return
        mutable.update { it.copy(accepting = true, error = null) }
        viewModelScope.launch {
            try {
                val row = ApiClient.service(AcceptBookingApi::class.java).accept(bookingId)
                mutable.update { it.copy(accepting = false, result = row, booking = row) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(accepting = false, error = "Could not accept this booking. ${e.userMessage()}") } }
        }
    }

    companion object {
        fun factory(id: String) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST") override fun <T : ViewModel> create(modelClass: Class<T>): T = AcceptBookingViewModel(id) as T
        }
    }
}

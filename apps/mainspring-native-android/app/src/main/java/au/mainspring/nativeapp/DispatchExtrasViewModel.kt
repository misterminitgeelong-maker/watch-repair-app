package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class DispatchExtrasState(
    val technicians: List<TeamUser> = emptyList(),
    val busy: Boolean = false,
    val message: String? = null,
    val error: String? = null,
    /** True after a send whose outcome is unknown: customers may already have been texted. */
    val uncertain: Boolean = false,
    val baseSaved: BaseLocation? = null,
)

/** Technician lanes, day-before reminders and base location for the Dispatch and Pool screens. */
class DispatchExtrasViewModel : ViewModel() {
    private val api = ApiClient.service(DispatchExtrasApi::class.java)
    private val mutable = MutableStateFlow(DispatchExtrasState())
    val state = mutable.asStateFlow()

    init { loadTechnicians() }

    fun loadTechnicians() {
        viewModelScope.launch {
            try {
                val users = ApiClient.api.teamUsers().filter { it.active }
                mutable.update { it.copy(technicians = users) }
            } catch(e: CancellationException) { throw e }
            catch(_: Exception) { /* technicians are optional (techs may not be allowed to list users); lanes just stay hidden */ }
        }
    }

    fun sendReminders() {
        if(mutable.value.busy || mutable.value.uncertain) return
        mutable.update { it.copy(busy = true, message = null, error = null) }
        viewModelScope.launch {
            try {
                val result = api.sendDayBeforeReminders()
                mutable.update { it.copy(message = if(result.sent == 0) "No reminders to send. Tomorrow has no booked customers with a phone number." else "Reminders sent to ${result.sent} customer${if(result.sent == 1) "" else "s"}.") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val definite = e is HttpException && e.code() in 400..499
                mutable.update { it.copy(uncertain = !definite,
                    error = if(definite) e.userMessage() else "Could not confirm the reminders were sent. Some customers may already have been texted. ${e.userMessage()}") }
            } finally { mutable.update { it.copy(busy = false) } }
        }
    }

    fun acknowledgeUncertain() = mutable.update { it.copy(uncertain = false, error = null) }
    fun clearMessage() = mutable.update { it.copy(message = null, error = null) }

    fun saveBaseLocation(address: String, radiusKm: Int, onSaved: () -> Unit = {}) {
        val trimmed = address.trim()
        if(mutable.value.busy) return
        if(trimmed.length < 5) { mutable.update { it.copy(error = "Enter a full address (at least 5 characters).") }; return }
        if(radiusKm !in 1..200) { mutable.update { it.copy(error = "Radius must be between 1 and 200 km.") }; return }
        mutable.update { it.copy(busy = true, error = null, message = null) }
        viewModelScope.launch {
            try {
                val saved = api.setBaseLocation(JsonObject().apply { addProperty("address", trimmed); addProperty("ring_radius_km", radiusKm) })
                mutable.update { it.copy(baseSaved = saved, message = "Base location saved. Pool rings are measured from here.") }
                onSaved()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
            finally { mutable.update { it.copy(busy = false) } }
        }
    }
}

package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AutoKeyJobRead
import au.mainspring.nativeapp.api.AutoKeyQuickIntakeCreate
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SendBookingRequestState(
    val name: String = "",
    val phone: String = "",
    val busy: Boolean = false,
    val error: String? = null,
    /** True when an earlier send may have reached the server; the operator must check before repeating it. */
    val uncertain: Boolean = false,
    val result: AutoKeyJobRead? = null,
)

/** Mirrors the web SendBookingRequestModal: phone is required, name falls back to "Customer". */
class SendBookingRequestViewModel : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val draftKey = "send-booking-request"

    private fun restored(): Map<String, String> = try {
        Gson().fromJson<Map<String, String>>(drafts.loadMessageDraft(draftKey).ifBlank { "{}" }, object : TypeToken<Map<String, String>>() {}.type) ?: emptyMap()
    } catch (_: Exception) { emptyMap() }

    private val mutable = MutableStateFlow(restored().let {
        SendBookingRequestState(name = it["name"].orEmpty(), phone = it["phone"].orEmpty(), uncertain = drafts.pendingOperation(draftKey))
    })
    val state = mutable.asStateFlow()

    private fun saveDraft() {
        val s = mutable.value
        drafts.saveMessageDraft(draftKey, if (s.name.isBlank() && s.phone.isBlank()) "" else Gson().toJson(mapOf("name" to s.name, "phone" to s.phone)))
    }

    fun name(value: String) { if (mutable.value.busy) return; mutable.update { it.copy(name = value, error = null) }; saveDraft() }
    fun phone(value: String) { if (mutable.value.busy) return; mutable.update { it.copy(phone = value, error = null) }; saveDraft() }

    fun checkedWithCustomer() { drafts.setPendingOperation(draftKey, false); mutable.update { it.copy(uncertain = false) } }

    /** Clears the result so another request can be sent. */
    fun startAnother() { if (mutable.value.busy) return; mutable.update { SendBookingRequestState() } }

    fun send() {
        val s = mutable.value
        if (s.busy || s.uncertain || s.result != null) return
        val phone = s.phone.trim()
        if (phone.isEmpty()) { mutable.update { it.copy(error = "Enter the customer's mobile number.") }; return }
        if (!drafts.setPendingOperation(draftKey, true)) {
            mutable.update { it.copy(error = "Could not save the send checkpoint. Check device storage and sign in before continuing.") }; return
        }
        mutable.update { it.copy(busy = true, error = null) }
        val body = AutoKeyQuickIntakeCreate(fullName = s.name.trim().ifEmpty { "Customer" }, phone = phone)
        viewModelScope.launch {
            try {
                val job = api.postAutoKeyQuickIntake(body)
                drafts.setPendingOperation(draftKey, false); drafts.saveMessageDraft(draftKey, "")
                mutable.update { it.copy(busy = false, result = job, uncertain = false) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                val unknown = e !is retrofit2.HttpException || e.code() >= 500
                drafts.setPendingOperation(draftKey, unknown)
                mutable.update {
                    it.copy(busy = false, uncertain = unknown,
                        error = (if (unknown) "Could not confirm the request was sent. Check with the customer before repeating it. " else "") + e.userMessage())
                }
            }
        }
    }
}

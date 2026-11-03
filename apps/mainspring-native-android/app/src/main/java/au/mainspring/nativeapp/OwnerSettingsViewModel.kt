package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class OwnerSettingsState(
    val loading: Boolean = true,
    val allowed: Boolean = true,
    val identity: ShopIdentity? = null,
    val identityError: String? = null,
    val savingIdentity: Boolean = false,
    val identityInfo: String? = null,
    val prefs: NotificationPrefs? = null,
    val prefsError: String? = null,
    val savingPref: String? = null,
    val health: IntegrationHealth? = null,
    val healthError: String? = null,
)

private val HEX_COLOR = Regex("^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

/** Shop identity editing (manager+), the signed-in user's email alert preferences, and integration health. */
class OwnerSettingsViewModel(private val api: OwnerAdminApi = ApiClient.service(OwnerAdminApi::class.java)) : ViewModel() {
    private val mutable = MutableStateFlow(OwnerSettingsState(allowed = TokenStore.canManageInvoices()))
    val state = mutable.asStateFlow()

    init { refresh() }

    fun refresh() {
        mutable.update { it.copy(loading = true, identityError = null, prefsError = null, healthError = null) }
        viewModelScope.launch {
            if(TokenStore.canManageInvoices()) {
                try { val v = api.shopIdentity(); mutable.update { it.copy(identity = v) } }
                catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(identityError = e.userMessage()) } }
            }
            try { val v = api.notificationPrefs(); mutable.update { it.copy(prefs = v) } }
            catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(prefsError = e.userMessage()) } }
            try { val v = api.integrationHealth(); mutable.update { it.copy(health = v) } }
            catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(healthError = e.userMessage()) } }
            mutable.update { it.copy(loading = false) }
        }
    }

    /** Returns a validation message, or null when the form is acceptable. */
    fun validate(phone: String, email: String, color: String, logoUrl: String): String? = when {
        email.isNotBlank() && !email.contains('@') -> "Enter a valid shop email."
        color.isNotBlank() && !HEX_COLOR.matches(color.trim()) -> "Brand colour must be a hex value such as #1A2B3C."
        logoUrl.isNotBlank() && !logoUrl.trim().startsWith("https://") -> "The logo link must start with https://."
        phone.length > 40 || email.length > 200 || logoUrl.length > 1000 -> "One of the fields is too long."
        else -> null
    }

    fun saveIdentity(abn: String, phone: String, email: String, payment: String, logoUrl: String, color: String) {
        if(!TokenStore.canManageInvoices() || mutable.value.savingIdentity) return
        validate(phone, email, color, logoUrl)?.let { msg -> mutable.update { it.copy(identityError = msg, identityInfo = null) }; return }
        mutable.update { it.copy(savingIdentity = true, identityError = null, identityInfo = null) }
        viewModelScope.launch {
            try {
                val saved = api.updateShopIdentity(ShopIdentityUpdate(abn.trim(), phone.trim(), email.trim(), payment.trim(), logoUrl.trim(), color.trim()))
                mutable.update { it.copy(identity = saved, savingIdentity = false, identityInfo = "Shop details saved.") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(savingIdentity = false, identityError = e.userMessage()) } }
        }
    }

    /** Toggles one email preference; the switch reflects the server's answer, not the optimistic tap. */
    fun setPref(field: String, value: Boolean) {
        if(mutable.value.savingPref != null) return
        mutable.update { it.copy(savingPref = field, prefsError = null) }
        viewModelScope.launch {
            try {
                val saved = api.updateNotificationPrefs(JsonObject().apply { addProperty(field, value) })
                mutable.update { it.copy(prefs = saved, savingPref = null) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(savingPref = null, prefsError = e.userMessage()) } }
        }
    }
}

package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException
import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonNull
import com.google.gson.JsonObject

data class ToolkitState(val catalog: ToolkitCatalog? = null, val selected: Set<String> = emptySet(), val saved: Set<String> = emptySet(),
 val loading: Boolean = true, val busy: Boolean = false, val error: String? = null, val readiness: ToolReadiness? = null)
/** Shop-level mobile services settings shown under "Settings" on the toolkit screen. Loaded independently of the tool selection. */
data class ToolkitSettingsState(
    val loaded: Boolean = false, val loading: Boolean = false, val busy: Boolean = false, val error: String? = null,
    val smsEnabled: Boolean = true, val dispatchPhone: String = "", val phoneDraft: String = "",
    val enabledCategories: Set<String> = emptySet(), val availableCategories: List<CatalogueCategory> = emptyList(),
    /** Owner / manager can change notifications; only the owner can change the catalogue (server rule). Others see read-only values. */
    val canEditNotifications: Boolean = false, val canEditCatalogue: Boolean = false,
)
class ToolkitViewModel: ViewModel() {
    private val settingsApi = au.mainspring.nativeapp.api.ApiClient.service(ToolkitSettingsApi::class.java)
    private val mutableSettings = MutableStateFlow(ToolkitSettingsState(
        canEditNotifications = au.mainspring.nativeapp.TokenStore.canManageInvoices(), canEditCatalogue = au.mainspring.nativeapp.TokenStore.canManageTeam()))
    val settings = mutableSettings.asStateFlow()
    fun loadSettings() { if(mutableSettings.value.busy) return; mutableSettings.update { it.copy(loading = true, error = null) }
        viewModelScope.launch { try {
            val notifications = settingsApi.notifications(); val catalogue = settingsApi.catalogue()
            mutableSettings.update { it.copy(loaded = true, loading = false, smsEnabled = notifications.customerSmsEnabled, dispatchPhone = notifications.dispatchPhone.orEmpty(),
                phoneDraft = notifications.dispatchPhone.orEmpty(), enabledCategories = catalogue.enabledCategories.toSet(), availableCategories = catalogue.availableCategories) }
        } catch(e: CancellationException) { throw e } catch(e: Exception) { mutableSettings.update { it.copy(loading = false, error = "Could not load shop settings. ${e.userMessage()}") } } }
    }
    fun phoneDraft(value: String) { mutableSettings.update { it.copy(phoneDraft = value.take(80)) } }
    fun setSms(enabled: Boolean) = patchNotifications(JsonObject().apply { addProperty("customer_sms_enabled", enabled) })
    fun saveDispatchPhone() { val phone = mutableSettings.value.phoneDraft.trim()
        patchNotifications(JsonObject().apply { if(phone.isEmpty()) add("dispatch_phone", JsonNull.INSTANCE) else addProperty("dispatch_phone", phone) }) }
    private fun patchNotifications(body: JsonObject) { val s = mutableSettings.value; if(!s.canEditNotifications || s.busy || s.loading) return
        mutableSettings.update { it.copy(busy = true, error = null) }
        viewModelScope.launch { try { val r = settingsApi.saveNotifications(body)
            mutableSettings.update { it.copy(busy = false, smsEnabled = r.customerSmsEnabled, dispatchPhone = r.dispatchPhone.orEmpty(), phoneDraft = r.dispatchPhone.orEmpty()) }
        } catch(e: CancellationException) { throw e } catch(e: Exception) { mutableSettings.update { it.copy(busy = false, error = "Could not save notification settings. ${e.userMessage()}") } } }
    }
    fun toggleCategory(key: String) { val s = mutableSettings.value; if(!s.canEditCatalogue || s.busy || s.loading) return
        val next = if(key in s.enabledCategories) s.enabledCategories - key else s.enabledCategories + key
        if(next.isEmpty()) { mutableSettings.update { it.copy(error = "Keep at least one category enabled.") }; return }
        val ordered = s.availableCategories.map { it.key }.filter { it in next }
        mutableSettings.update { it.copy(busy = true, error = null) }
        viewModelScope.launch { try { val r = settingsApi.saveCatalogue(JsonObject().apply { add("enabled_categories", JsonArray().also { a -> ordered.forEach(a::add) }) })
            mutableSettings.update { it.copy(busy = false, enabledCategories = r.enabledCategories.toSet(), availableCategories = r.availableCategories.ifEmpty { it.availableCategories }) }
        } catch(e: CancellationException) { throw e } catch(e: Exception) { mutableSettings.update { it.copy(busy = false, error = "Could not save catalogue categories. ${e.userMessage()}") } } }
    }
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 private val mutable = MutableStateFlow(ToolkitState()); val state = mutable.asStateFlow()
 init { load(); loadSettings() }
 fun load() { if(mutable.value.busy) return; mutable.update { it.copy(loading = true, error = null) }
  viewModelScope.launch { try {
   val catalog = api.toolkitCatalog(); val saved = api.toolkitSelection().keys.toSet()
   val raw = drafts.loadMessageDraft("toolkit")
   val draft = try { if(raw.isBlank()) null else Gson().fromJson(raw, ToolSelection::class.java).keys.toSet() } catch(_: Exception) { null }
   val valid = catalog.groups.flatMap { it.tools }.map { it.key }.toSet()
   mutable.value = ToolkitState(catalog, (draft ?: saved).intersect(valid), saved, loading = false)
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not load the shop toolkit. ${e.userMessage()}") } } }
 }
 fun toggle(key: String) { if(mutable.value.loading || mutable.value.busy) return
  mutable.update { it.copy(selected = if(key in it.selected) it.selected - key else it.selected + key, readiness = null) }; persist() }
 private fun persist() { drafts.saveMessageDraft("toolkit", Gson().toJson(ToolSelection(mutable.value.selected.toList()))) }
 fun discard() { mutable.update { it.copy(selected = it.saved, readiness = null) }; drafts.saveMessageDraft("toolkit", "") }
 fun save() { if(mutable.value.loading || mutable.value.busy) return; val keys = mutable.value.selected.toList(); mutable.update { it.copy(busy = true, error = null) }
  viewModelScope.launch { try {
   val result = api.saveToolkit(ToolSelection(keys)); drafts.saveMessageDraft("toolkit", "")
   mutable.update { it.copy(busy = false, selected = result.keys.toSet(), saved = result.keys.toSet()) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(busy = false, error = "Could not confirm selection save. Refresh before retrying. ${e.userMessage()}") } } }
 }
 fun checkScenario(id: String) { if(mutable.value.loading || mutable.value.busy) return; mutable.update { it.copy(busy = true, error = null) }
  viewModelScope.launch { try { val result = api.toolkitRecommend(ToolRecommend(id, mutable.value.selected.toList())); mutable.update { it.copy(busy = false, readiness = result) } }
   catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(busy = false, error = "Could not check this scenario. ${e.userMessage()}") } } }
 }
}

